#!/usr/bin/env python3

"""Implement the first coordinator-managed worker node."""

import time
from typing import Any

import rclpy
from std_msgs.msg import String

from roscoord_pkg.managed_node import ManagedNode


class Nodo1(ManagedNode):
    """Implement coordinator callbacks for worker node nodo1."""

    def __init__(self):
        """Initialize subscriptions and acknowledgment publishers for nodo1."""
        super().__init__('nodo1')
        self.create_subscription(String, '/nodo1/play', self.cb_play, 10)
        self.create_subscription(String, '/nodo1/stop', self.cb_stop, 10)
        self.play_ack_publisher = self.create_publisher(String, '/nodo1/play_ack', 10)
        self.stop_ack_publisher = self.create_publisher(String, '/nodo1/stop_ack', 10)

    def cb_play(self, msg: String) -> None:
        """Handle a play command and publish a play acknowledgment."""
        config = self.load_config(msg)
        work_duration_sec = self._safe_float(config.get('nodo1_play_sec', 0.25), 0.25)
        if self.status == 'playing':
            self.get_logger().warning('Nodo1 is already playing, sending play ack again.')
            self.publish_ack(self.play_ack_publisher, 'playing')
            return

        self.status = 'playing'
        self.get_logger().info(
            'Nodo1 simulating play work for %.2f seconds.' % work_duration_sec,
        )
        time.sleep(work_duration_sec)
        self.on_start(config)
        self.publish_ack(self.play_ack_publisher, 'playing')

    def cb_stop(self, msg: String) -> None:
        """Handle a stop command and publish a stop acknowledgment."""
        config = self.load_config(msg)
        work_duration_sec = self._safe_float(config.get('nodo1_stop_sec', 0.10), 0.10)
        if self.status == 'stopped':
            self.get_logger().warning('Nodo1 is already stopped, sending stop ack again.')
            self.publish_ack(self.stop_ack_publisher, 'stopped')
            return

        self.status = 'stopped'
        self.get_logger().info(
            'Nodo1 simulating stop work for %.2f seconds.' % work_duration_sec,
        )
        time.sleep(work_duration_sec)
        self.on_stop()
        self.publish_ack(self.stop_ack_publisher, 'stopped')

    def _safe_float(self, value: Any, fallback: float) -> float:
        """Convert numeric-like input to float, or return fallback."""
        try:
            converted = float(value)
        except (TypeError, ValueError):
            return fallback

        if converted <= 0.0:
            return fallback

        return converted

    def on_start(self, config: dict[str, object]) -> None:
        """Log startup configuration received from the coordinator."""
        self.get_logger().info('Nodo1 ready with config: %s' % config)

    def on_stop(self) -> None:
        """Log the stop event triggered by the coordinator."""
        self.get_logger().info('Nodo1 released its resources.')


def main(args=None) -> None:
    """Run worker node nodo1."""
    rclpy.init(args=args)
    node = Nodo1()
    rclpy.spin(node)
    node.destroy_node()


if __name__ == '__main__':
    main()
