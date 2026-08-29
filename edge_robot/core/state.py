"""
Strongly typed RobotState for independent Edge Robot Agent.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import math
import time
from typing import List, Optional, Tuple, Dict, Any

from edge_robot.core.enums import RobotStatus, RobotIntent


@dataclass
class RobotState:
    """
    Complete state representation of an autonomous mobile robot.
    Purely local to this robot instance, serializable for P2P communication.
    """
    robot_id: str
    position: Tuple[float, float] = (0.0, 0.0)
    heading: float = 0.0  # Degrees [0.0, 360.0)
    velocity: float = 0.0  # m/s
    battery: float = 100.0  # Percentage 0.0 - 100.0
    status: RobotStatus = RobotStatus.IDLE
    current_task: Optional[str] = None
    goal: Optional[Tuple[float, float]] = None
    current_path: List[Tuple[int, int]] = field(default_factory=list)
    next_node: Optional[Tuple[int, int]] = None
    intent: RobotIntent = RobotIntent.IDLE
    priority: float = 50.0
    timestamp: float = field(default_factory=time.time)
    waiting_time: float = 0.0
    is_safe: bool = True

    def distance_to(self, target: Tuple[float, float]) -> float:
        """Calculate Euclidean distance to a target position."""
        return math.hypot(self.position[0] - target[0], self.position[1] - target[1])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to standard dictionary for JSON / P2P transmission."""
        return {
            "robot_id": self.robot_id,
            "position": list(self.position),
            "heading": round(self.heading, 2),
            "velocity": round(self.velocity, 2),
            "battery": round(self.battery, 1),
            "status": self.status.value if isinstance(self.status, RobotStatus) else str(self.status),
            "current_task": self.current_task,
            "goal": list(self.goal) if self.goal else None,
            "current_path": [list(p) for p in self.current_path],
            "next_node": list(self.next_node) if self.next_node else None,
            "intent": self.intent.value if isinstance(self.intent, RobotIntent) else str(self.intent),
            "priority": round(self.priority, 2),
            "timestamp": self.timestamp,
            "waiting_time": round(self.waiting_time, 2),
            "is_safe": self.is_safe,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RobotState:
        """Construct RobotState from dictionary."""
        pos = tuple(data.get("position", (0.0, 0.0)))
        goal = tuple(data["goal"]) if data.get("goal") is not None else None
        next_n = tuple(data["next_node"]) if data.get("next_node") is not None else None
        path = [tuple(p) for p in data.get("current_path", [])]

        return cls(
            robot_id=data.get("robot_id", "UNKNOWN"),
            position=(float(pos[0]), float(pos[1])),
            heading=float(data.get("heading", 0.0)),
            velocity=float(data.get("velocity", 0.0)),
            battery=float(data.get("battery", 100.0)),
            status=RobotStatus(data.get("status", RobotStatus.IDLE.value)),
            current_task=data.get("current_task"),
            goal=(float(goal[0]), float(goal[1])) if goal else None,
            current_path=path,
            next_node=(int(next_n[0]), int(next_n[1])) if next_n else None,
            intent=RobotIntent(data.get("intent", RobotIntent.IDLE.value)),
            priority=float(data.get("priority", 50.0)),
            timestamp=float(data.get("timestamp", time.time())),
            waiting_time=float(data.get("waiting_time", 0.0)),
            is_safe=bool(data.get("is_safe", True)),
        )
