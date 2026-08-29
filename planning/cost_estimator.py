"""
Travel-Time & Route Cost Estimator.
Calculates deterministic travel times for full and partial routes,
factoring in base velocity, segment congestion, historical experience,
conflict/reservation delays, dynamic obstacles, and reroute overhead.
"""

from typing import List, Dict, Any, Optional
from world.grid_map import GridMap, Point, Segment
from world.world_model import LocalWorldModel
from learning.experience import ExperienceStore
from planning.congestion_estimator import CongestionEstimator
from config import RobotConfig

class CostEstimator:
    def __init__(self, config: RobotConfig, congestion_estimator: CongestionEstimator,
                 experience_store: Optional[ExperienceStore] = None):
        self.config = config
        self.congestion_estimator = congestion_estimator
        self.experience_store = experience_store or ExperienceStore(learning_rate=config.learning_rate)

    def estimate_segment_travel_time(self, segment: Segment, world_model: LocalWorldModel) -> float:
        p1, p2 = segment
        dist = GridMap.distance(p1, p2) * self.config.cell_size_meters
        base_time = dist / self.config.expected_velocity
        
        # 1. Congestion Delay
        cong_info = self.congestion_estimator.evaluate_segment_congestion(segment, world_model)
        cong_delay = cong_info.estimated_queue_delay
        
        # 2. Reservation / Conflict Delay
        res_delay = 0.0
        if world_model.is_cell_reserved(p2, self.config.robot_id):
            res_delay += 3.0 * self.config.reservation_delay_weight
            
        # 3. Dynamic Obstacle Delay
        obstacle_delay = 0.0
        if p2 in world_model.grid_map.dynamic_obstacles:
            obstacle_delay += 10.0 * self.config.obstacle_penalty_weight
            
        # 4. Historical Experience Penalty
        hist_penalty = 0.0
        if self.config.historical_cost_weight > 0:
            hist_penalty = self.experience_store.get_historical_cost_penalty(segment, base_time) * self.config.historical_cost_weight
            
        total_time = base_time + cong_delay + res_delay + obstacle_delay + hist_penalty
        return total_time

    def estimate_full_route_time(self, route: List[Point], world_model: LocalWorldModel) -> float:
        if not route or len(route) < 2:
            return 0.0
            
        segments = GridMap.path_to_segments(route)
        total_time = 0.0
        for seg in segments:
            total_time += self.estimate_segment_travel_time(seg, world_model)
        return total_time

    def estimate_remaining_route_time(
        self,
        current_route: List[Point],
        current_index: int,
        world_model: LocalWorldModel,
        already_waited_time: float = 0.0
    ) -> float:
        """
        Calculates expected remaining completion time on the current route from current_index.
        Includes current waiting time if stuck at an intersection.
        """
        if not current_route or current_index >= len(current_route) - 1:
            return 0.0
            
        remaining_path = current_route[current_index:]
        remaining_travel_time = self.estimate_full_route_time(remaining_path, world_model)
        
        # If currently waiting, add expected additional wait time
        # Formula: Expected additional wait if already waiting
        additional_wait = 0.0
        if already_waited_time > 0:
            # e.g., expected additional wait estimate
            additional_wait = max(1.0, 5.0 - (already_waited_time * 0.5))
            
        return remaining_travel_time + additional_wait

    def estimate_alternate_route_time(
        self,
        alternate_route: List[Point],
        world_model: LocalWorldModel,
        is_reroute: bool = True
    ) -> float:
        """
        Calculates expected travel time on an alternate candidate route.
        Includes rerouting switching overhead penalty if switching routes.
        """
        if not alternate_route or len(alternate_route) < 2:
            return float('inf')
            
        base_alternate_time = self.estimate_full_route_time(alternate_route, world_model)
        overhead = self.config.reroute_overhead_seconds if is_reroute else 0.0
        return base_alternate_time + overhead
