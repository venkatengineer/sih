"""
Route Planner and Decision Evaluator for Congestion-Aware Least-Time Path Selection.
Generates alternate candidate routes, evaluates expected remaining travel times,
and enforces stability rules (threshold, cooldown, safety).
"""

import time
from typing import List, Dict, Tuple, Optional, Any, Set
from world.grid_map import GridMap, Point, Segment
from world.world_model import LocalWorldModel
from planning.astar import AStarPlanner
from planning.congestion_estimator import CongestionEstimator
from planning.cost_estimator import CostEstimator
from learning.experience import ExperienceStore
from config import RobotConfig

class RoutePlanner:
    def __init__(
        self,
        grid_map: GridMap,
        config: RobotConfig,
        experience_store: Optional[ExperienceStore] = None,
        safety_checker: Optional[Any] = None
    ):
        self.grid_map = grid_map
        self.config = config
        self.experience_store = experience_store or ExperienceStore(learning_rate=config.learning_rate)
        self.safety_checker = safety_checker
        
        self.astar = AStarPlanner(grid_map)
        self.congestion_estimator = CongestionEstimator(config)
        self.cost_estimator = CostEstimator(config, self.congestion_estimator, self.experience_store)
        
        self.last_reroute_time: float = 0.0

    def generate_candidate_routes(
        self,
        start: Point,
        goal: Point,
        world_model: LocalWorldModel,
        current_route: Optional[List[Point]] = None
    ) -> List[List[Point]]:
        candidates: List[List[Point]] = []
        
        # 1. Primary A* route considering real-time congestion
        def primary_cost_callback(seg: Segment) -> float:
            return self.cost_estimator.estimate_segment_travel_time(seg, world_model)

        primary_path = self.astar.plan_path(start, goal, cost_callback=primary_cost_callback)
        if primary_path:
            candidates.append(primary_path)

        # 2. Include existing current route if provided and valid
        if current_route and len(current_route) > 1:
            # Re-anchor current route from start if start is on path
            try:
                idx = current_route.index(start)
                trimmed_current = current_route[idx:]
                if trimmed_current not in candidates:
                    candidates.append(trimmed_current)
            except ValueError:
                pass

        # 3. Generate alternate routes by penalizing congested edges on primary path
        base_route = primary_path or (current_route if current_route else None)
        if base_route and len(base_route) > 2:
            base_segments = GridMap.path_to_segments(base_route)
            
            # Identify congested / heavily used edges
            penalized_segments: Set[str] = set()
            for seg in base_segments:
                cong_info = self.congestion_estimator.evaluate_segment_congestion(seg, world_model)
                if cong_info.robot_count > 0 or cong_info.congestion_level in ("MEDIUM", "HIGH"):
                    penalized_segments.add(GridMap.undirected_segment_id(seg))

            # If no heavily congested edge found, penalize middle segments of primary path to force alternate discovery
            if not penalized_segments and len(base_segments) > 2:
                mid_idx = len(base_segments) // 2
                penalized_segments.add(GridMap.undirected_segment_id(base_segments[mid_idx]))

            # Alternate A* search with artificial penalty on primary edges
            def alternate_cost_callback(seg: Segment) -> float:
                cost = self.cost_estimator.estimate_segment_travel_time(seg, world_model)
                seg_id = GridMap.undirected_segment_id(seg)
                if seg_id in penalized_segments:
                    cost += 50.0  # Artificial penalty to force path divergence
                return cost

            alt_path = self.astar.plan_path(start, goal, cost_callback=alternate_cost_callback)
            if alt_path and alt_path not in candidates:
                candidates.append(alt_path)

        return candidates

    def select_best_route(
        self,
        start: Point,
        goal: Point,
        current_route: List[Point],
        current_index: int,
        world_model: LocalWorldModel,
        already_waited_time: float = 0.0
    ) -> Dict[str, Any]:
        """
        Evaluates current route remaining travel time against alternate candidate routes.
        Selects the minimum time route enforcing threshold, cooldown, and safety rules.
        """
        now = time.time()
        
        # Calculate Remaining Time on Current Route
        if current_route and 0 <= current_index < len(current_route):
            current_remaining_path = current_route[current_index:]
            current_remaining_time = self.cost_estimator.estimate_remaining_route_time(
                current_route, current_index, world_model, already_waited_time=already_waited_time
            )
        else:
            current_remaining_path = []
            current_remaining_time = float('inf')

        # Generate Candidates from current start position
        candidate_routes = self.generate_candidate_routes(start, goal, world_model, current_route=current_remaining_path)

        # Filter out current path from alternate candidates
        alternates: List[List[Point]] = []
        for cand in candidate_routes:
            if cand != current_remaining_path:
                alternates.append(cand)

        # Evaluate Congestion Level on current route
        cong_summary = self.congestion_estimator.get_route_congestion_summary(current_remaining_path, world_model)
        congestion_level = cong_summary["overall_congestion_level"]
        robots_on_current = cong_summary["max_robots_on_segment"]

        curr_dist = (len(current_remaining_path) - 1) * self.config.cell_size_meters if current_remaining_path and len(current_remaining_path) > 1 else 0.0
        alt_dist: Optional[float] = None

        # Case 1: No alternate routes available
        if not alternates:
            return {
                "best_route": current_remaining_path if current_remaining_path else [start],
                "estimated_time": current_remaining_time,
                "current_route_time": current_remaining_time,
                "alternate_route_time": None,
                "current_route_distance": curr_dist,
                "alternate_route_distance": None,
                "congestion_level": congestion_level,
                "robots_on_current_route": robots_on_current,
                "decision": "NO_ALTERNATE",
                "reason": "No valid alternate path found; continuing current route"
            }

        # Evaluate each alternate route
        best_alternate_route: Optional[List[Point]] = None
        best_alternate_time = float('inf')

        for alt in alternates:
            # Check Safety of Alternate Route
            if self.safety_checker:
                if not self.safety_checker.is_route_safe(alt, world_model):
                    continue  # Reject unsafe alternate path

            alt_time = self.cost_estimator.estimate_alternate_route_time(alt, world_model, is_reroute=True)
            if alt_time < best_alternate_time:
                best_alternate_time = alt_time
                best_alternate_route = alt

        if best_alternate_route:
            alt_dist = (len(best_alternate_route) - 1) * self.config.cell_size_meters

        # If all alternates were unsafe or invalid
        if not best_alternate_route or best_alternate_time == float('inf'):
            return {
                "best_route": current_remaining_path,
                "estimated_time": current_remaining_time,
                "current_route_time": current_remaining_time,
                "alternate_route_time": None,
                "current_route_distance": curr_dist,
                "alternate_route_distance": None,
                "congestion_level": congestion_level,
                "robots_on_current_route": robots_on_current,
                "decision": "NO_ALTERNATE",
                "reason": "All alternate routes are unsafe or invalid; continuing current route"
            }

        # Compare Current vs Alternate using Improvement Threshold and Cooldown
        required_time_limit = current_remaining_time * (1.0 - self.config.reroute_improvement_threshold)
        time_diff = current_remaining_time - best_alternate_time
        pct_improvement = (time_diff / current_remaining_time) * 100.0 if current_remaining_time > 0 else 0.0

        in_cooldown = (now - self.last_reroute_time) < self.config.reroute_cooldown_seconds

        if best_alternate_time < required_time_limit:
            if in_cooldown:
                # In cooldown period: suppress oscillation
                return {
                    "best_route": current_remaining_path,
                    "estimated_time": current_remaining_time,
                    "current_route_time": current_remaining_time,
                    "alternate_route_time": best_alternate_time,
                    "current_route_distance": curr_dist,
                    "alternate_route_distance": alt_dist,
                    "congestion_level": congestion_level,
                    "robots_on_current_route": robots_on_current,
                    "decision": "CONTINUE",
                    "reason": f"Alternate ({alt_dist}m) is faster by {pct_improvement:.1f}% than current ({curr_dist}m) but reroute cooldown is active"
                }
            else:
                # Trigger REROUTE
                self.last_reroute_time = now
                return {
                    "best_route": best_alternate_route,
                    "estimated_time": best_alternate_time,
                    "current_route_time": current_remaining_time,
                    "alternate_route_time": best_alternate_time,
                    "current_route_distance": curr_dist,
                    "alternate_route_distance": alt_dist,
                    "congestion_level": congestion_level,
                    "robots_on_current_route": robots_on_current,
                    "decision": "REROUTE",
                    "reason": f"Alternate route ({alt_dist}m, {best_alternate_time:.1f}s) is faster than current route ({curr_dist}m, {current_remaining_time:.1f}s) by {pct_improvement:.1f}%"
                }
        else:
            # Alternate is not sufficiently faster than threshold
            return {
                "best_route": current_remaining_path,
                "estimated_time": current_remaining_time,
                "current_route_time": current_remaining_time,
                "alternate_route_time": best_alternate_time,
                "current_route_distance": curr_dist,
                "alternate_route_distance": alt_dist,
                "congestion_level": congestion_level,
                "robots_on_current_route": robots_on_current,
                "decision": "CONTINUE",
                "reason": f"Current route ({curr_dist}m, {current_remaining_time:.1f}s) remains faster than alternate ({alt_dist}m, {best_alternate_time:.1f}s)"
            }
