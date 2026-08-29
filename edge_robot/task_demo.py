"""
CLI Task Demo for Decentralized Multi-AMR Task Allocation.
Executes an end-to-end task auction scenario with 3 independent edge robots over P2P UDP.

Usage:
    python3 -m edge_robot.task_demo
"""

import asyncio
import sys
import time

from edge_robot.config import RobotConfig
from edge_robot.core.robot import RobotAgent
from edge_robot.core.enums import TaskPriority


async def run_task_demo():
    print("=" * 72)
    print("🤖 DECENTRALIZED MULTI-AMR TASK ALLOCATION & AUCTION DEMO")
    print("=" * 72)
    print("Scenario:")
    print("  • 3 Independent Robots: AMR-01, AMR-02, AMR-03 (P2P UDP)")
    print("  • Zero central task server / Zero global scheduler")
    print("  • Task T-001: Pickup [4, 3] ➔ Dropoff [18, 8] (Priority: HIGH)")
    print("=" * 72)

    common_peers = [("127.0.0.1", 5901), ("127.0.0.1", 5902), ("127.0.0.1", 5903)]

    # 1. Initialize 3 independent robots
    cfg1 = RobotConfig(
        robot_id="AMR-01",
        initial_position=(2.0, 10.0),
        network_port=5901,
        peer_endpoints=common_peers,
        static_obstacles=[],
        loop_rate_hz=20.0,
        max_speed=2.0,
    )
    cfg2 = RobotConfig(
        robot_id="AMR-02",
        initial_position=(5.0, 4.0),  # Closest to pickup (4, 3)!
        network_port=5902,
        peer_endpoints=common_peers,
        static_obstacles=[],
        loop_rate_hz=20.0,
        max_speed=2.0,
    )
    cfg3 = RobotConfig(
        robot_id="AMR-03",
        initial_position=(20.0, 15.0),  # Far from pickup
        network_port=5903,
        peer_endpoints=common_peers,
        static_obstacles=[],
        loop_rate_hz=20.0,
        max_speed=2.0,
    )

    agent1 = RobotAgent(cfg1)
    agent2 = RobotAgent(cfg2)
    agent3 = RobotAgent(cfg3)

    print("\n[1/4] Starting independent AMR Edge Nodes...")
    await agent1.start()
    await agent2.start()
    await agent3.start()
    print("  ✅ AMR-01 Node active (pos=[2, 10], UDP=5901)")
    print("  ✅ AMR-02 Node active (pos=[5, 4],  UDP=5902)")
    print("  ✅ AMR-03 Node active (pos=[20, 15], UDP=5903)")

    # Wait for initial P2P discovery
    await asyncio.sleep(0.5)

    print("\n[2/4] Broadcasting Task Announcement from AMR-01 over P2P...")
    task = agent1.submit_task(
        pickup=(4, 3),
        dropoff=(18, 8),
        priority=TaskPriority.HIGH.value,
        task_id="T-001",
    )
    print(f"  📢 TASK ANNOUNCED: {task.task_id} (Pickup={task.pickup}, Dropoff={task.dropoff}, Priority=HIGH)")

    # Allow bidding window
    await asyncio.sleep(1.0)

    print("\n[3/4] Collecting Received Bids across Fleet:")
    auction1 = agent1.task_manager.auction_manager.get_auction("T-001")
    if auction1 and auction1.bids:
        for r_id, bid in sorted(auction1.bids.items()):
            print(f"  💰 {r_id} ➔ Cost: {bid.cost:5.2f} | Dist: {bid.distance:4.1f}m | Battery: {bid.battery:4.1f}% | Time: {bid.estimated_time:4.1f}s")

    print("\n[4/4] Deterministic Consensus Verification:")
    t1 = agent1.task_manager.get_task("T-001")
    t2 = agent2.task_manager.get_task("T-001")
    t3 = agent3.task_manager.get_task("T-001")

    w1 = t1.assigned_robot if t1 else None
    w2 = t2.assigned_robot if t2 else None
    w3 = t3.assigned_robot if t3 else None

    print(f"  • AMR-01 Local Decision: Winner = {w1}")
    print(f"  • AMR-02 Local Decision: Winner = {w2}")
    print(f"  • AMR-03 Local Decision: Winner = {w3}")

    if w1 == w2 == w3 and w1 == "AMR-02":
        print(f"\n🎉 SUCCESS: All 3 AMRs independently agreed on winner [{w1}] without a central server!")
        active_task = agent2.task_manager.get_active_task()
        if active_task:
            print(f"  🚀 AMR-02 has accepted {active_task.task_id} and initiated autonomous execution.")
    else:
        print("\n⚠️ Consensus mismatch:", w1, w2, w3)

    print("=" * 72)
    print("🛑 Shutting down demo nodes...")
    await agent1.stop()
    await agent2.stop()
    await agent3.stop()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(run_task_demo())
