"""
Lidar hardware module.
"""

from edge_robot.hardware.interfaces import LidarInterface
from edge_robot.hardware.mock_hardware import MockLidar

__all__ = ["LidarInterface", "MockLidar"]
