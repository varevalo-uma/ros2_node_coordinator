# roscoord_pkg Framework Guide

This package is a ROS 2 communication framework example built around a coordinator and worker nodes.
It is intended to be simple, extensible, and easy to share with teammates.

## What this framework does

- The coordinator controls worker activation with dedicated topics:
  - `/<node_name>/play`
  - `/<node_name>/stop`
- Each worker responds with acknowledgments:
  - `/<node_name>/play_ack`
  - `/<node_name>/stop_ack`
- Worker callbacks simulate short blocking work with `sleep` before acknowledging.
- The coordinator runs a generic event-driven state machine to manage the lifecycle.
- Simulation time is enabled programmatically (`use_sim_time=True`) in framework nodes.

## Package layout

- `roscoord_pkg/coordinator.py`: coordinator logic and generic state machine.
- `roscoord_pkg/managed_node.py`: base class used by worker nodes.
- `roscoord_pkg/nodo1.py`: example worker implementation #1.
- `roscoord_pkg/nodo2.py`: example worker implementation #2.
- `roscoord_pkg/clock_bridge.py`: bridge from `/clock_coppelia` to `/clock`.
- `launch/framework.launch.py`: launch file for coordinator + workers.

The default launch file is Coppelia-ready: it starts `Burger`, `nodo1`, `nodo2`, the coordinator, and the clock bridge.

## Core classes and responsibilities

### `NodeState` (in `coordinator.py`)

Simple dataclass that stores per-node runtime status:
- `name`
- `status`

### `StateMachine` (in `coordinator.py`)

Generic finite state machine with event-driven transitions.

Main methods:
- `add_transition(source_state, event, target_state, action=None)`
  - Registers one transition rule.
- `trigger(event) -> bool`
  - Executes transition for `(current_state, event)` if it exists.
  - Runs transition action (if defined).
  - Returns `True` if transition happened, otherwise `False`.

### `Coordinator` (in `coordinator.py`)

Main orchestrator node.

Main responsibilities:
- Declares and reads runtime parameters.
- Creates play/stop publishers and ack subscribers for each worker.
- Owns a `StateMachine` instance to control execution flow.
- Starts workers, waits for acks, tracks run time, and requests stop.

Important methods:
- `_configure_state_machine()`
  - Defines lifecycle transitions.
- `_transition(event)`
  - Wrapper around state-machine trigger with transition logs.
- `_on_enter_starting()`
  - Action on entering `starting`; publishes `play`.
- `_on_enter_running()`
  - Action on entering `running`; stores start timestamp.
- `_on_enter_stopping()`
  - Action on entering `stopping`; publishes `stop`.
- `_on_enter_done()`
  - Action on entering `done`; stops timer and shuts down.
- `_make_play_ack_callback(name)` / `_make_stop_ack_callback(name)`
  - Binds ack callbacks per node.
- `_handle_play_ack(...)` / `_handle_stop_ack(...)`
  - Validates ack content and triggers state transitions when all nodes match target status.
- `_tick()`
  - Drives automatic behavior (`auto_start` and runtime-based stop request).

## Coordinator state machine

Default states:
- `idle`
- `starting`
- `running`
- `stopping`
- `done`

Default events:
- `start`
- `all_play_acked`
- `stop_requested`
- `all_stop_acked`

Default transitions:
- `idle --(start)--> starting`
- `starting --(all_play_acked)--> running`
- `starting --(stop_requested)--> stopping`
- `running --(stop_requested)--> stopping`
- `stopping --(all_stop_acked)--> done`

## Worker base class

### `ManagedNode` (in `managed_node.py`)

Base class that reduces duplicate code in worker nodes.

Main fields:
- `status`: current worker status (`stopped`, `playing`, etc.).
- `last_config`: last decoded config sent by the coordinator.

Main methods:
- `load_config(msg)`
  - Parses JSON payload and stores normalized `config` in `last_config`.
- `publish_ack(publisher, status)`
  - Publishes standardized ack payload (`node`, `status`).
- `_decode_payload(raw_payload)`
  - Decodes JSON command payloads with fallback behavior for invalid data.
- `_normalize_config(config)`
  - Normalizes non-dictionary config values into dictionaries.
- `on_start(config)`
  - Extension hook for worker start logic.
- `on_stop()`
  - Extension hook for worker stop logic.

## Example workers

### `Nodo1` and `Nodo2`

Both nodes follow the same pattern:
- Subscribe to:
  - `/nodoX/play`
  - `/nodoX/stop`
- Publish to:
  - `/nodoX/play_ack`
  - `/nodoX/stop_ack`

Main callbacks:
- `cb_play(msg)`
  - Loads config, sleeps for a short configurable duration, sets `status='playing'`, calls `on_start`, publishes play ack.
- `cb_stop(msg)`
  - Sleeps for a short configurable duration, sets `status='stopped'`, calls `on_stop`, publishes stop ack.

Worker simulation details:
- `Burger` uses `Burger_play_sec` for play work duration and `Burger_stop_sec` for stop work duration.
- `Nodo1` uses `nodo1_play_sec` for play work duration and `nodo1_stop_sec` for stop work duration.
- `Nodo2` uses `nodo2_play_sec` for play work duration and `nodo2_stop_sec` for stop work duration.
- Defaults are short so callbacks remain easy to follow and quick to extend.

## Parameters

`Coordinator` parameters:
- `node_names` (`string[]`, default `['nodo1', 'nodo2']`)
  - Worker node names used to generate topics.
- `run_duration_sec` (`double`, default `5.0`)
  - Duration in `running` before stop is requested.
- `auto_start` (`bool`, default `True`)
  - If true, state machine triggers `start` automatically from `idle`.
- `example_config` (`string` with JSON)
  - Config payload sent to workers in play/stop messages.
  - Can include optional worker simulation tuning keys: `Burger_play_sec`, `Burger_stop_sec`, `nodo1_play_sec`, `nodo1_stop_sec`, `nodo2_play_sec`, `nodo2_stop_sec`.

Example `example_config` value:

```json
{
  "mission": "demo",
  "owner": "coordinator",
  "Burger_play_sec": 0.10,
  "Burger_stop_sec": 0.10,
  "nodo1_play_sec": 0.25,
  "nodo1_stop_sec": 0.10,
  "nodo2_play_sec": 0.20,
  "nodo2_stop_sec": 0.10
}
```

You can pass that JSON string through the coordinator `example_config` parameter when launching or when extending the coordinator for custom experiments.

## How to run

From your ROS 2 workspace root:

```bash
colcon build --packages-select roscoord_pkg
source install/setup.bash
ros2 launch roscoord_pkg framework.launch.py
```

You should see:
- Coordinator transitions across lifecycle states.
- `nodo1` and `nodo2` receiving play/stop and sending acknowledgments.

## How to extend the framework

### Add a new worker node

1. Create `roscoord_pkg/nodo3.py` inheriting from `ManagedNode`.
2. Add subscriptions to `/nodo3/play` and `/nodo3/stop`.
3. Add publishers for `/nodo3/play_ack` and `/nodo3/stop_ack`.
4. Implement `cb_play`, `cb_stop`, and optionally override `on_start` / `on_stop`.
5. Add a console script entry in `setup.py`.
6. Include the node in `launch/framework.launch.py`.
7. Add `'nodo3'` to coordinator `node_names` parameter.

### Add custom coordinator states

1. Add new transitions in `_configure_state_machine()`.
2. Add corresponding `_on_enter_<state>()` action methods.
3. Trigger events from callbacks or `_tick()` as needed.

## Simulation time and Coppelia integration

- `Coordinator` and `ManagedNode` set `use_sim_time=True` programmatically.
- `clock_bridge.py` can be used to bridge:
  - input: `/clock_coppelia` (`builtin_interfaces/Time`)
  - output: `/clock` (`rosgraph_msgs/Clock`)
- If you run the Coppelia script in [coppelia/burger_framework.lua](../coppelia/burger_framework.lua), the control topics are:
  - `/Burger/play`
  - `/Burger/stop`
  - `/Burger/play_ack`
  - `/Burger/stop_ack`
- To keep the coordinator in sync with the simulator, include `Burger` in `node_names` when you want the coordinator to manage the robot script.

The launch file starts `clock_bridge` together with the coordinator and example workers so the framework can consume the simulation clock if Coppelia is running.

## Troubleshooting

- Nodes never leave `starting`:
  - Verify each worker publishes `play_ack` with `status='playing'`.
  - Verify topic names include the exact node name from `node_names`.
- Nodes never leave `stopping`:
  - Verify each worker publishes `stop_ack` with `status='stopped'`.
- No simulated time:
  - Verify `/clock` exists and is being published.
  - If using Coppelia, ensure the bridge from `/clock_coppelia` to `/clock` is running.
