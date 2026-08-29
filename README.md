# AMR Fleet Web Control Center (Decentralized Operator Console)

A web-based operations center for monitoring and controlling the decentralized multi-AMR warehouse fleet.

---

## 🏛️ System Architecture

```
                     ┌───────────────────────────┐
                     │    WEB CONTROL CENTER     │
                     │   (Browser @ :8000/:3000) │
                     └─────────────┬─────────────┘
                                   │
                            REST + WebSocket
                                   │
                                   ▼
                     ┌───────────────────────────┐
                     │    PYTHON CONTROL API     │
                     │     (FastAPI/AsyncIO)     │
                     └─────────────┬─────────────┘
                                   │
               ┌───────────────────┼───────────────────┐
               │                   │                   │
               ▼                   ▼                   ▼
        [TaskManager]        [RobotAgents]       [GodotBridge]
         P2P Auctions         4 Edge AMRs         Digital Twin
               │                   │                   │
               └──────── P2P UDP ──┴───────────────────┘
```

* **Web UI**: Industrial operator dashboard.
* **Control API**: Python REST API and WebSocket live event broadcaster (`/ws`).
* **Source of Truth**: Decentralized `RobotAgent` and `TaskManager` running on edge nodes.
* **Digital Twin**: Godot 4.7 warehouse simulation.

---

## 🚀 Quick Startup

### 1. Launch Control Center (Web UI + API)
```bash
/data/sih/control_center/start.sh
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 📋 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/fleet` | Returns all 4 AMRs, their states, battery, and system metadata |
| `GET` | `/api/robots` | Returns list of all active robot nodes |
| `GET` | `/api/robots/{id}` | Telemetry and historical task log for a specific AMR |
| `POST` | `/api/robots/{id}/pause` | Safety pause command for an AMR |
| `POST` | `/api/robots/{id}/resume` | Resumes autonomous operation of an AMR |
| `GET` | `/api/tasks` | Returns all warehouse transport tasks |
| `POST` | `/api/tasks` | Creates a task and triggers decentralized P2P auction across fleet |
| `GET` | `/api/tasks/{id}` | Real-time status, bid matrix, and winner for a task |
| `POST` | `/api/tasks/{id}/cancel` | Cancels a task and releases assigned robot |
| `GET` | `/api/events` | Recent event log ring buffer |
| `GET` | `/api/system` | System metadata (P2P mesh state, central server: None) |
| `WS` | `/ws` | Real-time WebSocket event stream |

---

## ⚡ Task Creation & Autonomous P2P Auction Workflow

1. Operator opens `http://localhost:8000` -> **Create Task**.
2. Selects **Pickup Station** (`A3`), **Dropoff Station** (`D8`), and **Priority** (`HIGH`).
3. Clicks `🚀 BROADCAST & AUCTION TASK`.
4. The system submits the task into the P2P network:
   - AMRs independently calculate multi-factor cost bids based on distance, congestion, battery, and workload.
   - Bids are broadcasted over P2P UDP.
   - All AMRs reach deterministic consensus on the winner without a central coordinator.
   - The winner accepts and begins autonomous execution.
5. All live bids and status transitions are rendered in real time on the web dashboard and visualized inside the Godot 3D digital twin.
