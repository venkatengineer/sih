"""
Strongly typed Task data model and state machine for warehouse transport jobs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Tuple, Optional, Dict, Any, Union

from edge_robot.core.enums import TaskStatus, TaskPriority
from edge_robot.tasks.bid import TaskBid


class Task:
    """
    Represents a warehouse transport job:
    Pickup (location A) -> Transport -> Dropoff (location B).
    """

    def __init__(
        self,
        task_id: str,
        pickup: Tuple[int, int] | Tuple[float, float],
        dropoff: Optional[Tuple[int, int] | Tuple[float, float]] = None,
        destination: Optional[Tuple[int, int] | Tuple[float, float]] = None,
        priority: int = TaskPriority.NORMAL.value,
        created_at: Optional[float] = None,
        status: TaskStatus = TaskStatus.CREATED,
        assigned_robot: Optional[str] = None,
        auction_round: int = 1,
        deadline: Optional[float] = None,
        started_at: Optional[float] = None,
        picked_up_at: Optional[float] = None,
        completed_at: Optional[float] = None,
        failed_reason: Optional[str] = None,
    ):
        self.task_id = str(task_id)
        self.pickup = (int(round(pickup[0])), int(round(pickup[1])))

        target_dropoff = dropoff if dropoff is not None else destination
        if target_dropoff is None:
            target_dropoff = pickup
        self.dropoff = (int(round(target_dropoff[0])), int(round(target_dropoff[1])))

        self.priority = int(priority)
        self.created_at = created_at if created_at is not None else time.time()
        self.status = status
        self.assigned_robot = assigned_robot
        self.auction_round = int(auction_round)
        self.deadline = deadline
        self.started_at = started_at
        self.picked_up_at = picked_up_at
        self.completed_at = completed_at
        self.failed_reason = failed_reason

    @property
    def destination(self) -> Tuple[int, int]:
        """Backward compatibility alias for dropoff."""
        return self.dropoff

    @destination.setter
    def destination(self, value: Tuple[int, int]) -> None:
        self.dropoff = (int(round(value[0])), int(round(value[1])))

    def transition_to(self, new_status: TaskStatus, reason: Optional[str] = None) -> None:
        """Advance task state machine with timestamping."""
        self.status = new_status
        now = time.time()

        if new_status == TaskStatus.IN_PROGRESS and self.started_at is None:
            self.started_at = now
        elif new_status == TaskStatus.PICKED_UP and self.picked_up_at is None:
            self.picked_up_at = now
        elif new_status == TaskStatus.COMPLETED and self.completed_at is None:
            self.completed_at = now
        elif new_status == TaskStatus.FAILED:
            self.failed_reason = reason

    def to_dict(self) -> Dict[str, Any]:
        """JSON serializable dictionary representation."""
        return {
            "task_id": self.task_id,
            "pickup": list(self.pickup),
            "dropoff": list(self.dropoff),
            "destination": list(self.dropoff),
            "priority": int(self.priority),
            "created_at": self.created_at,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "assigned_robot": self.assigned_robot,
            "auction_round": self.auction_round,
            "deadline": self.deadline,
            "started_at": self.started_at,
            "picked_up_at": self.picked_up_at,
            "completed_at": self.completed_at,
            "failed_reason": self.failed_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Create Task instance from JSON dictionary."""
        p_raw = data.get("pickup", (0, 0))
        d_raw = data.get("dropoff", data.get("destination", (0, 0)))

        pickup = (int(round(p_raw[0])), int(round(p_raw[1])))
        dropoff = (int(round(d_raw[0])), int(round(d_raw[1])))

        raw_status = data.get("status", TaskStatus.CREATED.value)
        try:
            status = TaskStatus(raw_status)
        except ValueError:
            status = TaskStatus.CREATED

        return cls(
            task_id=str(data["task_id"]),
            pickup=pickup,
            dropoff=dropoff,
            priority=int(data.get("priority", TaskPriority.NORMAL.value)),
            created_at=float(data.get("created_at", time.time())),
            status=status,
            assigned_robot=data.get("assigned_robot"),
            auction_round=int(data.get("auction_round", 1)),
            deadline=float(data["deadline"]) if data.get("deadline") is not None else None,
            started_at=float(data["started_at"]) if data.get("started_at") is not None else None,
            picked_up_at=float(data["picked_up_at"]) if data.get("picked_up_at") is not None else None,
            completed_at=float(data["completed_at"]) if data.get("completed_at") is not None else None,
            failed_reason=data.get("failed_reason"),
        )

    def __repr__(self) -> str:
        return (
            f"Task(task_id='{self.task_id}', pickup={self.pickup}, dropoff={self.dropoff}, "
            f"status={self.status}, assigned={self.assigned_robot}, round={self.auction_round})"
        )
