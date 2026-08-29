"""
Experience Store and Statistical Route Cost Learning.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
import time
from typing import Dict, List, Tuple, Optional, Any


@dataclass
class TripRecord:
    """Historical record of a completed navigation trip."""
    trip_id: str
    robot_id: str
    start_node: Tuple[int, int]
    goal_node: Tuple[int, int]
    path: List[Tuple[int, int]]
    distance: float
    travel_time_s: float
    waiting_time_s: float
    obstacles_encountered: int
    reroutes_count: int
    completed: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "robot_id": self.robot_id,
            "start_node": list(self.start_node),
            "goal_node": list(self.goal_node),
            "path": [list(p) for p in self.path],
            "distance": round(self.distance, 2),
            "travel_time_s": round(self.travel_time_s, 2),
            "waiting_time_s": round(self.waiting_time_s, 2),
            "obstacles_encountered": self.obstacles_encountered,
            "reroutes_count": self.reroutes_count,
            "completed": self.completed,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TripRecord:
        return cls(
            trip_id=data["trip_id"],
            robot_id=data.get("robot_id", "AMR"),
            start_node=tuple(data.get("start_node", (0, 0))),
            goal_node=tuple(data.get("goal_node", (0, 0))),
            path=[tuple(p) for p in data.get("path", [])],
            distance=float(data.get("distance", 0.0)),
            travel_time_s=float(data.get("travel_time_s", 0.0)),
            waiting_time_s=float(data.get("waiting_time_s", 0.0)),
            obstacles_encountered=int(data.get("obstacles_encountered", 0)),
            reroutes_count=int(data.get("reroutes_count", 0)),
            completed=bool(data.get("completed", True)),
            timestamp=float(data.get("timestamp", time.time())),
        )


class ExperienceStore:
    """
    Stores local and shared navigation experiences.
    Computes statistical edge costs to guide route planning towards faster, less congested paths.
    """

    def __init__(self, robot_id: str):
        self.robot_id = robot_id
        self.trips: List[TripRecord] = []
        # edge (u, v) -> list of traversal durations in seconds
        self.edge_durations: Dict[Tuple[Tuple[int, int], Tuple[int, int]], List[float]] = {}
        # node -> obstacle count history
        self.node_obstacle_counts: Dict[Tuple[int, int], int] = {}

    def record_trip(self, trip: TripRecord) -> None:
        """Record completed trip and update edge traversal statistics."""
        self.trips.append(trip)

        # Update per-edge duration estimates
        if len(trip.path) >= 2:
            step_duration = trip.travel_time_s / (len(trip.path) - 1) if (len(trip.path) > 1) else 1.0
            for i in range(len(trip.path) - 1):
                u, v = trip.path[i], trip.path[i + 1]
                edge = (u, v)
                if edge not in self.edge_durations:
                    self.edge_durations[edge] = []
                self.edge_durations[edge].append(step_duration)

    def record_obstacle_encounter(self, node: Tuple[int, int]) -> None:
        """Increment historical obstacle encounter count for this grid node."""
        self.node_obstacle_counts[node] = self.node_obstacle_counts.get(node, 0) + 1

    def get_edge_travel_time(self, u: Tuple[int, int], v: Tuple[int, int], default_time: float = 1.0) -> float:
        """Returns historical mean travel time across an edge."""
        edge = (u, v)
        durations = self.edge_durations.get(edge)
        if durations:
            return sum(durations) / len(durations)
        return default_time

    def estimate_route_cost(self, path: List[Tuple[int, int]]) -> float:
        """
        Calculates total historical estimated travel time + penalty for high obstacle history.
        """
        if len(path) < 2:
            return 0.0

        total_cost = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            total_cost += self.get_edge_travel_time(u, v)
            # Add obstacle history penalty
            obs_penalty = self.node_obstacle_counts.get(v, 0) * 0.5
            total_cost += obs_penalty

        return total_cost

    def get_route_statistics(self) -> Dict[str, Any]:
        """Aggregate performance summary."""
        total_trips = len(self.trips)
        if total_trips == 0:
            return {
                "total_trips": 0,
                "avg_travel_time_s": 0.0,
                "avg_waiting_time_s": 0.0,
                "total_distance": 0.0,
                "total_obstacles": 0,
                "total_reroutes": 0,
            }

        avg_time = sum(t.travel_time_s for t in self.trips) / total_trips
        avg_wait = sum(t.waiting_time_s for t in self.trips) / total_trips
        tot_dist = sum(t.distance for t in self.trips)
        tot_obs = sum(t.obstacles_encountered for t in self.trips)
        tot_reroutes = sum(t.reroutes_count for t in self.trips)

        return {
            "total_trips": total_trips,
            "avg_travel_time_s": round(avg_time, 2),
            "avg_waiting_time_s": round(avg_wait, 2),
            "total_distance": round(tot_dist, 2),
            "total_obstacles": tot_obs,
            "total_reroutes": tot_reroutes,
        }
