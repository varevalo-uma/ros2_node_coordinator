#!/usr/bin/env python3

"""Provide shared coordinator-controlled behavior for worker nodes."""

import json
from typing import Any

from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import String


class ManagedNode(Node):
    """Implement shared utilities for coordinator-managed nodes."""

    def __init__(self, node_name: str):
        """Initialize common state and ROS configuration for a worker node."""
        super().__init__(node_name)
        self.set_parameters([
            Parameter('use_sim_time', Parameter.Type.BOOL, True),
        ])
        self.status = 'stopped'
        self.last_config: dict[str, Any] = {}
        self.get_logger().info(
            'Ready to receive play/stop commands for %s.' % node_name,
        )

    def _decode_payload(self, raw_payload: str) -> dict[str, Any]:
        """Decode a JSON command payload and normalize invalid inputs."""
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            self.get_logger().warning('Invalid JSON command: %s' % raw_payload)
            return {'action': None, 'config': {'raw_payload': raw_payload}}

        if isinstance(payload, dict):
            return payload

        return {'action': None, 'config': {'payload': payload}}

    def _normalize_config(self, config: Any) -> dict[str, Any]:
        """Normalize configuration values into a dictionary."""
        if isinstance(config, dict):
            return config

        if config is None:
            return {}

        return {'value': config}

    def load_config(self, msg: String) -> dict[str, Any]:
        """Decode and store configuration received from the coordinator."""
        payload = self._decode_payload(msg.data)
        self.last_config = self._normalize_config(payload.get('config'))
        return self.last_config

    def publish_ack(self, publisher, status: str) -> None:
        """Publish the node status as a coordinator acknowledgment."""
        msg = String()
        msg.data = json.dumps({
            'node': self.get_name(),
            'status': status,
        })
        publisher.publish(msg)

    def on_start(self, config: dict[str, Any]) -> None:
        """Handle start notifications in subclasses."""
        self.get_logger().info('Started with config: %s' % config)

    def on_stop(self) -> None:
        """Handle stop notifications in subclasses."""
        self.get_logger().info('Stopped by coordinator command.')