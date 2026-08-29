"""
Data models and serialization schemas for Control Center REST & WebSocket APIs.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import time
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class TaskCreateRequest:
    task_id: str
    pickup: Tuple[int, int]
    dropoff: Tuple[int, int]
    priority: int = 5
    source_shelf: Optional[str] = None
    destination_shelf: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskCreateRequest:
        from edge_robot.world.shelf_registry import shelf_registry

        src_shelf = data.get("source_shelf") or data.get("source") or data.get("source_shelf_id")
        dest_shelf = data.get("destination_shelf") or data.get("destination_shelf_id")
        # Check if 'destination' field was provided as a string shelf ID or coordinate
        dest_field = data.get("destination")
        if isinstance(dest_field, str) and not dest_shelf:
            dest_shelf = dest_field

        p_raw = None
        d_raw = None

        if src_shelf and isinstance(src_shelf, str) and dest_shelf and isinstance(dest_shelf, str):
            try:
                p_raw, d_raw = shelf_registry.resolve_shelf_locations(src_shelf, dest_shelf)
            except Exception:
                pass

        if p_raw is None:
            p_raw = data.get("pickup", [4, 3])
        if d_raw is None:
            d_raw = data.get("dropoff", data.get("destination", [18, 8]))
            if isinstance(d_raw, str):
                s_obj = shelf_registry.get_shelf(d_raw)
                d_raw = s_obj.dropoff_position if s_obj else [18, 8]

        prio = data.get("priority", 5)
        if isinstance(prio, str):
            prio_map = {"CRITICAL": 10, "URGENT": 10, "HIGH": 5, "NORMAL": 3, "LOW": 1}
            prio = prio_map.get(prio.upper(), 5)

        t_id = data.get("task_id", f"T-{int(time.time()*1000)%100000:05d}")
        return cls(
            task_id=str(t_id),
            pickup=(int(p_raw[0]), int(p_raw[1])),
            dropoff=(int(d_raw[0]), int(d_raw[1])),
            priority=int(prio),
            source_shelf=str(src_shelf) if src_shelf else None,
            destination_shelf=str(dest_shelf) if dest_shelf else None,
        )


@dataclass
class TaskSummary:
    task_id: str
    pickup: Tuple[int, int]
    dropoff: Tuple[int, int]
    priority: int
    status: str
    source_shelf: Optional[str] = None
    destination_shelf: Optional[str] = None
    assigned_robot: Optional[str] = None
    auction_round: int = 1
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    picked_up_at: Optional[float] = None
    completed_at: Optional[float] = None
    bids: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    winner_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "pickup": list(self.pickup),
            "dropoff": list(self.dropoff),
            "source_shelf": self.source_shelf,
            "destination_shelf": self.destination_shelf,
            "source": self.source_shelf,
            "destination": self.destination_shelf,
            "priority": self.priority,
            "status": self.status,
            "assigned_robot": self.assigned_robot,
            "auction_round": self.auction_round,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "picked_up_at": self.picked_up_at,
            "completed_at": self.completed_at,
            "bids": self.bids,
            "winner_score": self.winner_score,
        }


@dataclass
class RobotSummary:
    robot_id: str
    status: str = "IDLE"
    battery: float = 100.0
    position: Tuple[float, float] = (0.0, 0.0)
    heading: float = 0.0
    velocity: float = 0.0
    current_task: Optional[str] = None
    current_goal: Optional[Tuple[int, int]] = None
    current_path: List[Tuple[int, int]] = field(default_factory=list)
    is_online: bool = True
    last_heartbeat: float = field(default_factory=time.time)
    task_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "status": self.status,
            "battery": round(self.battery, 1),
            "position": [round(self.position[0], 2), round(self.position[1], 2)],
            "heading": round(self.heading, 1),
            "velocity": round(self.velocity, 2),
            "current_task": self.current_task,
            "current_goal": list(self.current_goal) if self.current_goal else None,
            "current_path": [list(p) for p in self.current_path],
            "is_online": self.is_online,
            "last_heartbeat_ago_ms": int((time.time() - self.last_heartbeat) * 1000),
            "task_history": self.task_history[-10:],
        }


@dataclass
class SystemStatus:
    mode: str = "DECENTRALIZED"
    network: str = "P2P UDP"
    central_server: str = "NONE"
    robots_total: int = 4
    robots_online: int = 4
    active_tasks: int = 0
    completed_tasks: int = 0
    auctioning_tasks: int = 0
    system_uptime: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "network": self.network,
            "central_server": self.central_server,
            "robots_total": self.robots_total,
            "robots_online": self.robots_online,
            "active_tasks": self.active_tasks,
            "completed_tasks": self.completed_tasks,
            "auctioning_tasks": self.auctioning_tasks,
            "uptime_seconds": int(time.time() - self.system_uptime),
        }
