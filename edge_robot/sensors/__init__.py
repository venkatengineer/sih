"""
Sensors package for Edge Robot.
"""

from edge_robot.sensors.interfaces import (
    DetectedObstacleData,
    SensorObservation,
    SensorInterface,
)
from edge_robot.sensors.mock import MockSensor

__all__ = [
    "DetectedObstacleData",
    "SensorObservation",
    "SensorInterface",
    "MockSensor",
]
