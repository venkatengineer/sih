"""
Deterministic Safety Controller for Edge Robot.
Acts as a safety shield between high-level decisions and low-level motor hardware.
"""

import time
from typing import Tuple, Optional
from edge_robot.hardware.interfaces import MotorInterface


class SafetyController:
    """
    Deterministic safety controller.
    Overrides all planner/AI velocity commands if safety criteria are violated.
    """

    def __init__(self, motor: MotorInterface, min_safe_distance: float = 1.0):
        self.motor = motor
        self.min_safe_distance = min_safe_distance
        self.last_safety_stop_time: Optional[float] = None
        self.is_emergency_stopped: bool = False

    async def execute_safe_velocity(
        self,
        linear_velocity: float,
        angular_velocity: float,
        nearest_obstacle_dist: float,
    ) -> bool:
        """
        Verify safety before commanding motors.
        If nearest_obstacle_dist < min_safe_distance and trying to move forward:
            Forces STOP and returns False.
        Otherwise:
            Commands motor and returns True.
        """
        # If robot is trying to move forward towards an obstacle that is too close
        if linear_velocity > 0 and nearest_obstacle_dist <= self.min_safe_distance:
            await self.motor.stop()
            self.last_safety_stop_time = time.time()
            self.is_emergency_stopped = True
            return False

        # Safe to proceed
        self.is_emergency_stopped = False
        await self.motor.set_velocity(linear_velocity, angular_velocity)
        return True

    async def force_stop(self) -> None:
        """Immediate command to stop motor."""
        await self.motor.stop()
        self.is_emergency_stopped = True

    async def force_emergency_stop(self) -> None:
        """Emergency hard stop."""
        await self.motor.emergency_stop()
        self.is_emergency_stopped = True
