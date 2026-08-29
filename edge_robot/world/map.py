"""
Local world model and occupancy grid for an independent Edge Robot.
"""

from __future__ import annotations
import math
import time
from typing import List, Tuple, Set, Dict, Optional

from edge_robot.core.enums import ObstacleType
from edge_robot.world.obstacle import LocalObstacle


class LocalWorldModel:
    """
    Every RobotAgent maintains its own local world model.
    Contains static obstacles, dynamic obstacles, known peer robots,
    blocked areas, and temporary reservations.
    """

    def __init__(self, width: int = 20, height: int = 20, static_obstacles: Optional[List[Tuple[int, int]]] = None):
        self.width = width
        self.height = height
        self.static_obstacles: Set[Tuple[int, int]] = set(static_obstacles or [])
        self.dynamic_obstacles: Dict[str, LocalObstacle] = {}
        self.blocked_nodes: Set[Tuple[int, int]] = set()
        self.peer_positions: Dict[str, Tuple[float, float]] = {}
        self.peer_next_nodes: Dict[str, Tuple[int, int]] = {}
        self.peer_reservations: Dict[str, Tuple[int, int]] = {}  # robot_id -> reserved_node

    def is_in_bounds(self, node: Tuple[int, int]) -> bool:
        """Check if grid coordinates are within the warehouse boundary."""
        x, y = node
        return 0 <= x < self.width and 0 <= y < self.height

    def is_static_free(self, node: Tuple[int, int]) -> bool:
        """Check if node is inside bounds and free of permanent static obstacles."""
        return self.is_in_bounds(node) and (node not in self.static_obstacles)

    def is_free(self, node: Tuple[int, int], ignore_peer_id: Optional[str] = None) -> bool:
        """
        Check if a node is completely free of static/dynamic obstacles, blocked areas, and peer robots.
        """
        if not self.is_static_free(node):
            return False

        if node in self.blocked_nodes:
            return False

        # Check dynamic obstacles
        for obs in self.dynamic_obstacles.values():
            obs_grid = (int(round(obs.position[0])), int(round(obs.position[1])))
            if obs_grid == node:
                return False

        # Check peer occupied positions & next nodes
        for p_id, pos in self.peer_positions.items():
            if p_id == ignore_peer_id:
                continue
            peer_grid = (int(round(pos[0])), int(round(pos[1])))
            if peer_grid == node:
                return False

        for p_id, next_n in self.peer_next_nodes.items():
            if p_id == ignore_peer_id:
                continue
            if next_n == node:
                return False

        return True

    def is_passable_for_planning(self, node: Tuple[int, int], avoid_nodes: Optional[Set[Tuple[int, int]]] = None) -> bool:
        """
        Passability check for A* path planner.
        Avoids static walls, dynamic obstacles, blocked aisles, and explicitly avoided nodes.
        """
        if not self.is_static_free(node):
            return False

        if node in self.blocked_nodes:
            return False

        if avoid_nodes and node in avoid_nodes:
            return False

        for obs in self.dynamic_obstacles.values():
            obs_grid = (int(round(obs.position[0])), int(round(obs.position[1])))
            if obs_grid == node:
                return False

        return True

    def get_neighbors(self, node: Tuple[int, int], avoid_nodes: Optional[Set[Tuple[int, int]]] = None) -> List[Tuple[int, int]]:
        """
        Get valid 4-connected (N, S, E, W) neighbors for path planning.
        """
        x, y = node
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in candidates if self.is_passable_for_planning(c, avoid_nodes)]

    def add_obstacle(self, obstacle: LocalObstacle) -> None:
        """Add or update a local dynamic obstacle."""
        self.dynamic_obstacles[obstacle.obstacle_id] = obstacle

    def remove_obstacle(self, obstacle_id: str) -> None:
        """Remove a dynamic obstacle."""
        if obstacle_id in self.dynamic_obstacles:
            del self.dynamic_obstacles[obstacle_id]

    def block_node(self, node: Tuple[int, int]) -> None:
        """Manually mark a node as blocked (e.g. spilled aisle, maintenance)."""
        self.blocked_nodes.add(node)

    def unblock_node(self, node: Tuple[int, int]) -> None:
        """Unblock a node."""
        self.blocked_nodes.discard(node)

    def update_peer(
        self,
        robot_id: str,
        position: Tuple[float, float],
        next_node: Optional[Tuple[int, int]] = None,
        reserved_node: Optional[Tuple[int, int]] = None,
    ) -> None:
        """Update peer robot state in local world model."""
        self.peer_positions[robot_id] = position
        if next_node:
            self.peer_next_nodes[robot_id] = next_node
        elif robot_id in self.peer_next_nodes:
            del self.peer_next_nodes[robot_id]

        if reserved_node:
            self.peer_reservations[robot_id] = reserved_node
        elif robot_id in self.peer_reservations:
            del self.peer_reservations[robot_id]

    def remove_peer(self, robot_id: str) -> None:
        """Remove peer robot (e.g. after heartbeat timeout)."""
        self.peer_positions.pop(robot_id, None)
        self.peer_next_nodes.pop(robot_id, None)
        self.peer_reservations.pop(robot_id, None)

    def clean_expired(self, current_time: Optional[float] = None) -> None:
        """Remove expired dynamic obstacles."""
        t = current_time or time.time()
        expired_ids = [obs_id for obs_id, obs in self.dynamic_obstacles.items() if obs.is_expired(t)]
        for obs_id in expired_ids:
            del self.dynamic_obstacles[obs_id]

    def get_nearest_obstacle_distance(self, current_position: Tuple[float, float]) -> float:
        """Calculate minimum Euclidean distance to any known obstacle or peer."""
        min_dist = 999.0

        # Check static obstacles within proximity
        curr_x, curr_y = current_position
        for (sx, sy) in self.static_obstacles:
            d = math.hypot(curr_x - sx, curr_y - sy)
            if d < min_dist:
                min_dist = d

        # Check dynamic obstacles
        for obs in self.dynamic_obstacles.values():
            d = math.hypot(curr_x - obs.position[0], curr_y - obs.position[1])
            if d < min_dist:
                min_dist = d

        # Check peer positions
        for pos in self.peer_positions.values():
            d = math.hypot(curr_x - pos[0], curr_y - pos[1])
            if d < min_dist:
                min_dist = d

        return min_dist
