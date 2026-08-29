"""
Unit and Integration Test Suite for Decentralized Congestion-Aware Least-Time Path Selection.
Implements 10 mandatory test scenarios specified in section 20 of requirements.
"""

import unittest
import time
from typing import List

from config import RobotConfig
from world.grid_map import GridMap, Point
from world.world_model import LocalWorldModel
from learning.experience import ExperienceStore
from planning.planner import RoutePlanner
from planning.astar import AStarPlanner
from coordination.safety import SafetyController
from agent.amr_agent import AMRAgent

class TestCongestionAwarePathSelection(unittest.TestCase):

    def setUp(self):
        self.grid = GridMap(width=30, height=30, cell_size=1.0)
        self.config = RobotConfig(robot_id="AMR-05", reroute_improvement_threshold=0.10)
        self.experience_store = ExperienceStore()
        self.safety = SafetyController(self.config)
        self.planner = RoutePlanner(
            grid_map=self.grid,
            config=self.config,
            experience_store=self.experience_store,
            safety_checker=self.safety
        )
        self.world_model = LocalWorldModel(self.grid, robot_id="AMR-05")

    # --- Test 1: Low Congestion ---
    def test_01_low_congestion(self):
        """Current route = 40s, Alternate = 50s -> Expected: CONTINUE"""
        # Define current route: 10 steps (10m) = 10s base time
        current_route = [(0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5), (6, 5), (7, 5), (8, 5), (9, 5), (10, 5)]
        
        # Alternate route: longer path 15 steps (15m) = 15s base time
        start = (0, 5)
        goal = (10, 5)

        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        self.assertIn(res["decision"], ["CONTINUE", "NO_ALTERNATE"])

    # --- Test 2: Heavy Congestion ---
    def test_02_heavy_congestion(self):
        """Current route heavily congested (80s estimated), Alternate clear (45s) -> Expected: REROUTE"""
        start = (0, 5)
        goal = (10, 5)
        
        # Path A (Current): Straight corridor along y=5
        current_route = [(x, 5) for x in range(11)]
        
        # Add 6 peer robots along Path A to simulate heavy crowding
        for i in range(6):
            peer_id = f"AMR-0{i+1}"
            self.world_model.update_peer(
                robot_id=peer_id,
                position=(5, 5),
                current_path=[(x, 5) for x in range(11)]
            )

        # Allow planner to evaluate
        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        self.assertEqual(res["decision"], "REROUTE")

    # --- Test 3: No Alternate ---
    def test_03_no_alternate(self):
        """Current route congested, but wall blocks all alternate routes -> Expected: CONTINUE or NO_ALTERNATE"""
        start = (0, 5)
        goal = (10, 5)
        current_route = [(x, 5) for x in range(11)]

        # Block all surrounding cells (y=4 and y=6) with static obstacles
        for x in range(30):
            if (x, 4) != start and (x, 4) != goal:
                self.grid.set_obstacle(x, 4, True)
            if (x, 6) != start and (x, 6) != goal:
                self.grid.set_obstacle(x, 6, True)

        # Add heavy peer crowding on current route
        for i in range(5):
            self.world_model.update_peer(f"AMR-0{i+1}", position=(5, 5), current_path=current_route)

        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        self.assertIn(res["decision"], ["CONTINUE", "NO_ALTERNATE"])
        self.assertIsNotNone(res["best_route"])

    # --- Test 4: Small Improvement Below Threshold ---
    def test_04_small_improvement(self):
        """Current route = 60s, Alternate = 58s, Threshold = 10% -> Expected: CONTINUE"""
        self.config.reroute_improvement_threshold = 0.10  # 10% required
        
        current_route = [(x, 5) for x in range(11)]
        start = (0, 5)
        goal = (10, 5)

        # Add minor congestion on current route (2 robots)
        self.world_model.update_peer("AMR-01", position=(4, 5))
        self.world_model.update_peer("AMR-02", position=(5, 5))

        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        self.assertEqual(res["decision"], "CONTINUE")

    # --- Test 5: Significant Improvement Above Threshold ---
    def test_05_significant_improvement(self):
        """Current route = 60s, Alternate = 40s (33% faster), Threshold = 10% -> Expected: REROUTE"""
        self.config.reroute_improvement_threshold = 0.10
        
        start = (0, 5)
        goal = (10, 5)
        current_route = [(x, 5) for x in range(11)]

        # Heavy congestion on current route (5 robots)
        for i in range(5):
            self.world_model.update_peer(f"AMR-0{i+1}", position=(5, 5), current_path=current_route)

        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        self.assertEqual(res["decision"], "REROUTE")

    # --- Test 6: Robot Already Waiting (Wait vs Reroute) ---
    def test_06_robot_already_waiting(self):
        """Robot waiting 15s at congested intersection compares remaining wait+travel vs reroute overhead+alternate"""
        start = (5, 5)
        goal = (15, 5)
        current_route = [(x, 5) for x in range(5, 16)]

        # Simulate heavy congestion ahead on current route
        for i in range(6):
            self.world_model.update_peer(f"AMR-0{i+1}", position=(8, 5), current_path=current_route)

        # Evaluate with 15 seconds already waited
        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model,
            already_waited_time=15.0
        )

        self.assertEqual(res["decision"], "REROUTE")

    # --- Test 7: Predictive Congestion ---
    def test_07_predictive_congestion(self):
        """AMR-05 approaches corridor already planned by 4 peers. Detects incoming intent and reroutes early."""
        start = (0, 10)
        goal = (20, 10)
        current_route = [(x, 10) for x in range(21)]

        # Peers are NOT at the corridor yet, but publish PLANNED_PATH intent over (5, 10) -> (15, 10)
        corridor_intent = [(x, 10) for x in range(21)]
        for i in range(4):
            self.world_model.update_peer(
                robot_id=f"AMR-0{i+1}",
                position=(0, 0),  # Currently far away
                planned_path=corridor_intent
            )

        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        # Predictive congestion estimator detects 4 incoming path intents
        self.assertEqual(res["decision"], "REROUTE")

    # --- Test 8: Congestion Clears & Cooldown Anti-Oscillation ---
    def test_08_congestion_clears_cooldown(self):
        """Verify that after rerouting, route change respects cooldown period to prevent rapid oscillation."""
        start = (0, 5)
        goal = (10, 5)
        current_route = [(x, 5) for x in range(11)]

        # Trigger initial reroute
        for i in range(5):
            self.world_model.update_peer(f"AMR-0{i+1}", position=(5, 5), current_path=current_route)

        res1 = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        self.assertEqual(res1["decision"], "REROUTE")

        # Immediately call select_best_route again within cooldown window
        res2 = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=res1["best_route"],
            current_index=0,
            world_model=self.world_model
        )

        # Should CONTINUE on newly selected route due to active cooldown
        self.assertEqual(res2["decision"], "CONTINUE")

    # --- Test 9: Safety Override ---
    def test_09_safety_override(self):
        """Even if alternate route is faster, if alternate routes contain obstacles/hazards -> DO NOT REROUTE"""
        start = (0, 5)
        goal = (10, 5)
        current_route = [(x, 5) for x in range(11)]

        # Heavy congestion on current route
        for i in range(5):
            self.world_model.update_peer(f"AMR-0{i+1}", position=(5, 5), current_path=current_route)

        # Block ALL alternate rows (y=0..4, 6..29) with dynamic hazard obstacles
        for x in range(30):
            for y in range(30):
                if y != 5:
                    self.grid.set_dynamic_obstacle(x, y, True)

        res = self.planner.select_best_route(
            start=start,
            goal=goal,
            current_route=current_route,
            current_index=0,
            world_model=self.world_model
        )

        # Safety controller invalidates unsafe alternate route
        self.assertIn(res["decision"], ["CONTINUE", "NO_ALTERNATE"])

    # --- Test 10: Three-Robot Decentralized P2P Integration Scenario ---
    def test_10_three_robot_decentralized(self):
        """Simulate 3 independent AMRs sharing peer telemetry via P2P callbacks without central server."""
        cfg1 = RobotConfig(robot_id="AMR-01")
        cfg2 = RobotConfig(robot_id="AMR-02")
        cfg3 = RobotConfig(robot_id="AMR-03")

        agent1 = AMRAgent(cfg1, self.grid)
        agent2 = AMRAgent(cfg2, self.grid)
        agent3 = AMRAgent(cfg3, self.grid)

        # Interconnect P2P in memory
        def wire(src, tgt):
            old_bc = src.p2p.broadcast
            def bc_wrapper(msg):
                old_bc(msg)
                tgt._handle_p2p_message(msg)
            src.p2p.broadcast = bc_wrapper

        wire(agent1, agent2)
        wire(agent1, agent3)
        wire(agent2, agent1)
        wire(agent2, agent3)
        wire(agent3, agent1)
        wire(agent3, agent2)

        # Assign goals
        agent1.current_position = (0, 5)
        agent1.set_navigation_goal((10, 5))

        agent2.current_position = (1, 5)
        agent2.set_navigation_goal((10, 5))

        agent3.current_position = (0, 4)
        agent3.set_navigation_goal((10, 5))

        # Execute 1 step for each agent
        res1 = agent1.step()
        res2 = agent2.step()
        res3 = agent3.step()

        # Verify peer tables updated via P2P
        self.assertIn("AMR-02", agent1.world_model.peers)
        self.assertIn("AMR-03", agent1.world_model.peers)
        self.assertIn("AMR-01", agent2.world_model.peers)

if __name__ == "__main__":
    unittest.main()
