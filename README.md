# ROSCoord Workspace Overview

This workspace contains a ROS 2 coordination example between a coordinator node and managed nodes.

## Node Overview

- The `coordinator` node orchestrates the managed-node lifecycle through `play` and `stop` commands.
- Worker nodes (`nodo1`, `nodo2`, and optionally `Burger` in Coppelia) respond with `play_ack` and `stop_ack`.
- The main flow is: `idle -> starting -> running -> stopping -> done`.
- The active ROS package in this project is `roscoord_pkg`.

## Package Documentation

- Full package guide: [src/roscoord_pkg/README.md](src/roscoord_pkg/README.md)
- Quick reference: [src/roscoord_pkg/QUICK_REFERENCE.md](src/roscoord_pkg/QUICK_REFERENCE.md)

## Quick Start

```bash
colcon build --packages-select roscoord_pkg
source install/setup.bash
ros2 launch roscoord_pkg framework.launch.py
```
