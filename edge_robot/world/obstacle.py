"""
Obstacle representation within the local world model.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Tuple, Dict, Any

from edge_robot.core.enums import ObstacleType


@dataclass
class LocalObstacle:
    """Obstacle tracked in the robot's local world model."""
    obstacle_id: str
    obstacle_type: ObstacleType
    position: Tuple[float, float]
    radius: float = 0.5  # Bounding radius in meters
    confidence: float = 1.0
    source: str = "sensor"
    discovered_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 10.0)  # Dynamic obstacles expire

    def is_expired(self, current_time: float) -> bool:
        """Check if transient dynamic obstacle has timed out."""
        return current_time > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obstacle_id": self.obstacle_id,
            "obstacle_type": self.obstacle_type.value,
            "position": list(self.position),
            "radius": self.radius,
            "confidence": self.confidence,
            "source": self.source,
            "discovered_at": self.discovered_at,
            "expires_at": self.expires_at,
        }
