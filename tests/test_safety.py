"""
Unit tests for Safety Controller.
"""

import unittest
import asyncio
from edge_robot.hardware.mock_hardware import MockMotor
from edge_robot.safety.safety_controller import SafetyController


class TestSafety(unittest.TestCase):
    def test_safety_override(self):
        async def _run():
            motor = MockMotor()
            safety = SafetyController(motor, min_safe_distance=1.2)

            safe = await safety.execute_safe_velocity(linear_velocity=1.0, angular_velocity=0.0, nearest_obstacle_dist=5.0)
            self.assertTrue(safe)
            self.assertEqual(motor.linear_velocity, 1.0)
            self.assertFalse(safety.is_emergency_stopped)

            safe = await safety.execute_safe_velocity(linear_velocity=1.0, angular_velocity=0.0, nearest_obstacle_dist=0.8)
            self.assertFalse(safe)
            self.assertEqual(motor.linear_velocity, 0.0)
            self.assertTrue(safety.is_emergency_stopped)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
