"""
Robot Intent Representation for Predictive Decentralized Coordination.
Encapsulates current state, planned future path cells, ETAs, and priority.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import List, Tuple, Optional, Dict, Any


@dataclass
class RobotIntentData:
    """
    Rich intent broadcasted by an AMR to its peers.
    Enables predictive spatio-temporal conflict detection across the P2P mesh.
    """
    robot_id: str
    position: Tuple[float, float]
    velocity: Tuple[float, float] = (0.0, 0.0)
    current_cell: Tuple[int, int] = (0, 0)
    path: List[Tuple[int, int]] = field(default_factory=list)
    next_waypoint: Optional[Tuple[int, int]] = None
    eta: float = 0.0
    priority: float = 50.0
    task_id: Optional[str] = None
    status: str = "IDLE"
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "position": [round(self.position[0], 2), round(self.position[1], 2)],
            "velocity": [round(self.velocity[0], 2), round(self.velocity[1], 2)],
            "current_cell": list(self.current_cell),
            "path": [list(p) for p in self.path],
            "next_waypoint": list(self.next_waypoint) if self.next_waypoint else None,
            "eta": round(self.eta, 2),
            "priority": round(self.priority, 2),
            "task_id": self.task_id,
            "status": self.status,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RobotIntentData:
        pos = data.get("position", [0.0, 0.0])
        vel = data.get("velocity", [0.0, 0.0])
        cell = data.get("current_cell", [int(round(pos[0])), int(round(pos[1]))])
        path_raw = data.get("path", [])
        path = [tuple(p) for p in path_raw]
        next_wp = tuple(data["next_waypoint"]) if data.get("next_waypoint") else None

        return cls(
            robot_id=str(data.get("robot_id", "")),
            position=(float(pos[0]), float(pos[1])),
            velocity=(float(vel[0]), float(vel[1])),
            current_cell=(int(cell[0]), int(cell[1])),
            path=path,
            next_waypoint=next_wp,
            eta=float(data.get("eta", 0.0)),
            priority=float(data.get("priority", 50.0)),
            task_id=data.get("task_id"),
            status=str(data.get("status", "IDLE")),
            timestamp=float(data.get("timestamp", time.time())),
            sequence=int(data.get("sequence", 0)),
        )
