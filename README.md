# Edge Robot Agent — Decentralized Autonomous Mobile Robot (AMR) Module

Pure Python Edge Robot Agent module engineered to run as an independent onboard compute node on Autonomous Mobile Robots (AMR), Raspberry Pi, or NVIDIA Jetson hardware.

Each running process represents **exactly one independent robot** with zero central path planning or fleet orchestration bottlenecks.

---

## System Architecture

```
                 EXTERNAL FRONTEND SIMULATION
                              │
                    WebSocket │ (ws://localhost:8001 / 8002 / 8003)
                              ▼
                      ┌───────────────┐
                      │  RobotAgent   │ (AMR-01)
                      └───────┬───────┘
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
              Planner     Coordinator    Safety
                 │            │            │
                 └────────────┼────────────┘
                              │
                        Decision/Command
                              │
                    WebSocket │ (STATE, PATH, COMMAND, DECISION_EVENT)
                              ▼
                       FRONTEND VISUAL ROBOT

                      P2P UDP BROADCAST (Local)
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
             AMR-02 Edge Node   AMR-03 Edge Node
              (UDP Port 5002)    (UDP Port 5003)
```

---

## Key Architectural Principles

1. **One Python Process = One Robot**: No shared memory, no central `FleetController`.
2. **Frontend Simulation Connection**: Each robot exposes an independent WebSocket server (`ws://localhost:8001`, `8002`, `8003`).
3. **P2P Decentralized Coordination**: Asynchronous UDP state broadcasting, intent lookahead, deterministic priority calculation, head-on swap/intersection conflict resolution, and Wait-For Graph (WFG) deadlock detection.
4. **Closed-Loop Control**:
   - Python sends `COMMAND` (`MOVE`, `WAIT`, `YIELD`, `REROUTE`, `STOP`) with target waypoints.
   - Frontend animates visual robot and sends `POSITION` updates back.
   - Python updates local state and plans the next step.
5. **Hardware Abstraction Layer (HAL)**: Hardware-agnostic core (`MotorInterface`, `LidarInterface`, `CameraInterface`, `LocalizationInterface`), switchable between mock simulation and physical GPIO/serial drivers without modifying agent logic.
6. **Zero Heavy Framework Dependencies**: Standard library Python 3.10+ (pure `asyncio`, `dataclasses`, `sockets`, `math`, `heapq`).

---

## Package Structure

```
edge_robot/
├── __init__.py           # Package exports (RobotAgent, RobotState, FrontendGateway, etc.)
├── __main__.py           # python -m edge_robot entry point
├── main.py               # CLI lifecycle runner
├── config.py             # RobotConfig definitions & loader
├── core/
│   ├── robot.py          # RobotAgent continuous control loop & hooks
│   ├── state.py          # Strongly typed RobotState model & serialization
│   └── enums.py          # RobotStatus, RobotIntent, ConflictAction, etc.
├── gateway/
│   ├── __init__.py       # Gateway exports
│   ├── frontend_protocol.py # WebSocket protocol schemas (COMMAND, STATE, PATH, DECISION_EVENT)
│   ├── websocket_server.py  # Zero-dependency RFC 6455 Asyncio WebSocket Server
│   └── session.py        # FrontendGateway session manager
├── hardware/
│   ├── interfaces.py     # CameraInterface, LidarInterface, MotorInterface, LocalizationInterface
│   ├── camera.py         # Camera hardware module
│   ├── lidar.py          # Lidar hardware module
│   ├── motors.py         # Motor controller module
│   └── mock_hardware.py  # Mock implementations for testing & simulation
├── sensors/
│   ├── interfaces.py     # SensorObservation & SensorInterface
│   └── mock.py           # MockSensor with obstacle injection
├── localization/
│   ├── interface.py      # LocalizerInterface
│   └── localizer.py      # Kinematic dead-reckoning localizer
├── world/
│   ├── obstacle.py       # Local dynamic/static obstacle tracker with TTL
│   ├── map.py            # LocalWorldModel & occupancy grid
│   └── robot_view.py     # Read-only world view query helper
├── planning/
│   ├── astar.py          # Pure Python deterministic A* path planner
│   ├── route.py          # Route validation & waypoint utilities
│   └── planner.py        # PathPlanner & dynamic replanner
├── coordination/
│   ├── priority.py       # Deterministic priority calculation formula
│   ├── conflict.py       # ConflictDetector & ConflictResolver (PROCEED / YIELD / REROUTE)
│   ├── reservation.py    # Time-to-live (TTL) intersection reservations
│   └── deadlock.py       # Wait-For Graph (WFG) cycle detection & breaker
├── communication/
│   ├── protocol.py       # P2P NetworkMessage schemas (ROBOT_STATE, OBSTACLE, etc.)
│   ├── peer.py           # PeerTable with heartbeat timeout tracking
│   ├── network.py        # Asyncio UDP network transport
│   └── discovery.py      # Peer discovery helper
├── tasks/
│   ├── task.py           # Task & TaskBid data models
│   └── task_manager.py   # TaskManager & decentralized auction evaluator
├── learning/
│   └── experience.py     # ExperienceStore & statistical edge cost estimator
└── safety/
    └── safety_controller.py # Deterministic emergency safety shield
```

---

## WebSocket Frontend Protocol

### Inbound (Frontend $\to$ Python Edge Agent)

* **`INIT`**: Reinitialize robot starting pose and goal.
  ```json
  {"type": "INIT", "robot_id": "AMR-01", "position": [1, 2], "goal": [18, 2]}
  ```
* **`WORLD_UPDATE`**: Inject visual obstacles and peer observations.
  ```json
  {"type": "WORLD_UPDATE", "obstacles": [{"id": "OBS-01", "position": [8, 2], "radius": 0.5}], "robots": [{"robot_id": "AMR-02", "position": [12, 2]}]}
  ```
* **`GOAL_UPDATE`**: Set a new target destination.
  ```json
  {"type": "GOAL_UPDATE", "goal": [18, 2]}
  ```
* **`POSITION`**: Closed-loop visual position feedback from frontend animation.
  ```json
  {"type": "POSITION", "position": [2.0, 2.0], "heading": 0.0}
  ```
* **`TASK`**: Assign a transport task.
  ```json
  {"type": "TASK", "task_id": "T-01", "pickup": [4, 2], "destination": [18, 2], "priority": 50}
  ```
* **`RESET`**: Reset robot to default state.
  ```json
  {"type": "RESET"}
  ```

### Outbound (Python Edge Agent $\to$ Frontend)

* **`STATE`**: Real-time robot status, position, velocity, and battery.
  ```json
  {"type": "STATE", "robot_id": "AMR-01", "position": [5.0, 2.0], "velocity": 1.0, "heading": 0.0, "status": "MOVING", "battery": 92.0}
  ```
* **`PATH`**: Planned A* waypoint coordinates for visual path drawing.
  ```json
  {"type": "PATH", "robot_id": "AMR-01", "path": [[5, 2], [6, 2], [7, 2], [8, 2]]}
  ```
* **`COMMAND`**: Movement actions for frontend execution.
  ```json
  {"type": "COMMAND", "robot_id": "AMR-01", "action": "MOVE", "target": [6.0, 2.0], "speed": 1.0}
  ```
* **`DECISION_EVENT`**: Explainable reasoning behind decentralized decisions.
  ```json
  {"type": "DECISION_EVENT", "robot_id": "AMR-02", "event": "YIELD", "reason": "Lower priority (50.0 vs 70.0) -> Yield to AMR-01", "peer": "AMR-01", "node": [8, 2]}
  ```

---

## Running Multi-Robot Nodes with Frontend Gateway

Start each robot in its own terminal or background process:

**Terminal 1 (AMR-01):**
```bash
python3 -m edge_robot --robot-id AMR-01 --port 5001 --frontend-port 8001
```

**Terminal 2 (AMR-02):**
```bash
python3 -m edge_robot --robot-id AMR-02 --port 5002 --frontend-port 8002
```

**Terminal 3 (AMR-03):**
```bash
python3 -m edge_robot --robot-id AMR-03 --port 5003 --frontend-port 8003
```

---

## Running the Test Suite

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
