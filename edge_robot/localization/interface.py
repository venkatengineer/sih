"""
Localization interface and local state estimator.
"""

from abc import ABC, abstractmethod
from typing import Tuple


class LocalizerInterface(ABC):
    """Abstract interface for robot localization estimation."""

    @abstractmethod
    def get_pose(self) -> Tuple[float, float, float]:
        """Returns (x, y, heading_degrees)."""
        pass

    @abstractmethod
    def update(self, delta_time: float, linear_velocity: float, angular_velocity: float) -> None:
        """Update dead reckoning estimation based on motion."""
        pass

    @abstractmethod
    def set_pose(self, x: float, y: float, heading: float) -> None:
        """Force set current pose (e.g. initial calibration)."""
        pass
