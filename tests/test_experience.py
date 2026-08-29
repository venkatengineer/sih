"""
Unit tests for Experience Store.
"""

import unittest
from edge_robot.learning.experience import ExperienceStore, TripRecord


class TestExperience(unittest.TestCase):
    def test_experience_learning_and_edge_costs(self):
        store = ExperienceStore("AMR-01")

        trip1 = TripRecord(
            trip_id="trip-1",
            robot_id="AMR-01",
            start_node=(1, 1),
            goal_node=(1, 3),
            path=[(1, 1), (1, 2), (1, 3)],
            distance=2.0,
            travel_time_s=10.0,
            waiting_time_s=0.0,
            obstacles_encountered=0,
            reroutes_count=0,
        )
        store.record_trip(trip1)

        time_cost = store.get_edge_travel_time((1, 1), (1, 2))
        self.assertEqual(time_cost, 5.0)

        stats = store.get_route_statistics()
        self.assertEqual(stats["total_trips"], 1)
        self.assertEqual(stats["avg_travel_time_s"], 10.0)


if __name__ == "__main__":
    unittest.main()
