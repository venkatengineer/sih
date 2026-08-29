"""
Unit tests for A* planning.
"""

import unittest
from edge_robot.world.map import LocalWorldModel
from edge_robot.planning.astar import astar_search


class TestAStar(unittest.TestCase):
    def test_astar_simple_path(self):
        world = LocalWorldModel(width=10, height=10)
        start = (1, 1)
        goal = (4, 1)

        path = astar_search(start, goal, world)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], (1, 1))
        self.assertEqual(path[-1], (4, 1))
        self.assertEqual(len(path), 4)

    def test_astar_around_obstacle(self):
        static_obstacles = [(2, 0), (2, 1), (2, 2), (2, 3)]
        world = LocalWorldModel(width=10, height=10, static_obstacles=static_obstacles)

        start = (1, 1)
        goal = (3, 1)

        path = astar_search(start, goal, world)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], goal)
        self.assertTrue(any(node[1] >= 4 for node in path))

    def test_astar_no_path(self):
        static_obstacles = [(0, 1), (1, 0), (2, 1), (1, 2)]
        world = LocalWorldModel(width=5, height=5, static_obstacles=static_obstacles)

        path = astar_search((1, 1), (4, 4), world)
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
