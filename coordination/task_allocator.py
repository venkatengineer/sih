"""
Decentralized Task Allocator.
Implements task bidding mechanism where robots evaluate task distance and assign tasks locally.
"""

from typing import Dict, List, Optional, Any
from world.grid_map import GridMap, Point

class Task:
    def __init__(self, task_id: str, pickup: Point, dropoff: Point, priority: int = 1):
        self.task_id = task_id
        self.pickup = pickup
        self.dropoff = dropoff
        self.priority = priority
        self.assigned_robot: Optional[str] = None

class TaskAllocator:
    def __init__(self, robot_id: str):
        self.robot_id = robot_id

    def calculate_bid(self, current_pos: Point, task: Task) -> float:
        """
        Calculates bid cost based on distance to pickup point. Lower cost wins bid.
        """
        dist = GridMap.manhattan_distance(current_pos, task.pickup)
        return float(dist)

    def select_winning_bid(self, bids: Dict[str, float]) -> Optional[str]:
        if not bids:
            return None
        # Lowest bid cost wins. Tie breaker: lexicographical robot ID
        winning_robot = min(bids.keys(), key=lambda r: (bids[r], r))
        return winning_robot
