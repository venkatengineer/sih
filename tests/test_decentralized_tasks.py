"""
Comprehensive Unit & Integration Test Suite for Decentralized Multi-AMR Task System.
Tests task models, bidding formulas, deterministic auction consensus, P2P network exchanges,
offline peer failure recovery, and dynamic route blockage.
"""

import unittest
import asyncio
import time
from typing import List, Tuple

from edge_robot.core.enums import TaskStatus, TaskPriority, RobotStatus
from edge_robot.config import RobotConfig
from edge_robot.core.robot import RobotAgent
from edge_robot.tasks.task import Task
from edge_robot.tasks.bid import TaskBid
from edge_robot.tasks.cost import BidCostCalculator
from edge_robot.tasks.auction import AuctionManager
from edge_robot.tasks.task_manager import TaskManager
from edge_robot.world.map import LocalWorldModel
from edge_robot.world.obstacle import LocalObstacle
from edge_robot.planning.planner import PathPlanner
from edge_robot.learning.experience import ExperienceStore, TripRecord


class TestDecentralizedTasks(unittest.TestCase):
    def setUp(self):
        self.world = LocalWorldModel(width=25, height=20, static_obstacles=[])
        self.planner = PathPlanner(self.world)
        self.exp_store = ExperienceStore("AMR-01")
        self.cost_calc = BidCostCalculator(
            planner=self.planner,
            world=self.world,
            experience_store=self.exp_store,
            distance_weight=1.0,
            congestion_weight=5.0,
            workload_weight=3.0,
            battery_weight=2.0,
            experience_weight=2.0,
            minimum_task_battery=20.0,
        )

    # =========================================================================
    # 1. Task Model Tests
    # =========================================================================

    def test_task_model_and_transitions(self):
        task = Task(
            task_id="T-001",
            pickup=(4, 3),
            dropoff=(18, 8),
            priority=TaskPriority.HIGH.value,
        )
        self.assertEqual(task.status, TaskStatus.CREATED)
        self.assertEqual(task.destination, (18, 8))

        # Transition: CREATED -> AUCTIONING -> ASSIGNED -> IN_PROGRESS -> PICKED_UP -> COMPLETED
        task.transition_to(TaskStatus.AUCTIONING)
        self.assertEqual(task.status, TaskStatus.AUCTIONING)

        task.assigned_robot = "AMR-02"
        task.transition_to(TaskStatus.ASSIGNED)
        self.assertEqual(task.status, TaskStatus.ASSIGNED)

        task.transition_to(TaskStatus.IN_PROGRESS)
        self.assertIsNotNone(task.started_at)

        task.transition_to(TaskStatus.PICKED_UP)
        self.assertIsNotNone(task.picked_up_at)

        task.transition_to(TaskStatus.COMPLETED)
        self.assertIsNotNone(task.completed_at)

        # JSON round-trip
        data = task.to_dict()
        reconstructed = Task.from_dict(data)
        self.assertEqual(reconstructed.task_id, "T-001")
        self.assertEqual(reconstructed.pickup, (4, 3))
        self.assertEqual(reconstructed.dropoff, (18, 8))
        self.assertEqual(reconstructed.status, TaskStatus.COMPLETED)
        self.assertEqual(reconstructed.assigned_robot, "AMR-02")

    # =========================================================================
    # 2. TaskBid Model Tests
    # =========================================================================

    def test_task_bid_serialization(self):
        bid = TaskBid(
            task_id="T-001",
            robot_id="AMR-02",
            cost=18.4,
            auction_round=1,
            estimated_time=42.0,
            distance=31.0,
            battery=86.0,
            congestion=0.2,
            workload=0,
            is_valid=True,
        )
        d = bid.to_dict()
        self.assertEqual(d["cost"], 18.4)
        self.assertEqual(d["robot_id"], "AMR-02")

        bid_rec = TaskBid.from_dict(d)
        self.assertEqual(bid_rec.task_id, "T-001")
        self.assertEqual(bid_rec.cost, 18.4)
        self.assertTrue(bid_rec.is_valid)

    # =========================================================================
    # 3. Cost Calculation Tests
    # =========================================================================

    def test_cost_calculation_distance_and_battery(self):
        task = Task(task_id="T-101", pickup=(5, 5), dropoff=(10, 5))

        # Robot 1: close to pickup (4, 5), full battery (95%)
        bid1 = self.cost_calc.calculate_bid(
            task=task,
            robot_id="AMR-01",
            current_position=(4.0, 5.0),
            battery_percent=95.0,
        )
        self.assertTrue(bid1.is_valid)
        self.assertAlmostEqual(bid1.distance, 6.0)

        # Robot 2: far from pickup (20, 5), full battery (95%)
        bid2 = self.cost_calc.calculate_bid(
            task=task,
            robot_id="AMR-02",
            current_position=(20.0, 5.0),
            battery_percent=95.0,
        )
        self.assertTrue(bid2.is_valid)
        self.assertGreater(bid2.cost, bid1.cost)

        # Robot 3: close to pickup (4, 5), but low battery (15% < 20% minimum)
        bid3 = self.cost_calc.calculate_bid(
            task=task,
            robot_id="AMR-03",
            current_position=(4.0, 5.0),
            battery_percent=15.0,
        )
        self.assertFalse(bid3.is_valid)
        self.assertEqual(bid3.cost, float("inf"))

    def test_cost_calculation_workload_and_experience(self):
        task = Task(task_id="T-102", pickup=(5, 5), dropoff=(10, 5))

        # Free robot vs busy robot (workload penalty)
        bid_free = self.cost_calc.calculate_bid(
            task=task,
            robot_id="AMR-01",
            current_position=(5.0, 5.0),
            battery_percent=90.0,
            active_task_count=0,
        )
        bid_busy = self.cost_calc.calculate_bid(
            task=task,
            robot_id="AMR-02",
            current_position=(5.0, 5.0),
            battery_percent=90.0,
            active_task_count=1,
        )
        self.assertGreater(bid_busy.cost, bid_free.cost)

        # Historical obstacle encounter increases experience cost
        for _ in range(5):
            self.exp_store.record_obstacle_encounter((7, 5))

        bid_exp = self.cost_calc.calculate_bid(
            task=task,
            robot_id="AMR-01",
            current_position=(5.0, 5.0),
            battery_percent=90.0,
            active_task_count=0,
        )
        self.assertGreater(bid_exp.cost, bid_free.cost)

    # =========================================================================
    # 4. Deterministic Auction Resolution Tests
    # =========================================================================

    def test_auction_deterministic_winner_and_tie_breaker(self):
        auction_mgr = AuctionManager(default_timeout_seconds=0.5)
        task = Task(task_id="T-201", pickup=(4, 3), dropoff=(18, 8))
        auction_mgr.start_auction(task, auction_round=1)

        # Case 1: Distinct costs -> lowest cost wins
        auction_mgr.record_bid(TaskBid(task_id="T-201", robot_id="AMR-01", cost=25.2, auction_round=1))
        auction_mgr.record_bid(TaskBid(task_id="T-201", robot_id="AMR-02", cost=17.8, auction_round=1))
        auction_mgr.record_bid(TaskBid(task_id="T-201", robot_id="AMR-03", cost=21.4, auction_round=1))

        winner, winning_bid = auction_mgr.evaluate_winner("T-201")
        self.assertEqual(winner, "AMR-02")
        self.assertEqual(winning_bid.cost, 17.8)

        # Case 2: Exact tie between AMR-02 and AMR-01 -> AMR-01 wins lexicographically
        auction_mgr.start_auction(task, auction_round=2)
        auction_mgr.record_bid(TaskBid(task_id="T-201", robot_id="AMR-02", cost=18.0, auction_round=2))
        auction_mgr.record_bid(TaskBid(task_id="T-201", robot_id="AMR-01", cost=18.0, auction_round=2))

        winner_tie, _ = auction_mgr.evaluate_winner("T-201")
        self.assertEqual(winner_tie, "AMR-01")

        # Case 3: Stale bid from Round 1 ignored when auction is in Round 2
        recorded_stale = auction_mgr.record_bid(
            TaskBid(task_id="T-201", robot_id="AMR-03", cost=10.0, auction_round=1)
        )
        self.assertFalse(recorded_stale)

    # =========================================================================
    # 5. Full P2P Multi-Agent Task Auction over UDP
    # =========================================================================

    def test_three_robot_p2p_auction_and_execution(self):
        async def _run():
            common_peers = [("127.0.0.1", 5801), ("127.0.0.1", 5802), ("127.0.0.1", 5803)]

            # AMR-01: Position (2, 2)
            cfg1 = RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 2.0),
                network_port=5801,
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
                max_speed=2.0,
            )
            # AMR-02: Position (5, 5) -> Closest to pickup (4, 4)!
            cfg2 = RobotConfig(
                robot_id="AMR-02",
                initial_position=(5.0, 5.0),
                network_port=5802,
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
                max_speed=2.0,
            )
            # AMR-03: Position (20, 15) -> Far from pickup
            cfg3 = RobotConfig(
                robot_id="AMR-03",
                initial_position=(20.0, 15.0),
                network_port=5803,
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
                max_speed=2.0,
            )

            agent1 = RobotAgent(cfg1)
            agent2 = RobotAgent(cfg2)
            agent3 = RobotAgent(cfg3)

            await agent1.start()
            await agent2.start()
            await agent3.start()

            try:
                # Wait for peer discovery
                await asyncio.sleep(0.4)

                # Announce task T-001 from AMR-01: pickup (4, 4), dropoff (8, 4)
                agent1.submit_task(pickup=(4, 4), dropoff=(8, 4), priority=TaskPriority.HIGH.value, task_id="T-001")

                # Allow bidding and auction finalization over UDP
                await asyncio.sleep(1.2)

                # Winner must be AMR-02 across all 3 independent nodes
                t1 = agent1.task_manager.get_task("T-001")
                t2 = agent2.task_manager.get_task("T-001")
                t3 = agent3.task_manager.get_task("T-001")

                self.assertIsNotNone(t1)
                self.assertIsNotNone(t2)
                self.assertIsNotNone(t3)

                self.assertEqual(t1.assigned_robot, "AMR-02")
                self.assertEqual(t2.assigned_robot, "AMR-02")
                self.assertEqual(t3.assigned_robot, "AMR-02")

            finally:
                await agent1.stop()
                await agent2.stop()
                await agent3.stop()

        asyncio.run(_run())

    # =========================================================================
    # 6. Fault Tolerance: Offline Peer Re-Auction
    # =========================================================================

    def test_offline_peer_task_recovery_and_re_auction(self):
        async def _run():
            common_peers = [("127.0.0.1", 5811), ("127.0.0.1", 5812), ("127.0.0.1", 5813)]

            # AMR-01 at (2, 10) - distance to pickup (4, 3) is 9
            agent1 = RobotAgent(RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 10.0),
                network_port=5811,
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
            ))
            # AMR-02 at (5.0, 4.0) - closest to pickup (4, 3) (distance 2)
            agent2 = RobotAgent(RobotConfig(
                robot_id="AMR-02",
                initial_position=(5.0, 4.0),
                network_port=5812,
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
            ))
            # AMR-03 at (20.0, 15.0) - far from pickup (4, 3) (distance 26)
            agent3 = RobotAgent(RobotConfig(
                robot_id="AMR-03",
                initial_position=(20.0, 15.0),
                network_port=5813,
                peer_endpoints=common_peers,
                static_obstacles=[],
                loop_rate_hz=20.0,
            ))

            await agent1.start()
            await agent2.start()
            await agent3.start()

            try:
                await asyncio.sleep(0.4)

                # Announce task T-999: pickup (4, 3), dropoff (18, 8)
                agent1.submit_task(pickup=(4, 3), dropoff=(18, 8), task_id="T-999")
                await asyncio.sleep(1.2)

                # AMR-02 won Round 1
                t2 = agent2.task_manager.get_task("T-999")
                self.assertIsNotNone(t2)
                self.assertEqual(t2.assigned_robot, "AMR-02")

                # Now AMR-02 crashes/stops
                await agent2.stop()

                # Simulate peer timeout detection on AMR-01 & AMR-03
                reassigned1 = agent1.task_manager.handle_peer_offline("AMR-02")
                reassigned3 = agent3.task_manager.handle_peer_offline("AMR-02")

                self.assertEqual(len(reassigned1), 1)
                self.assertEqual(reassigned1[0].task_id, "T-999")
                self.assertEqual(reassigned1[0].auction_round, 2)

                # Trigger round 2 re-auction
                agent1.task_manager.announce_task(reassigned1[0], auction_round=2)
                agent3.task_manager.announce_task(reassigned3[0], auction_round=2)

                # Both bid in round 2
                _, bid1 = agent1.task_manager.handle_task_announcement(
                    task_dict=reassigned1[0].to_dict(),
                    auction_round=2,
                    current_position=agent1.state.position,
                    battery_percent=agent1.state.battery,
                )
                _, bid3 = agent3.task_manager.handle_task_announcement(
                    task_dict=reassigned3[0].to_dict(),
                    auction_round=2,
                    current_position=agent3.state.position,
                    battery_percent=agent3.state.battery,
                )

                agent1.task_manager.handle_incoming_bid(bid3.to_dict())
                agent3.task_manager.handle_incoming_bid(bid1.to_dict())

                winner1, _ = agent1.task_manager.finalize_auction("T-999")
                winner3, _ = agent3.task_manager.finalize_auction("T-999")

                # AMR-01 is closer to pickup (dist 9 vs 26) -> AMR-01 wins Round 2!
                self.assertEqual(winner1, "AMR-01")
                self.assertEqual(winner3, "AMR-01")

            finally:
                await agent1.stop()
                await agent3.stop()

        asyncio.run(_run())

    # =========================================================================
    # 7. Dynamic Route Blockage & Re-Auction
    # =========================================================================

    def test_dynamic_route_blockage_releases_task(self):
        agent = RobotAgent(RobotConfig(
            robot_id="AMR-01",
            initial_position=(2.0, 2.0),
            static_obstacles=[],
            loop_rate_hz=20.0,
        ))

        task = Task(task_id="T-BLK", pickup=(5, 2), dropoff=(10, 2))
        agent.assign_task(task)
        self.assertEqual(agent.task_manager.get_active_task().task_id, "T-BLK")

        # Place insurmountable wall blocking path to pickup
        for y in range(20):
            agent.world.add_obstacle(LocalObstacle(
                obstacle_id=f"wall-{y}",
                obstacle_type="WALL",
                position=(3.0, float(y)),
                radius=0.5,
            ))

        # Planning fails -> triggers task failure and release
        agent.plan_if_required()
        self.assertIsNone(agent.task_manager.get_active_task())
        self.assertEqual(len(agent.task_manager.failed_tasks), 1)
        self.assertEqual(agent.task_manager.failed_tasks[0].status, TaskStatus.FAILED)
        self.assertEqual(agent.task_manager.failed_tasks[0].auction_round, 2)


if __name__ == "__main__":
    unittest.main()
