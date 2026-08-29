"""
Unit tests for Task Manager and Decentralized Bidding.
"""

import unittest
from edge_robot.tasks.task import Task, TaskBid
from edge_robot.tasks.task_manager import TaskManager


class TestTaskManager(unittest.TestCase):
    def test_task_bidding_auction(self):
        tm1 = TaskManager("AMR-01")
        tm2 = TaskManager("AMR-02")

        task = Task(task_id="T-100", pickup=(2.0, 2.0), destination=(10.0, 10.0), priority=50)

        # Robot 1 is close to pickup (1, 1) -> low cost
        bid1 = tm1.create_bid(task, current_position=(1.0, 1.0), battery_percent=95.0)

        # Robot 2 is far from pickup (15, 15) -> high cost
        bid2 = tm2.create_bid(task, current_position=(15.0, 15.0), battery_percent=95.0)

        self.assertLess(bid1.cost, bid2.cost)

        # Both robots record each other's bids
        tm1.record_bid(bid2)
        tm2.record_bid(bid1)

        winner1 = tm1.evaluate_auction("T-100")
        winner2 = tm2.evaluate_auction("T-100")

        # Both independently arrive at the exact same winning robot
        self.assertEqual(winner1, "AMR-01")
        self.assertEqual(winner2, "AMR-01")


if __name__ == "__main__":
    unittest.main()
