"""
Unit tests for Conflict Detection, Priority Scoring, and Resolution.
"""

import unittest
from edge_robot.core.enums import ConflictAction, RobotStatus, RobotIntent
from edge_robot.core.state import RobotState
from edge_robot.coordination.priority import PriorityCalculator
from edge_robot.coordination.conflict import ConflictDetector, ConflictResolver


class TestCoordination(unittest.TestCase):
    def test_priority_calculation(self):
        p_idle = PriorityCalculator.calculate_priority(task_priority=50, waiting_time_s=0.0, battery_percent=100.0)
        p_waited = PriorityCalculator.calculate_priority(task_priority=50, waiting_time_s=10.0, battery_percent=100.0)
        self.assertGreater(p_waited, p_idle)

    def test_same_next_node_conflict_resolution(self):
        robot_a = RobotState(
            robot_id="AMR-01",
            position=(1.0, 2.0),
            next_node=(2, 2),
            priority=70.0,
        )
        robot_b = RobotState(
            robot_id="AMR-02",
            position=(3.0, 2.0),
            next_node=(2, 2),
            priority=50.0,
        )

        conflicts = ConflictDetector.detect_conflicts(
            self_state=robot_a,
            peer_states={"AMR-02": robot_b},
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, "SAME_NEXT_NODE")

        res_a = ConflictResolver.resolve_conflict(robot_a.robot_id, conflicts[0])
        self.assertEqual(res_a.action, ConflictAction.PROCEED)
        self.assertEqual(res_a.winner_id, "AMR-01")

        conflicts_b = ConflictDetector.detect_conflicts(
            self_state=robot_b,
            peer_states={"AMR-01": robot_a},
        )
        res_b = ConflictResolver.resolve_conflict(robot_b.robot_id, conflicts_b[0])
        self.assertEqual(res_b.action, ConflictAction.YIELD)
        self.assertEqual(res_b.winner_id, "AMR-01")

    def test_head_on_swap_conflict(self):
        robot_a = RobotState(
            robot_id="AMR-01",
            position=(1.0, 2.0),
            next_node=(2, 2),
            priority=60.0,
        )
        robot_b = RobotState(
            robot_id="AMR-02",
            position=(2.0, 2.0),
            next_node=(1, 2),
            priority=40.0,
        )

        conflicts_b = ConflictDetector.detect_conflicts(
            self_state=robot_b,
            peer_states={"AMR-01": robot_a},
        )
        self.assertEqual(len(conflicts_b), 1)
        self.assertEqual(conflicts_b[0].conflict_type, "HEAD_ON_SWAP")

        res_b = ConflictResolver.resolve_conflict(robot_b.robot_id, conflicts_b[0])
        self.assertEqual(res_b.action, ConflictAction.REROUTE)


if __name__ == "__main__":
    unittest.main()
