"""
Unit tests for Wait-For Graph (WFG) Deadlock Detection.
"""

import unittest
from edge_robot.core.state import RobotState
from edge_robot.coordination.deadlock import DeadlockDetector


class TestDeadlock(unittest.TestCase):
    def test_3_robot_deadlock_detection(self):
        r1 = RobotState(robot_id="AMR-01", position=(1.0, 1.0), next_node=(1, 2), priority=80.0)
        r2 = RobotState(robot_id="AMR-02", position=(1.0, 2.0), next_node=(2, 2), priority=60.0)
        r3 = RobotState(robot_id="AMR-03", position=(2.0, 2.0), next_node=(1, 1), priority=40.0)

        peers = {"AMR-02": r2, "AMR-03": r3}
        report = DeadlockDetector.evaluate_deadlock(r1, peers)

        self.assertIsNotNone(report)
        self.assertEqual(set(report.cycle), {"AMR-01", "AMR-02", "AMR-03"})
        self.assertEqual(report.victim_robot_id, "AMR-03")


if __name__ == "__main__":
    unittest.main()
