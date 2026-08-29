"""
Camera hardware module.
"""

from edge_robot.hardware.interfaces import CameraInterface
from edge_robot.hardware.mock_hardware import MockCamera

__all__ = ["CameraInterface", "MockCamera"]
