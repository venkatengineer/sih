"""
Snapshot view of world from the individual robot's perspective.
"""

from typing import List, Tuple, Dict, Any
from edge_robot.world.map import LocalWorldModel


class RobotWorldView:
    """Read-only query helper for the robot's local world model."""

    def __init__(self, world_model: LocalWorldModel):
        self.world = world_model

    def get_summary(self, robot_position: Tuple[float, float]) -> Dict[str, Any]:
        return {
            "static_obstacle_count": len(self.world.static_obstacles),
            "dynamic_obstacle_count": len(self.world.dynamic_obstacles),
            "known_peers": list(self.world.peer_positions.keys()),
            "blocked_nodes": [list(n) for n in self.world.blocked_nodes],
            "nearest_obstacle_dist": round(self.world.get_nearest_obstacle_distance(robot_position), 2),
        }
