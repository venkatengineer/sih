"""
Mock sensor implementation for testing and development.
"""

from typing import List, Tuple, Optional
import time

from edge_robot.core.enums import ObstacleType
from edge_robot.sensors.interfaces import (
    SensorInterface,
    SensorObservation,
    DetectedObstacleData,
)


class MockSensor(SensorInterface):
    """
    Mock sensor provider allowing programmatic injection of obstacles.
    """

    def __init__(self):
        self._injected_obstacles: List[DetectedObstacleData] = []
        self._min_distance: float = 999.0

    def inject_obstacle(
        self,
        obstacle_id: str,
        obstacle_type: ObstacleType,
        position: Tuple[float, float],
        distance: float,
        confidence: float = 0.95,
    ) -> None:
        """Inject a simulated detected obstacle."""
        obs = DetectedObstacleData(
            obstacle_id=obstacle_id,
            obstacle_type=obstacle_type,
            position=position,
            distance=distance,
            confidence=confidence,
            source="mock_sensor",
            timestamp=time.time(),
        )
        # Remove old with same ID
        self._injected_obstacles = [o for o in self._injected_obstacles if o.obstacle_id != obstacle_id]
        self._injected_obstacles.append(obs)
        self._update_min_distance()

    def clear_obstacles(self) -> None:
        """Clear all injected obstacles."""
        self._injected_obstacles.clear()
        self._min_distance = 999.0

    def remove_obstacle(self, obstacle_id: str) -> None:
        """Remove specific obstacle by id."""
        self._injected_obstacles = [o for o in self._injected_obstacles if o.obstacle_id != obstacle_id]
        self._update_min_distance()

    def _update_min_distance(self) -> None:
        if self._injected_obstacles:
            self._min_distance = min(o.distance for o in self._injected_obstacles)
        else:
            self._min_distance = 999.0

    def get_observation(self) -> SensorObservation:
        """Return the current sensor observation."""
        return SensorObservation(
            obstacles=list(self._injected_obstacles),
            min_obstacle_distance=self._min_distance,
            timestamp=time.time(),
        )
