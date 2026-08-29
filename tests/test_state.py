"""
Unit tests for RobotState and serialization.
"""

import unittest
from edge_robot.core.enums import RobotStatus, RobotIntent
from edge_robot.core.state import RobotState


class TestRobotState(unittest.TestCase):
    def test_robot_state_serialization(self):
        state = RobotState(
            robot_id="AMR-01",
            position=(5.5, 7.2),
            heading=90.0,
            velocity=1.0,
            battery=87.5,
            status=RobotStatus.MOVING,
            intent=RobotIntent.MOVE,
            priority=65.0,
            current_path=[(5, 7), (6, 7), (7, 7)],
            next_node=(6, 7),
        )

        data = state.to_dict()
        self.assertEqual(data["robot_id"], "AMR-01")
        self.assertEqual(data["position"], [5.5, 7.2])
        self.assertEqual(data["status"], "MOVING")
        self.assertEqual(data["intent"], "MOVE")
        self.assertEqual(data["next_node"], [6, 7])

        restored = RobotState.from_dict(data)
        self.assertEqual(restored.robot_id, "AMR-01")
        self.assertEqual(restored.position, (5.5, 7.2))
        self.assertEqual(restored.status, RobotStatus.MOVING)
        self.assertEqual(restored.intent, RobotIntent.MOVE)
        self.assertEqual(restored.next_node, (6, 7))
        self.assertEqual(restored.current_path, [(5, 7), (6, 7), (7, 7)])

    def test_distance_calculation(self):
        state = RobotState(robot_id="AMR-01", position=(0.0, 0.0))
        self.assertEqual(state.distance_to((3.0, 4.0)), 5.0)


if __name__ == "__main__":
    unittest.main()
