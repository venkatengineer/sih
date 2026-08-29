"""
Congestion-Aware Dynamic A* Path Planner.
Implements standard A* with customizable edge cost callbacks to evaluate distance,
congestion penalties, and temporary edge weights for alternate path discovery.
"""

import heapq
from typing import List, Tuple, Dict, Set, Optional, Callable
from world.grid_map import GridMap, Point, Segment

class AStarPlanner:
    def __init__(self, grid_map: GridMap):
        self.grid_map = grid_map

    def plan_path(
        self,
        start: Point,
        goal: Point,
        cost_callback: Optional[Callable[[Segment], float]] = None,
        ignore_dynamic: bool = False
    ) -> Optional[List[Point]]:
        if not self.grid_map.is_traversable(start, ignore_dynamic=ignore_dynamic):
            return None
        if not self.grid_map.is_traversable(goal, ignore_dynamic=ignore_dynamic):
            return None

        if start == goal:
            return [start]

        open_set: List[Tuple[float, Point]] = []
        heapq.heappush(open_set, (0.0, start))

        came_from: Dict[Point, Point] = {}
        g_score: Dict[Point, float] = {start: 0.0}
        f_score: Dict[Point, float] = {start: GridMap.distance(start, goal)}

        visited: Set[Point] = set()

        while open_set:
            _, current = heapq.heappop(open_set)

            if current in visited:
                continue
            visited.add(current)

            if current == goal:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            for neighbor in self.grid_map.get_neighbors(current, ignore_dynamic=ignore_dynamic):
                segment = (current, neighbor)
                
                # Base step cost
                step_cost = GridMap.distance(current, neighbor)
                
                # Add custom edge cost if callback provided
                if cost_callback:
                    step_cost += cost_callback(segment)

                tentative_g = g_score[current] + step_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_val = tentative_g + GridMap.distance(neighbor, goal)
                    f_score[neighbor] = f_val
                    heapq.heappush(open_set, (f_val, neighbor))

        return None  # No path found
