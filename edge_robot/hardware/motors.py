"""
Motor hardware module.
"""

from edge_robot.hardware.interfaces import MotorInterface
from edge_robot.hardware.mock_hardware import MockMotor

__all__ = ["MotorInterface", "MockMotor"]
