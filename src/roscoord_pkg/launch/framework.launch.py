#!/usr/bin/env python3

"""Launch the coordinator communication example stack."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    """Build the launch description for the example framework."""
    return LaunchDescription([
        # Optional local nodes for ROS-only testing.
        # Node(
        #     package='roscoord_pkg',
        #     executable='clock_bridge',
        #     name='clock_bridge',
        #     output='screen',
        # ),
        # Node(
        #     package='roscoord_pkg',
        #     executable='nodo1',
        #     name='nodo1',
        #     output='screen',
        # ),
        # Node(
        #     package='roscoord_pkg',
        #     executable='nodo2',
        #     name='nodo2',
        #     output='screen',
        # ),
        # Coordinator controlling Coppelia Burger and the example Python nodes.
        Node(
            package='roscoord_pkg',
            executable='coordinator',
            name='coordinator',
            output='screen',
            parameters=[
                {
                    'node_names': ['Burger', 'nodo1', 'nodo2'],
                    'example_config': '{"mission":"demo","owner":"coordinator","Burger_play_sec":0.10,"Burger_stop_sec":0.10,"nodo1_play_sec":0.25,"nodo1_stop_sec":0.10,"nodo2_play_sec":0.20,"nodo2_stop_sec":0.10}'
                }
            ],
        ),
    ])