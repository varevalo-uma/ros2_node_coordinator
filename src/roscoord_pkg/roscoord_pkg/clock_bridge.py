#!/usr/bin/env python3

"""Bridge Coppelia simulation time into the ROS 2 /clock topic."""

# ROS2 imports
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from builtin_interfaces.msg import Time
from rosgraph_msgs.msg import Clock


class ClockBridge(Node):
    """Forward simulation time messages published by Coppelia."""

    def __init__(self):
        """Initialize subscriptions and publishers for time bridging."""
        super().__init__('clock_bridge')
        self.set_parameters([
            Parameter('use_sim_time', Parameter.Type.BOOL, True)
        ])
        # Listen to the custom clock topic emitted by the Coppelia script.
        self.sub = self.create_subscription(
            Time, 
            '/clock_coppelia', 
            self.callback, 
            10
        )
        # Re-publish in rosgraph_msgs/Clock format expected by ROS tools.
        self.pub = self.create_publisher(Clock, '/clock', 10)
        self.get_logger().info('Clock bridge started, bridging /clock_coppelia to /clock')

    def callback(self, msg: Time) -> None:
        """Convert builtin_interfaces/Time into rosgraph_msgs/Clock."""
        clock_msg = Clock()
        clock_msg.clock.sec = msg.sec
        clock_msg.clock.nanosec = msg.nanosec
        self.pub.publish(clock_msg)


def main() -> None:
    """Run the clock bridge node."""
    rclpy.init()
    node = ClockBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()