# roscoord_pkg Quick Reference

This is a compact developer cheat sheet for the coordinator-worker communication framework.

## 1) Main components

- Coordinator: orchestrates worker lifecycle using a generic state machine.
- ManagedNode: reusable base class for worker nodes.
- Nodo1 / Nodo2: example workers with play/stop callbacks and ack publishing.
- Burger: optional simulator-controlled worker managed by the coordinator in the Coppelia launch.

## 2) Communication topics

Per worker name (for example, nodo1):

- Input commands:
  - /nodo1/play
  - /nodo1/stop
- Output acknowledgments:
  - /nodo1/play_ack
  - /nodo1/stop_ack

  For the simulator worker:

  - /Burger/play
  - /Burger/stop
  - /Burger/play_ack
  - /Burger/stop_ack

Payload format (String JSON):

- Command payload fields:
  - source: coordinator node name
  - config: arbitrary configuration object
- Ack payload fields:
  - node: worker name
  - status: playing or stopped

## 3) Coordinator state machine

States:

- idle
- starting
- running
- stopping
- done

Events:

- start
- all_play_acked
- stop_requested
- all_stop_acked

Default transition chain:

- idle -> starting -> running -> stopping -> done

Extra supported transition:

- starting -> stopping when event stop_requested is triggered early

## 4) Key Coordinator methods

- _configure_state_machine(): registers transitions and enter-state actions.
- _transition(event): triggers events with transition logging.
- _on_enter_starting(): broadcasts play to all workers.
- _on_enter_running(): records run start time.
- _on_enter_stopping(): broadcasts stop to all workers.
- _on_enter_done(): finalizes execution and shuts down.
- _handle_play_ack(...): validates play ack and may trigger all_play_acked.
- _handle_stop_ack(...): validates stop ack and may trigger all_stop_acked.
- _tick(): drives auto-start and runtime-based stop request.

## 5) Key ManagedNode methods

- load_config(msg): parses and normalizes config from incoming JSON.
- publish_ack(publisher, status): sends standard ack payload.
- on_start(config): override hook for start behavior.
- on_stop(): override hook for stop behavior.

## 6) Worker node callback pattern

In each worker:

- cb_play(msg):
  - config = load_config(msg)
  - sleep briefly to simulate play work
  - status = playing
  - on_start(config)
  - publish play ack

- cb_stop(msg):
  - load_config(msg)
  - sleep briefly to simulate stop work
  - status = stopped
  - on_stop()
  - publish stop ack

Simulation tuning keys in config payload:

- nodo1_play_sec (default 0.25)
- Burger_play_sec (default 0.10)
- Burger_stop_sec (default 0.10)
- nodo1_stop_sec (default 0.10)
- nodo2_play_sec (default 0.20)
- nodo2_stop_sec (default 0.10)

## 7) Runtime parameters (Coordinator)

- node_names (string array): list of worker names.
- run_duration_sec (double): running duration before stop request.
- auto_start (bool): start automatically from idle.
- example_config (JSON string): payload sent to workers.

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

## 8) Build and launch

From workspace root:

```bash
colcon build --packages-select roscoord_pkg
source install/setup.bash
ros2 launch roscoord_pkg framework.launch.py
```

## 9) Add a new worker quickly

1. Create nodo3.py inheriting from ManagedNode.
2. Subscribe to /nodo3/play and /nodo3/stop.
3. Publish /nodo3/play_ack and /nodo3/stop_ack.
4. Add cb_play and cb_stop.
5. Register console script in setup.py.
6. Add node action in launch/framework.launch.py.
7. Add nodo3 to coordinator node_names.

## 10) Simulation time notes

- Coordinator and ManagedNode enable use_sim_time programmatically.
- clock_bridge.py bridges /clock_coppelia to /clock and is started by the framework launch file.

## 11) Coppelia robot script

- Unified control topics:
  - /Burger/play
  - /Burger/stop
  - /Burger/play_ack
  - /Burger/stop_ack
- Add Burger to coordinator node_names if the simulator script is part of the managed lifecycle.
