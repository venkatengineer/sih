"""
Abstract hardware interfaces for Edge Robot.
Enables running the exact same agent logic on Mock hardware and physical Raspberry Pi hardware.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Any


class CameraInterface(ABC):
    """Abstract interface for camera video stream."""

    @abstractmethod
    def read_frame(self) -> Optional[Any]:
        """Read a single frame from the camera. Returns raw frame or None."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """Check if camera device is active."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Release camera hardware resources."""
        pass


class LidarInterface(ABC):
    """Abstract interface for 2D/3D Lidar range scanner."""

    @abstractmethod
    def get_scan(self) -> List[Tuple[float, float]]:
        """
        Get range scan data.
        Returns list of (distance_meters, angle_radians).
        """
        pass

    @abstractmethod
    def get_min_distance(self) -> float:
        """Get distance in meters to the closest detected object."""
        pass


class MotorInterface(ABC):
    """Abstract interface for differential drive or omnidirectional wheel motors."""

    @abstractmethod
    async def forward(self, speed: float) -> None:
        """Drive forward at given speed (m/s)."""
        pass

    @abstractmethod
    async def rotate(self, angular_velocity: float) -> None:
        """Rotate at given angular velocity (rad/s)."""
        pass

    @abstractmethod
    async def set_velocity(self, linear: float, angular: float) -> None:
        """Set linear and angular velocity simultaneously."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Safely bring motors to zero speed."""
        pass

    @abstractmethod
    async def emergency_stop(self) -> None:
        """Immediate hard stop (locks brakes if available)."""
        pass


class LocalizationInterface(ABC):
    """Abstract interface for dead reckoning, wheel odometry, or external tracking."""

    @abstractmethod
    def get_pose(self) -> Tuple[float, float, float]:
        """Returns (x, y, heading_degrees)."""
        pass

    @abstractmethod
    def set_pose(self, x: float, y: float, heading: float) -> None:
        """Calibrate / reset current robot pose."""
        pass
