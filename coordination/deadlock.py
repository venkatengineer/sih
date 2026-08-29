"""
Decentralized Deadlock Detector and Recovery Mechanism.
Detects circular waiting and sustained stall conditions, triggering yield/wait actions.
"""

import time
from typing import Dict, List, Optional
from world.grid_map import Point
from world.world_model import LocalWorldModel

class DeadlockDetector:
    def __init__(self, robot_id: str, stall_threshold_seconds: float = 4.0):
        self.robot_id = robot_id
        self.stall_threshold_seconds = stall_threshold_seconds
        self.last_position: Optional[Point] = None
        self.last_move_time: float = time.time()
        self.in_deadlock: bool = False

    def update_position(self, current_pos: Point):
        now = time.time()
        if self.last_position is None or self.last_position != current_pos:
            self.last_position = current_pos
            self.last_move_time = now
            self.in_deadlock = False

    def check_deadlock(self, current_pos: Point, has_goal: bool) -> bool:
        now = time.time()
        self.update_position(current_pos)
        
        if has_goal and (now - self.last_move_time) > self.stall_threshold_seconds:
            self.in_deadlock = True
            return True
        return False

    def resolve_deadlock_action(self, my_id: str, peer_id: str) -> str:
        """
        Determines deadlock recovery action. Lower ID robot yields or backs up.
        """
        if my_id > peer_id:
            return "YIELD"
        else:
            return "PROCEED"
