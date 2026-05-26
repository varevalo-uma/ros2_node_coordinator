#!/usr/bin/env python3

"""Coordinate play/stop commands and acknowledgments across managed nodes."""

import json
from dataclasses import dataclass
from typing import Any, Callable

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import String


@dataclass
class NodeState:
    """Store runtime status for a managed node."""
    name: str
    status: str = 'stopped'


class StateMachine:
    """Represent a simple event-driven state machine."""

    def __init__(self, initial_state: str):
        """Initialize the state machine with an initial state."""
        self.state = initial_state
        self._transitions: dict[tuple[str, str], tuple[str, Callable[[], None] | None]] = {}

    def add_transition(
        self,
        source_state: str,
        event: str,
        target_state: str,
        action: Callable[[], None] | None = None,
    ) -> None:
        """Register a transition for a source state and event."""
        self._transitions[(source_state, event)] = (target_state, action)

    def trigger(self, event: str) -> bool:
        """Apply a transition for the current state and event if available."""
        transition = self._transitions.get((self.state, event))
        if transition is None:
            return False

        target_state, action = transition
        self.state = target_state

        if action is not None:
            action()

        return True


class Coordinator(Node):
    """Broadcast play/stop commands and collect node acknowledgments."""

    def __init__(self):
        """Initialize publishers, subscriptions, and lifecycle state."""
        super().__init__('coordinator')
        self.set_parameters([
            Parameter('use_sim_time', Parameter.Type.BOOL, True),
        ])

        self.declare_parameter('node_names', ['nodo1', 'nodo2'])
        self.declare_parameter('run_duration_sec', 5.0)
        self.declare_parameter('auto_start', True)
        self.declare_parameter(
            'example_config',
            '{"mission":"demo","owner":"coordinator"}',
        )

        self.node_names = list(
            self.get_parameter('node_names').get_parameter_value().string_array_value,
        )
        self.run_duration_sec = (
            self.get_parameter('run_duration_sec')
            .get_parameter_value()
            .double_value
        )
        self.auto_start = self.get_parameter('auto_start').get_parameter_value().bool_value
        self.example_config = self._load_config_parameter()
        self._started_at_ns: int | None = None
        self._started_once = False

        self._nodes = {
            name: NodeState(name=name, status='stopped')
            for name in self.node_names
        }
        self._play_publishers = {}
        self._stop_publishers = {}

        for name in self.node_names:
            self._play_publishers[name] = self.create_publisher(
                String,
                f'/{name}/play',
                10,
            )
            self._stop_publishers[name] = self.create_publisher(
                String,
                f'/{name}/stop',
                10,
            )
            self.create_subscription(
                String,
                f'/{name}/play_ack',
                self._make_play_ack_callback(name),
                10,
            )
            self.create_subscription(
                String,
                f'/{name}/stop_ack',
                self._make_stop_ack_callback(name),
                10,
            )

        self._sm = StateMachine(initial_state='idle')
        self._configure_state_machine()

        self.timer = self.create_timer(0.5, self._tick)
        self.get_logger().info(
            'Coordinator started for nodes: %s' % ', '.join(self.node_names),
        )

    def _configure_state_machine(self) -> None:
        """Define coordinator state transitions and entry actions."""
        self._sm.add_transition('idle', 'start', 'starting', self._on_enter_starting)
        self._sm.add_transition('starting', 'all_play_acked', 'running', self._on_enter_running)
        self._sm.add_transition('starting', 'stop_requested', 'stopping', self._on_enter_stopping)
        self._sm.add_transition('running', 'stop_requested', 'stopping', self._on_enter_stopping)
        self._sm.add_transition('stopping', 'all_stop_acked', 'done', self._on_enter_done)

    def _transition(self, event: str) -> bool:
        """Trigger an event and log the resulting state transition."""
        previous_state = self._sm.state
        moved = self._sm.trigger(event)
        if moved:
            self.get_logger().info(
                'Transition %s --(%s)--> %s' % (
                    previous_state,
                    event,
                    self._sm.state,
                ),
            )
        return moved

    def _on_enter_starting(self) -> None:
        """Enter the starting phase and broadcast play."""
        self._broadcast_play()

    def _on_enter_running(self) -> None:
        """Enter the running phase after all play acknowledgments arrive."""
        self._started_at_ns = self.get_clock().now().nanoseconds
        self.get_logger().info('All nodes acknowledged the play command.')

    def _on_enter_stopping(self) -> None:
        """Enter the stopping phase and broadcast stop."""
        self._broadcast_stop()

    def _on_enter_done(self) -> None:
        """Finish the lifecycle once all stop acknowledgments arrive."""
        self.get_logger().info('All nodes acknowledged the stop command.')
        self.timer.cancel()
        # Request shutdown on this node context so spin() can exit cleanly.
        self.context.try_shutdown()

    def _load_config_parameter(self) -> dict[str, Any]:
        """Parse the JSON configuration stored in the parameter server."""
        raw_config = (
            self.get_parameter('example_config')
            .get_parameter_value()
            .string_value
        )

        try:
            config = json.loads(raw_config)
        except json.JSONDecodeError:
            self.get_logger().warning(
                'Parameter example_config is not valid JSON: %s' % raw_config,
            )
            return {'raw_config': raw_config}

        if isinstance(config, dict):
            return config

        return {'value': config}

    def _make_play_ack_callback(self, expected_name: str):
        """Create a bound callback for play acknowledgments."""

        def callback(msg: String) -> None:
            self._handle_play_ack(expected_name, msg)

        return callback

    def _make_stop_ack_callback(self, expected_name: str):
        """Create a bound callback for stop acknowledgments."""

        def callback(msg: String) -> None:
            self._handle_stop_ack(expected_name, msg)

        return callback

    def _parse_ack(self, expected_name: str, msg: String) -> tuple[str, str] | None:
        """Decode an acknowledgment payload and validate sender identity."""
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning(
                'Invalid acknowledgment from %s: %s' % (expected_name, msg.data),
            )
            return None

        node_name = payload.get('node', expected_name)
        status = payload.get('status')

        if node_name not in self._nodes:
            self.get_logger().warning('Ignoring ack from unknown node: %s' % node_name)
            return None

        return node_name, status

    def _handle_play_ack(self, expected_name: str, msg: String) -> None:
        """Process a play acknowledgment and advance state when complete."""
        ack_data = self._parse_ack(expected_name, msg)
        if ack_data is None:
            return

        node_name, status = ack_data
        if status != 'playing':
            self.get_logger().warning(
                'Ignoring unexpected play_ack status from %s: %s' % (node_name, status),
            )
            return

        self._nodes[node_name].status = status
        self.get_logger().info('Play ack from %s: %s' % (node_name, status))

        if self._sm.state == 'starting' and self._all_nodes_in_state('playing'):
            self._transition('all_play_acked')

    def _handle_stop_ack(self, expected_name: str, msg: String) -> None:
        """Process a stop acknowledgment and advance state when complete."""
        ack_data = self._parse_ack(expected_name, msg)
        if ack_data is None:
            return

        node_name, status = ack_data
        if status != 'stopped':
            self.get_logger().warning(
                'Ignoring unexpected stop_ack status from %s: %s' % (node_name, status),
            )
            return

        self._nodes[node_name].status = status
        self.get_logger().info('Stop ack from %s: %s' % (node_name, status))

        if self._sm.state == 'stopping' and self._all_nodes_in_state('stopped'):
            self._transition('all_stop_acked')

    def _all_nodes_in_state(self, status: str) -> bool:
        """Return whether all managed nodes match the requested status."""
        return all(node.status == status for node in self._nodes.values())

    def _build_control_message(self) -> String:
        """Build the JSON payload shared by play and stop commands."""
        msg = String()
        msg.data = json.dumps({
            'source': self.get_name(),
            'config': self.example_config,
        })
        return msg

    def _broadcast_play(self) -> None:
        """Publish a play command to each managed node."""
        msg = self._build_control_message()

        for name, publisher in self._play_publishers.items():
            self._nodes[name].status = 'starting'
            publisher.publish(msg)

        self.get_logger().info('Broadcasted play command.')

    def _broadcast_stop(self) -> None:
        """Publish a stop command to each managed node."""
        msg = self._build_control_message()

        for name, publisher in self._stop_publishers.items():
            self._nodes[name].status = 'stopping'
            publisher.publish(msg)

        self.get_logger().info('Broadcasted stop command.')

    def _tick(self) -> None:
        """Drive automatic transitions based on elapsed time and acknowledgments."""
        if self.auto_start and not self._started_once and self._sm.state == 'idle':
            if self._transition('start'):
                self._started_once = True
            return

        if self._sm.state != 'running' or self._started_at_ns is None:
            return

        elapsed_sec = (
            self.get_clock().now().nanoseconds - self._started_at_ns
        ) / 1e9

        if elapsed_sec < self.run_duration_sec:
            return

        self._transition('stop_requested')


def main(args=None) -> None:
    """Run the coordinator node."""
    rclpy.init(args=args)
    node = Coordinator()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        node.context.try_shutdown()


if __name__ == '__main__':
    main()
