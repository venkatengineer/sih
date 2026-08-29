"""
Route representation, metrics, and validity checking.
"""

from typing import List, Tuple, Optional
from edge_robot.world.map import LocalWorldModel


class RouteUtils:
    """Utilities for working with planned paths."""

    @staticmethod
    def is_path_valid(path: List[Tuple[int, int]], world: LocalWorldModel, current_idx: int = 0) -> bool:
        """
        Verify that all remaining nodes in the path are still passable.
        If an obstacle appeared on any remaining waypoint, returns False.
        """
        if not path:
            return False

        for node in path[current_idx:]:
            if not world.is_passable_for_planning(node):
                return False
        return True

    @staticmethod
    def get_remaining_path(path: List[Tuple[int, int]], current_pos: Tuple[float, float]) -> List[Tuple[int, int]]:
        """
        Find closest future waypoint and return slice of remaining nodes.
        """
        if not path:
            return []

        curr_x, curr_y = current_pos
        # Find index of closest node
        min_idx = 0
        min_dist = float("inf")
        for i, node in enumerate(path):
            d = (node[0] - curr_x) ** 2 + (node[1] - curr_y) ** 2
            if d < min_dist:
                min_dist = d
                min_idx = i

        return path[min_idx:]

    @staticmethod
    def get_lookahead_nodes(path: List[Tuple[int, int]], count: int = 3) -> List[Tuple[int, int]]:
        """Extract the next N lookahead nodes for intent broadcast."""
        return path[:count]
