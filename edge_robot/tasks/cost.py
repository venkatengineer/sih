"""
Deterministic Bid Cost Calculator for Decentralized Task Allocation.
Evaluates travel distance (A*), local congestion, active workload, battery reserves,
and historical route experience without any machine learning dependencies.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple, Any

from edge_robot.tasks.task import Task
from edge_robot.tasks.bid import TaskBid
from edge_robot.planning.planner import PathPlanner
from edge_robot.world.map import LocalWorldModel
from edge_robot.learning.experience import ExperienceStore


class BidCostCalculator:
    """
    Computes a deterministic cost score for bidding on a warehouse transport task:
    Cost = (w_dist * distance) + (w_cong * congestion) + (w_work * workload) + (w_bat * battery_penalty) + (w_exp * experience)
    """

    def __init__(
        self,
        planner: Optional[PathPlanner] = None,
        world: Optional[LocalWorldModel] = None,
        experience_store: Optional[ExperienceStore] = None,
        distance_weight: float = 1.0,
        congestion_weight: float = 5.0,
        workload_weight: float = 3.0,
        battery_weight: float = 2.0,
        experience_weight: float = 2.0,
        minimum_task_battery: float = 20.0,
        nominal_speed: float = 1.5,
    ):
        self.planner = planner
        self.world = world
        self.experience_store = experience_store
        self.distance_weight = distance_weight
        self.congestion_weight = congestion_weight
        self.workload_weight = workload_weight
        self.battery_weight = battery_weight
        self.experience_weight = experience_weight
        self.minimum_task_battery = minimum_task_battery
        self.nominal_speed = nominal_speed

    def calculate_bid(
        self,
        task: Task,
        robot_id: str,
        current_position: Tuple[float, float],
        battery_percent: float,
        active_task_count: int = 0,
        pending_task_count: int = 0,
        auction_round: int = 1,
        known_peer_positions: Optional[List[Tuple[float, float]]] = None,
    ) -> TaskBid:
        """
        Calculates full bid for a task. Returns a valid TaskBid or an invalid TaskBid if infeasible.
        """
        # 1. Hard Battery Feasibility Check
        if battery_percent < self.minimum_task_battery:
            return TaskBid(
                task_id=task.task_id,
                robot_id=robot_id,
                cost=float("inf"),
                auction_round=auction_round,
                battery=battery_percent,
                workload=active_task_count + pending_task_count,
                is_valid=False,
            )

        # 2. Path & Distance Calculation (current -> pickup -> dropoff)
        path_to_pickup: List[Tuple[int, int]] = []
        path_to_dropoff: List[Tuple[int, int]] = []

        curr_pt = (current_position[0], current_position[1])
        pickup_pt = (float(task.pickup[0]), float(task.pickup[1]))
        dropoff_pt = (float(task.dropoff[0]), float(task.dropoff[1]))

        if self.planner:
            path_to_pickup = self.planner.plan(curr_pt, pickup_pt)
            path_to_dropoff = self.planner.plan(pickup_pt, dropoff_pt)

            if not path_to_pickup or not path_to_dropoff:
                # No walkable path to pickup or dropoff
                return TaskBid(
                    task_id=task.task_id,
                    robot_id=robot_id,
                    cost=float("inf"),
                    auction_round=auction_round,
                    battery=battery_percent,
                    workload=active_task_count + pending_task_count,
                    is_valid=False,
                )

            dist1 = max(0, len(path_to_pickup) - 1)
            dist2 = max(0, len(path_to_dropoff) - 1)
            total_distance = float(dist1 + dist2)
            combined_path = path_to_pickup + (path_to_dropoff[1:] if len(path_to_dropoff) > 1 else [])
        else:
            # Euclidean distance fallback if planner not provided
            dist1 = math.hypot(curr_pt[0] - pickup_pt[0], curr_pt[1] - pickup_pt[1])
            dist2 = math.hypot(pickup_pt[0] - dropoff_pt[0], pickup_pt[1] - dropoff_pt[1])
            total_distance = float(dist1 + dist2)
            combined_path = []

        # 3. Congestion Estimation
        congestion = self._estimate_congestion(combined_path, known_peer_positions)

        # 4. Workload Penalty
        workload = active_task_count + pending_task_count
        workload_penalty = (active_task_count * 10.0) + (pending_task_count * 5.0)

        # 5. Battery Penalty (discourage robots with lower remaining charge)
        battery_penalty = 0.0
        if battery_percent < 50.0:
            battery_penalty = (50.0 - battery_percent) * 0.4

        # 6. Historical Route Experience Penalty
        experience_penalty = 0.0
        if self.experience_store and combined_path:
            historical_cost = self.experience_store.estimate_route_cost(combined_path)
            # Compare against nominal time
            nominal_time = total_distance / self.nominal_speed
            if historical_cost > nominal_time:
                experience_penalty = (historical_cost - nominal_time) * 0.5

        # 7. Total Cost Formula
        total_cost = (
            (self.distance_weight * total_distance)
            + (self.congestion_weight * congestion * 10.0)
            + (self.workload_weight * workload_penalty)
            + (self.battery_weight * battery_penalty)
            + (self.experience_weight * experience_penalty)
        )

        estimated_time = (total_distance / self.nominal_speed) * (1.0 + (congestion * 0.5))

        return TaskBid(
            task_id=task.task_id,
            robot_id=robot_id,
            cost=round(total_cost, 2),
            auction_round=auction_round,
            estimated_time=round(estimated_time, 2),
            distance=round(total_distance, 2),
            battery=round(battery_percent, 1),
            congestion=round(congestion, 2),
            workload=workload,
            is_valid=True,
        )

    def _estimate_congestion(
        self,
        path: List[Tuple[int, int]],
        known_peer_positions: Optional[List[Tuple[float, float]]],
    ) -> float:
        """Estimate congestion score [0.0 to 1.0] along the candidate path."""
        if not path:
            return 0.0

        congested_nodes = 0
        path_set = set(path)

        # Check peer proximity to path
        if known_peer_positions:
            for px, py in known_peer_positions:
                peer_node = (int(round(px)), int(round(py)))
                if peer_node in path_set:
                    congested_nodes += 2

        # Check dynamic obstacles in world
        if self.world:
            for obs in self.world.dynamic_obstacles.values():
                obs_node = (int(round(obs.position[0])), int(round(obs.position[1])))
                if obs_node in path_set:
                    congested_nodes += 3

        score = float(congested_nodes) / float(max(1, len(path)))
        return min(1.0, max(0.0, score))
