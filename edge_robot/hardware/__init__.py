"""
Hardware interfaces and implementations for Edge Robot.
"""

from edge_robot.hardware.interfaces import (
    CameraInterface,
    LidarInterface,
    MotorInterface,
    LocalizationInterface,
)
from edge_robot.hardware.mock_hardware import (
    MockCamera,
    MockLidar,
    MockMotor,
    MockLocalization,
)

__all__ = [
    "CameraInterface",
    "LidarInterface",
    "MotorInterface",
    "LocalizationInterface",
    "MockCamera",
    "MockLidar",
    "MockMotor",
    "MockLocalization",
]
