"""
Dead-reckoning and kinematics localizer for Edge Robot.
"""

import math
from typing import Tuple
from edge_robot.localization.interface import LocalizerInterface


class Localizer(LocalizerInterface):
    """
    Tracks robot position and heading via dead reckoning kinematics.
    """

    def __init__(self, initial_x: float = 0.0, initial_y: float = 0.0, initial_heading: float = 0.0):
        self.x: float = initial_x
        self.y: float = initial_y
        self.heading: float = initial_heading  # in degrees [0, 360)

    def get_pose(self) -> Tuple[float, float, float]:
        return (round(self.x, 3), round(self.y, 3), round(self.heading, 2))

    def set_pose(self, x: float, y: float, heading: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.heading = float(heading % 360.0)

    def update(self, delta_time: float, linear_velocity: float, angular_velocity: float) -> None:
        """
        Integrate velocities to update position and heading.
        """
        # Update heading (angular velocity in deg/s or rad/s, we use deg/s)
        self.heading = (self.heading + angular_velocity * delta_time) % 360.0

        # Update position along current heading
        rad = math.radians(self.heading)
        distance = linear_velocity * delta_time
        self.x += distance * math.cos(rad)
        self.y += distance * math.sin(rad)

    def move_towards(self, target: Tuple[float, float], step_distance: float) -> Tuple[float, float, float]:
        """
        Helper for discrete/continuous waypoint traversal: moves directly towards target by step_distance.
        Returns new (x, y, heading).
        """
        dx = target[0] - self.x
        dy = target[1] - self.y
        dist = math.hypot(dx, dy)

        if dist <= step_distance:
            self.x = target[0]
            self.y = target[1]
        else:
            self.x += (dx / dist) * step_distance
            self.y += (dy / dist) * step_distance

        if dist > 1e-4:
            self.heading = math.degrees(math.atan2(dy, dx)) % 360.0

        return self.get_pose()
