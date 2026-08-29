"""
TaskBid data model submitted by independent AMRs during decentralized auctions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, Any


@dataclass
class TaskBid:
    """
    A bid submitted by an AMR representing its estimated cost to execute a task.
    """
    task_id: str
    robot_id: str
    cost: float
    auction_round: int = 1
    estimated_time: float = 0.0
    distance: float = 0.0
    battery: float = 100.0
    congestion: float = 0.0
    workload: int = 0
    is_valid: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to serializable dictionary for P2P transmission."""
        return {
            "task_id": self.task_id,
            "robot_id": self.robot_id,
            "cost": round(self.cost, 2) if self.cost != float("inf") else 999999.0,
            "auction_round": self.auction_round,
            "estimated_time": round(self.estimated_time, 2),
            "distance": round(self.distance, 2),
            "battery": round(self.battery, 1),
            "congestion": round(self.congestion, 2),
            "workload": self.workload,
            "is_valid": self.is_valid,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskBid:
        """Create TaskBid from dictionary."""
        cost = float(data.get("cost", 999999.0))
        if cost >= 999999.0:
            cost = float("inf")

        return cls(
            task_id=str(data["task_id"]),
            robot_id=str(data["robot_id"]),
            cost=cost,
            auction_round=int(data.get("auction_round", 1)),
            estimated_time=float(data.get("estimated_time", 0.0)),
            distance=float(data.get("distance", 0.0)),
            battery=float(data.get("battery", 100.0)),
            congestion=float(data.get("congestion", 0.0)),
            workload=int(data.get("workload", 0)),
            is_valid=bool(data.get("is_valid", True)),
            timestamp=float(data.get("timestamp", time.time())),
        )
