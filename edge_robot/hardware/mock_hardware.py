"""
Mock hardware implementations for testing and simulation.
"""

import math
import time
from typing import List, Tuple, Optional, Any

from edge_robot.hardware.interfaces import (
    CameraInterface,
    LidarInterface,
    MotorInterface,
    LocalizationInterface,
)


class MockCamera(CameraInterface):
    """Simulated camera source returning empty or synthetic frames."""

    def __init__(self, fps: int = 30):
        self._fps = fps
        self._opened = True

    def read_frame(self) -> Optional[Any]:
        if not self._opened:
            return None
        # Return a mock representation of a 640x480 frame
        return {"width": 640, "height": 480, "timestamp": time.time()}

    def is_opened(self) -> bool:
        return self._opened

    def release(self) -> None:
        self._opened = False


class MockLidar(LidarInterface):
    """Simulated Lidar sensor with programmable obstacle distance."""

    def __init__(self, default_min_distance: float = 10.0):
        self.default_min_distance = default_min_distance
        self.current_min_distance = default_min_distance

    def set_min_distance(self, distance: float) -> None:
        self.current_min_distance = distance

    def get_scan(self) -> List[Tuple[float, float]]:
        # Return 360-degree mock scan
        return [(self.current_min_distance, math.radians(i)) for i in range(0, 360, 10)]

    def get_min_distance(self) -> float:
        return self.current_min_distance


class MockMotor(MotorInterface):
    """Simulated motor controller tracking state commands."""

    def __init__(self):
        self.linear_velocity: float = 0.0
        self.angular_velocity: float = 0.0
        self.is_stopped: bool = True
        self.emergency_stopped: bool = False
        self.command_log: List[Tuple[float, str, float, float]] = []

    async def forward(self, speed: float) -> None:
        self.linear_velocity = speed
        self.angular_velocity = 0.0
        self.is_stopped = False
        self.command_log.append((time.time(), "FORWARD", speed, 0.0))

    async def rotate(self, angular_velocity: float) -> None:
        self.linear_velocity = 0.0
        self.angular_velocity = angular_velocity
        self.is_stopped = False
        self.command_log.append((time.time(), "ROTATE", 0.0, angular_velocity))

    async def set_velocity(self, linear: float, angular: float) -> None:
        self.linear_velocity = linear
        self.angular_velocity = angular
        self.is_stopped = (linear == 0.0 and angular == 0.0)
        self.command_log.append((time.time(), "SET_VELOCITY", linear, angular))

    async def stop(self) -> None:
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0
        self.is_stopped = True
        self.command_log.append((time.time(), "STOP", 0.0, 0.0))

    async def emergency_stop(self) -> None:
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0
        self.is_stopped = True
        self.emergency_stopped = True
        self.command_log.append((time.time(), "EMERGENCY_STOP", 0.0, 0.0))


class MockLocalization(LocalizationInterface):
    """Simulated dead reckoning and localization."""

    def __init__(self, initial_x: float = 0.0, initial_y: float = 0.0, initial_heading: float = 0.0):
        self.x = initial_x
        self.y = initial_y
        self.heading = initial_heading

    def get_pose(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.heading)

    def set_pose(self, x: float, y: float, heading: float) -> None:
        self.x = x
        self.y = y
        self.heading = heading
