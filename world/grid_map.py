"""
Grid Map abstraction for 2D Warehouse Environment.
Supports cell traversability, Manhattan/Euclidean distance heuristics,
neighbor lookup, and path segment helpers.
"""

import math
from typing import List, Tuple, Set, Dict, Optional

Point = Tuple[int, int]
Segment = Tuple[Point, Point]

class GridMap:
    def __init__(self, width: int = 30, height: int = 30, cell_size: float = 1.0):
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.obstacles: Set[Point] = set()
        self.dynamic_obstacles: Set[Point] = set()

    def set_obstacle(self, x: int, y: int, is_obstacle: bool = True):
        p = (x, y)
        if is_obstacle:
            self.obstacles.add(p)
        else:
            self.obstacles.discard(p)

    def set_dynamic_obstacle(self, x: int, y: int, is_obstacle: bool = True):
        p = (x, y)
        if is_obstacle:
            self.dynamic_obstacles.add(p)
        else:
            self.dynamic_obstacles.discard(p)

    def clear_dynamic_obstacles(self):
        self.dynamic_obstacles.clear()

    def load_default_warehouse_obstacles(self):
        """Populates realistic warehouse storage racking aisles with cross-passages."""
        self.obstacles.clear()
        # Warehouse Racking Rows at y=7, y=12, y=18, y=23
        for x in range(4, 26):
            if x not in (10, 11, 19, 20):  # Gaps for aisle cross-passages
                self.obstacles.add((x, 7))
                self.obstacles.add((x, 12))
                self.obstacles.add((x, 18))
                self.obstacles.add((x, 23))

    def is_in_bounds(self, p: Point) -> bool:
        x, y = p
        return 0 <= x < self.width and 0 <= y < self.height

    def is_traversable(self, p: Point, ignore_dynamic: bool = False) -> bool:
        if not self.is_in_bounds(p):
            return False
        if p in self.obstacles:
            return False
        if not ignore_dynamic and p in self.dynamic_obstacles:
            return False
        return True

    def get_neighbors(self, p: Point, ignore_dynamic: bool = False) -> List[Point]:
        x, y = p
        candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [c for c in candidates if self.is_traversable(c, ignore_dynamic=ignore_dynamic)]

    @staticmethod
    def distance(p1: Point, p2: Point) -> float:
        # Euclidean distance
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    @staticmethod
    def manhattan_distance(p1: Point, p2: Point) -> float:
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

    @staticmethod
    def path_to_segments(path: List[Point]) -> List[Segment]:
        if not path or len(path) < 2:
            return []
        segments = []
        for i in range(len(path) - 1):
            segments.append((path[i], path[i+1]))
        return segments

    @staticmethod
    def segment_id(seg: Segment) -> str:
        # Standardize segment string id regardless of direction or directed
        p1, p2 = seg
        return f"{p1[0]},{p1[1]}->{p2[0]},{p2[1]}"

    @staticmethod
    def undirected_segment_id(seg: Segment) -> str:
        p1, p2 = seg
        if p1 > p2:
            p1, p2 = p2, p1
        return f"{p1[0]},{p1[1]}--{p2[0]},{p2[1]}"
