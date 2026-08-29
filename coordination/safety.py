"""
Safety Controller for Edge-AI AMR.
Enforces top priority safety constraints: emergency stop, collision avoidance,
obstacle proximity, and path safety validation.
"""

from typing import List, Optional
from world.grid_map import GridMap, Point
from world.world_model import LocalWorldModel
from config import RobotConfig

class SafetyController:
    def __init__(self, config: RobotConfig):
        self.config = config
        self.emergency_stop_triggered: bool = False

    def trigger_emergency_stop(self):
        self.emergency_stop_triggered = True

    def reset_emergency_stop(self):
        self.emergency_stop_triggered = False

    def is_collision_imminent(self, current_pos: Point, target_pos: Point, world_model: LocalWorldModel) -> bool:
        if self.emergency_stop_triggered:
            return True
            
        # Check static obstacles
        if not world_model.grid_map.is_traversable(target_pos):
            return True

        # Check peer position collision
        for peer in world_model.get_all_active_peers():
            if peer.position == target_pos:
                return True
            # Head-on collision check
            if peer.position == target_pos and current_pos in (peer.current_path or []):
                return True

        return False

    def is_route_safe(self, route: List[Point], world_model: LocalWorldModel) -> bool:
        """
        Validates that an entire candidate route is physically safe and free of static/dynamic blockages.
        """
        if self.emergency_stop_triggered:
            return False
            
        if not route:
            return False

        for cell in route:
            # Must be inside map and not static obstacle
            if not world_model.grid_map.is_traversable(cell, ignore_dynamic=False):
                return False

            # Check if cell is blocked by dynamic obstacle marked as unsafe
            if cell in world_model.grid_map.dynamic_obstacles:
                return False

        return True
