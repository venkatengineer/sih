"""
Robot Bridge - Translates between Web Control Center APIs and the decentralized Python AMR fleet.
Consumes real RobotAgent / TaskManager states and broadcasts live events over WebSockets.
"""

from __future__ import annotations
import asyncio
import json
import logging
import sys
import time
from typing import Dict, List, Optional, Tuple, Any

# Ensure /data/sih/robot is in sys.path
if "/data/sih/robot" not in sys.path:
    sys.path.insert(0, "/data/sih/robot")

from edge_robot.config import RobotConfig
from edge_robot.core.robot import RobotAgent
from edge_robot.core.enums import TaskStatus, TaskPriority, RobotStatus, RobotIntent
from edge_robot.tasks.task import Task
from edge_robot.tasks.bid import TaskBid
from control_center.backend.models.api_models import (
    TaskCreateRequest,
    TaskSummary,
    RobotSummary,
    SystemStatus,
)
from control_center.backend.websocket.manager import ws_manager

logger = logging.getLogger("control_center.bridge")


class RobotFleetBridge:
    """
    Bridge connecting the Web Control Center to the decentralized Python AMR Fleet.
    Zero centralized decision making — acts as a live proxy and task originator.
    """

    def __init__(self, amr_ids: Optional[List[str]] = None):
        self.amr_ids = amr_ids or ["AMR-01", "AMR-02", "AMR-03", "AMR-04"]
        self.robots: Dict[str, RobotSummary] = {}
        self.tasks: Dict[str, TaskSummary] = {}
        self.events: List[Dict[str, Any]] = []
        self.max_events = 200

        # Embedded agents collection (if running in-process)
        self.agents: Dict[str, RobotAgent] = {}
        self.is_running = False

        # Initialize robot states
        self._init_robot_states()

    def _init_robot_states(self) -> None:
        init_positions = {
            "AMR-01": (2.0, 10.0),
            "AMR-02": (5.0, 4.0),
            "AMR-03": (20.0, 15.0),
            "AMR-04": (18.0, 2.0),
        }
        for r_id in self.amr_ids:
            pos = init_positions.get(r_id, (0.0, 0.0))
            self.robots[r_id] = RobotSummary(
                robot_id=r_id,
                status="IDLE",
                battery=100.0,
                position=pos,
                heading=0.0,
                velocity=0.0,
                is_online=True,
                last_heartbeat=time.time(),
            )

    async def start(self, spawn_embedded: bool = True) -> None:
        """Start the fleet bridge and optionally spawn embedded AMR nodes."""
        self.is_running = True
        logger.info("Starting Robot Fleet Bridge...")

        if spawn_embedded:
            await self._spawn_embedded_fleet()

        self._record_event("SYSTEM_READY", {"message": "Decentralized Control Bridge Online (4 AMRs)"})

    async def stop(self) -> None:
        """Stop all embedded agents and bridge."""
        self.is_running = False
        for agent in self.agents.values():
            try:
                await agent.stop()
            except Exception as e:
                logger.debug(f"Error stopping agent {agent.robot_id}: {e}")
        self.agents.clear()
        logger.info("Robot Fleet Bridge Stopped.")

    # =========================================================================
    # Embedded Fleet Lifecycle (Decentralized Mesh)
    # =========================================================================

    async def _spawn_embedded_fleet(self) -> None:
        """Instantiate 4 independent RobotAgents communicating over P2P UDP."""
        common_peers = [
            ("127.0.0.1", 5701),
            ("127.0.0.1", 5702),
            ("127.0.0.1", 5703),
            ("127.0.0.1", 5704),
        ]
        ports = [5701, 5702, 5703, 5704]
        positions = [(2.0, 10.0), (5.0, 4.0), (20.0, 15.0), (18.0, 2.0)]

        for i, r_id in enumerate(self.amr_ids):
            cfg = RobotConfig(
                robot_id=r_id,
                initial_position=positions[i],
                network_port=ports[i],
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
                max_speed=2.5,
            )
            agent = RobotAgent(cfg)
            self.agents[r_id] = agent

            # Attach listeners
            agent.on_state(self._on_agent_state)
            agent.on_path(lambda p, id=r_id: self._on_agent_path(id, p))
            agent.on_event(self._on_agent_decision_event)
            agent.task_manager.on_task_event(self._on_agent_task_event)

            await agent.start()
            logger.info(f"Spawned Embedded Edge Node: {r_id} (UDP={ports[i]})")

    # =========================================================================
    # Agent State & Event Listeners
    # =========================================================================

    def _on_agent_state(self, state: Any) -> None:
        """Handle periodic robot state updates."""
        r_id = state.robot_id
        if r_id in self.robots:
            r = self.robots[r_id]
            r.position = state.position
            r.heading = state.heading
            r.velocity = state.velocity
            r.battery = state.battery
            r.status = state.status.value if hasattr(state.status, "value") else str(state.status)
            r.current_task = state.current_task
            r.current_goal = state.goal
            r.last_heartbeat = time.time()
            r.is_online = True

            asyncio.create_task(ws_manager.broadcast_event("ROBOT_STATE", r.to_dict()))

    def _on_agent_path(self, robot_id: str, path: List[Tuple[int, int]]) -> None:
        """Handle updated path waypoints."""
        if robot_id in self.robots:
            self.robots[robot_id].current_path = path
            asyncio.create_task(ws_manager.broadcast_event("ROBOT_PATH", {
                "robot_id": robot_id,
                "path": [list(p) for p in path],
            }))

    def _on_agent_decision_event(self, event: Any) -> None:
        """Handle decision, conflict, and rerouting events."""
        event_dict = event.to_dict() if hasattr(event, "to_dict") else dict(event)
        self._record_event("DECISION_EVENT", event_dict)
        asyncio.create_task(ws_manager.broadcast_event("DECISION_EVENT", event_dict))

    def _on_agent_task_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Handle decentralized task allocation events (Bids, Awards, Completion, Re-auctions)."""
        t_id = payload.get("task_id", "")
        r_id = payload.get("robot_id", "")

        if t_id and t_id in self.tasks:
            task = self.tasks[t_id]

            if event_name == "TASK_BID_SUBMITTED":
                bid_data = payload.get("bid", {})
                bidder = bid_data.get("robot_id", r_id)
                task.bids[bidder] = bid_data
                self._record_event("TASK_BID", {
                    "task_id": t_id,
                    "robot_id": bidder,
                    "cost": bid_data.get("cost"),
                    "distance": bid_data.get("distance"),
                    "battery": bid_data.get("battery"),
                })

            elif event_name == "TASK_ASSIGNED":
                winner = payload.get("winner_id", "")
                task.assigned_robot = winner
                task.status = "ASSIGNED"
                if winner in task.bids:
                    task.winner_score = task.bids[winner].get("cost")

                # Update robot history
                if winner in self.robots:
                    self.robots[winner].task_history.append({
                        "task_id": t_id,
                        "status": "ASSIGNED",
                        "timestamp": time.time(),
                    })

                self._record_event("TASK_AWARD", {
                    "task_id": t_id,
                    "winner_id": winner,
                    "score": task.winner_score,
                    "round": task.auction_round,
                })

            elif event_name == "TASK_STARTED":
                task.status = "IN_PROGRESS"
                task.started_at = time.time()
                self._record_event("TASK_PROGRESS", {"task_id": t_id, "status": "IN_PROGRESS", "robot_id": r_id})

            elif event_name == "TASK_PICKED_UP":
                task.status = "PICKED_UP"
                task.picked_up_at = time.time()
                self._record_event("TASK_PROGRESS", {"task_id": t_id, "status": "PICKED_UP", "robot_id": r_id})

            elif event_name == "TASK_COMPLETED":
                task.status = "COMPLETED"
                task.completed_at = time.time()
                self._record_event("TASK_COMPLETE", {"task_id": t_id, "robot_id": r_id})

            elif event_name in ("TASK_RELEASED", "TASK_FAILED"):
                prev_robot = payload.get("previous_robot", r_id)
                reason = payload.get("reason", "ROBOT_UNAVAILABLE")
                new_round = int(payload.get("new_round", task.auction_round + 1))
                task.assigned_robot = None
                task.status = "REASSIGNING"
                task.auction_round = new_round
                task.bids.clear()

                self._record_event("TASK_RELEASE", {
                    "task_id": t_id,
                    "previous_robot": prev_robot,
                    "reason": reason,
                    "new_round": new_round,
                })

        # Broadcast event to WebSockets
        asyncio.create_task(ws_manager.broadcast_event(event_name, payload))

    # =========================================================================
    # Task Operations API
    # =========================================================================

    def submit_task(self, req: TaskCreateRequest) -> TaskSummary:
        """
        Create and broadcast task into the real decentralized P2P fleet.
        Zero central selection — fleet AMRs independently calculate bids.
        """
        t_id = req.task_id
        task_summary = TaskSummary(
            task_id=t_id,
            pickup=req.pickup,
            dropoff=req.dropoff,
            priority=req.priority,
            source_shelf=req.source_shelf,
            destination_shelf=req.destination_shelf,
            status="AUCTIONING",
            created_at=time.time(),
        )
        self.tasks[t_id] = task_summary

        self._record_event("TASK_CREATED", {
            "task_id": t_id,
            "pickup": list(req.pickup),
            "dropoff": list(req.dropoff),
            "priority": req.priority,
            "source_shelf": req.source_shelf,
            "destination_shelf": req.destination_shelf,
        })

        # Submit to first available agent to originate P2P broadcast
        if self.agents:
            primary_agent = next(iter(self.agents.values()))
            if req.source_shelf and req.destination_shelf:
                primary_agent.submit_shelf_task(
                    source_shelf_id=req.source_shelf,
                    destination_shelf_id=req.destination_shelf,
                    priority=req.priority,
                    task_id=t_id,
                )
            else:
                primary_agent.submit_task(
                    pickup=req.pickup,
                    dropoff=req.dropoff,
                    priority=req.priority,
                    task_id=t_id,
                )
            logger.info(f"Broadcast task {t_id} into P2P mesh via {primary_agent.robot_id}")

        asyncio.create_task(ws_manager.broadcast_event("TASK_AUCTIONING", task_summary.to_dict()))
        return task_summary

    def cancel_task(self, task_id: str) -> Optional[TaskSummary]:
        """Cancel a pending or active task."""
        if task_id not in self.tasks:
            return None

        task = self.tasks[task_id]
        task.status = "CANCELLED"

        if task.assigned_robot and task.assigned_robot in self.agents:
            agent = self.agents[task.assigned_robot]
            agent.task_manager.release_task(task_id, reason="CANCELLED_BY_OPERATOR")

        self._record_event("TASK_CANCELLED", {"task_id": task_id})
        asyncio.create_task(ws_manager.broadcast_event("TASK_CANCELLED", task.to_dict()))
        return task

    # =========================================================================
    # Robot Operations API
    # =========================================================================

    def pause_robot(self, robot_id: str) -> bool:
        if robot_id in self.agents:
            self.agents[robot_id].state.status = RobotStatus.WAITING
            if robot_id in self.robots:
                self.robots[robot_id].status = "WAITING"
            self._record_event("ROBOT_PAUSED", {"robot_id": robot_id})
            asyncio.create_task(ws_manager.broadcast_event("ROBOT_STATE", self.robots[robot_id].to_dict()))
            return True
        return False

    def resume_robot(self, robot_id: str) -> bool:
        if robot_id in self.agents:
            self.agents[robot_id].state.status = RobotStatus.MOVING
            if robot_id in self.robots:
                self.robots[robot_id].status = "MOVING"
            self._record_event("ROBOT_RESUMED", {"robot_id": robot_id})
            asyncio.create_task(ws_manager.broadcast_event("ROBOT_STATE", self.robots[robot_id].to_dict()))
            return True
        return False

    # =========================================================================
    # Queries & State Summaries
    # =========================================================================

    def get_fleet_summary(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.robots.values()]

    def get_robot(self, robot_id: str) -> Optional[Dict[str, Any]]:
        if robot_id in self.robots:
            return self.robots[robot_id].to_dict()
        return None

    def get_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        if task_id in self.tasks:
            return self.tasks[task_id].to_dict()
        return None

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.events[-limit:]

    def get_system_status(self) -> Dict[str, Any]:
        active_cnt = sum(1 for t in self.tasks.values() if t.status in ("ASSIGNED", "IN_PROGRESS", "PICKED_UP"))
        completed_cnt = sum(1 for t in self.tasks.values() if t.status == "COMPLETED")
        auction_cnt = sum(1 for t in self.tasks.values() if t.status in ("AUCTIONING", "REASSIGNING"))
        online_cnt = sum(1 for r in self.robots.values() if r.is_online)

        sys_status = SystemStatus(
            mode="DECENTRALIZED",
            network="P2P UDP",
            central_server="NONE",
            robots_total=len(self.robots),
            robots_online=online_cnt,
            active_tasks=active_cnt,
            completed_tasks=completed_cnt,
            auctioning_tasks=auction_cnt,
        )
        return sys_status.to_dict()

    def _record_event(self, event_type: str, data: Dict[str, Any]) -> None:
        event_entry = {
            "event": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        self.events.append(event_entry)
        if len(self.events) > self.max_events:
            self.events.pop(0)


# Global singleton instance
fleet_bridge = RobotFleetBridge()
