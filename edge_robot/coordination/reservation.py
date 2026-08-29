"""
Intersection and Critical Zone Time-Based Reservation System.
Prevents simultaneous occupation of choke points and intersections.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, Tuple, Optional, Any, List


@dataclass
class Reservation:
    """Temporary reservation claim on a critical intersection or grid cell."""
    reservation_id: str
    robot_id: str
    node: Tuple[int, int]
    priority: float
    enter_time: float = field(default_factory=time.time)
    exit_time: float = field(default_factory=lambda: time.time() + 3.0)
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 3.0

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        t = current_time or time.time()
        return (t - self.created_at) > self.ttl_seconds or t > self.exit_time

    def overlaps(self, enter_t: float, exit_t: float) -> bool:
        """Returns True if the time interval [enter_t, exit_t] overlaps with this reservation."""
        return not (exit_t <= self.enter_time or enter_t >= self.exit_time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reservation_id": self.reservation_id,
            "robot_id": self.robot_id,
            "node": list(self.node),
            "priority": self.priority,
            "enter_time": self.enter_time,
            "exit_time": self.exit_time,
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Reservation:
        return cls(
            reservation_id=data.get("reservation_id", "res-0"),
            robot_id=data.get("robot_id", ""),
            node=tuple(data.get("node", (0, 0))),
            priority=float(data.get("priority", 50.0)),
            enter_time=float(data.get("enter_time", time.time())),
            exit_time=float(data.get("exit_time", time.time() + 3.0)),
            created_at=float(data.get("created_at", time.time())),
            ttl_seconds=float(data.get("ttl_seconds", 3.0)),
        )


class ReservationManager:
    """Manages active reservations for the local agent and peers."""

    def __init__(self, default_ttl: float = 3.0):
        self.default_ttl = default_ttl
        self.active_reservations: Dict[Tuple[int, int], List[Reservation]] = {}

    def create_reservation(
        self,
        robot_id: str,
        node: Tuple[int, int],
        priority: float,
        duration_s: float = 2.5,
    ) -> Reservation:
        now = time.time()
        res = Reservation(
            reservation_id=f"res-{robot_id}-{node[0]}_{node[1]}-{int(now*1000)}",
            robot_id=robot_id,
            node=node,
            priority=priority,
            enter_time=now,
            exit_time=now + duration_s,
            created_at=now,
            ttl_seconds=max(self.default_ttl, duration_s + 1.0),
        )
        if node not in self.active_reservations:
            self.active_reservations[node] = []
        self.active_reservations[node].append(res)
        return res

    def register_peer_reservation(self, res: Reservation) -> None:
        """Register or update a peer's reservation."""
        self.clean_expired()
        if res.node not in self.active_reservations:
            self.active_reservations[res.node] = []

        # Check if already present from same robot
        existing_list = self.active_reservations[res.node]
        for idx, r in enumerate(existing_list):
            if r.robot_id == res.robot_id:
                existing_list[idx] = res
                return

        existing_list.append(res)

    def release_reservation(self, node: Tuple[int, int], robot_id: str) -> None:
        if node in self.active_reservations:
            self.active_reservations[node] = [
                r for r in self.active_reservations[node]
                if r.robot_id != robot_id
            ]
            if not self.active_reservations[node]:
                del self.active_reservations[node]

    def release_all_for_robot(self, robot_id: str) -> List[Tuple[int, int]]:
        """Release all reservations held by a specific robot (e.g. when peer goes offline)."""
        released_nodes: List[Tuple[int, int]] = []
        for node in list(self.active_reservations.keys()):
            self.active_reservations[node] = [
                r for r in self.active_reservations[node]
                if r.robot_id != robot_id
            ]
            if not self.active_reservations[node]:
                del self.active_reservations[node]
                released_nodes.append(node)
        return released_nodes

    def is_node_reserved_by_other(
        self,
        node: Tuple[int, int],
        self_id: str,
        enter_time: Optional[float] = None,
        exit_time: Optional[float] = None,
    ) -> Optional[Reservation]:
        """Check if node is currently reserved by a peer with overlapping interval."""
        self.clean_expired()
        res_list = self.active_reservations.get(node, [])
        now = time.time()
        check_enter = enter_time or now
        check_exit = exit_time or (now + 2.0)

        for res in res_list:
            if res.robot_id != self_id and not res.is_expired():
                if res.overlaps(check_enter, check_exit):
                    return res
        return None

    def clean_expired(self) -> None:
        now = time.time()
        for node in list(self.active_reservations.keys()):
            self.active_reservations[node] = [
                r for r in self.active_reservations[node]
                if not r.is_expired(now)
            ]
            if not self.active_reservations[node]:
                del self.active_reservations[node]
