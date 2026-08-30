#!/usr/bin/env python3
"""
===============================================================================
CONTINUOUS WAREHOUSE FLEET TRAFFIC SIMULATOR
===============================================================================
Dispatches continuous shelf-to-shelf tasks to the decentralized AMR fleet.
Demonstrates multi-robot pick-and-place, cargo attachment, and autonomous
intersection conflict avoidance in Godot and Web Mission Control.
"""

import asyncio
import json
import random
import time
import urllib.request

SHELVE_IDS = [
    "SHELF-01", "SHELF-02", "SHELF-03", "SHELF-04",
    "SHELF-05", "SHELF-06", "SHELF-07", "SHELF-08",
    "SHELF-09", "SHELF-10", "SHELF-11", "SHELF-12",
    "SHELF-13", "SHELF-14", "SHELF-15", "SHELF-16",
]

# Curated intersecting task pairs that create exciting aisle conflicts
INTERSECTING_PAIRS = [
    ("SHELF-02", "SHELF-10", "HIGH"),     # West to East along Central Aisle
    ("SHELF-07", "SHELF-05", "NORMAL"),   # South to North intersecting Central Aisle
    ("SHELF-14", "SHELF-03", "HIGH"),     # East to West along Main Crossway
    ("SHELF-06", "SHELF-15", "NORMAL"),   # Cross-docking route
    ("SHELF-01", "SHELF-12", "URGENT"),   # Long diagonal delivery
    ("SHELF-08", "SHELF-04", "NORMAL"),
    ("SHELF-11", "SHELF-02", "HIGH"),
    ("SHELF-13", "SHELF-07", "NORMAL"),
]


def post_task(src: str, dst: str, priority: str, cargo: str = "PALLET-BOX-AUTO-PARTS"):
    url = "http://localhost:8000/api/tasks"
    payload = {
        "source_shelf": src,
        "destination_shelf": dst,
        "priority": priority,
        "cargo_item": cargo,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=3) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception as e:
        print(f"[SIMULATOR] Error posting task: {e}")
        return None


def get_fleet_status():
    url = "http://localhost:8000/api/fleet"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as res:
            return json.loads(res.read().decode("utf-8"))
    except Exception:
        return None


async def run_traffic_simulation():
    print("\n" + "=" * 76)
    print("🏭 STARTING CONTINUOUS WAREHOUSE TRAFFIC SIMULATION")
    print("=" * 76)
    print("• Dispatches continuous multi-AMR intersecting delivery missions.")
    print("• Watch Godot 3D Twin & Web Mission Control for live collision avoidance!")
    print("• Press Ctrl+C at any time to stop.")
    print("-" * 76 + "\n")

    task_idx = 0

    # Initial burst: dispatch two intersecting tasks simultaneously
    print("⚡ Dispatching Initial Intersecting Conflict Pair...")
    post_task("SHELF-02", "SHELF-10", "HIGH", "CARGO-ENGINE-BLOCKS")
    time.sleep(0.5)
    post_task("SHELF-07", "SHELF-05", "NORMAL", "CARGO-BRAKE-ASSEMBLY")
    print("✅ Dispatched Task 1 (S-02 -> S-10) & Task 2 (S-07 -> S-05) -> AMRs Moving!\n")

    while True:
        await asyncio.sleep(8.0)
        task_idx = (task_idx + 1) % len(INTERSECTING_PAIRS)
        pair = INTERSECTING_PAIRS[task_idx]

        status = get_fleet_status()
        if status and "fleet" in status:
            moving_count = sum(1 for r in status["fleet"] if r.get("status") in ("MOVING", "YIELDING"))
            print(f"[T+{time.strftime('%H:%M:%S')}] Fleet Status: {moving_count} AMRs Active | Dispatched: {pair[0]} ➔ {pair[1]} ({pair[2]})")

        post_task(pair[0], pair[1], pair[2], f"CARGO-BATCH-{task_idx+100}")


if __name__ == "__main__":
    try:
        asyncio.run(run_traffic_simulation())
    except KeyboardInterrupt:
        print("\n[SIMULATOR] Simulation stopped.")
