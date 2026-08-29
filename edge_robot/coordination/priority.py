"""
Deterministic Priority Calculation and Tie-Breaking for Decentralized Coordination.
Ensures that all AMRs independently reach the exact same precedence ordering.
"""

from __future__ import annotations
from typing import Optional, Tuple


class PriorityCalculator:
    """
    Computes a deterministic priority score for resolving peer conflicts.
    Higher score indicates higher precedence to move through contested space.
    """

    @staticmethod
    def calculate_priority(
        task_priority: int = 50,
        waiting_time_s: float = 0.0,
        battery_percent: float = 100.0,
        distance_to_goal: float = 10.0,
        eta: float = 0.0,
    ) -> float:
        """
        Calculates priority score:
        - Base task priority (1-100)
        - Waiting time bonus (+2.0 points per second spent waiting to prevent starvation)
        - Battery urgency bonus (+25.0 if battery < 20% to reach charging/dropoff)
        - Goal proximity bonus (+0.5 per meter closer to goal)
        """
        # Base task priority
        score = float(task_priority)

        # Starvation prevention: increase priority as waiting time accumulates
        score += min(waiting_time_s * 2.0, 50.0)

        # Battery urgency: low battery robots get elevated priority
        if battery_percent < 20.0:
            score += 25.0
        elif battery_percent < 35.0:
            score += 10.0

        # Goal proximity: closer to goal has slight advantage to clear space
        if distance_to_goal > 0:
            proximity_bonus = max(0.0, 20.0 - distance_to_goal)
            score += proximity_bonus * 0.5

        return round(score, 2)

    @staticmethod
    def compare_precedence(
        self_id: str,
        self_priority: float,
        self_eta: float,
        peer_id: str,
        peer_priority: float,
        peer_eta: float,
    ) -> bool:
        """
        Deterministic precedence evaluation.
        Returns True if self_id has precedence over peer_id, False otherwise.
        
        Precedence Hierarchy:
        1. Higher priority score
        2. Lower ETA (first to arrive at contested zone)
        3. Deterministic lexicographical tie-breaker (e.g. "AMR-01" < "AMR-02")
        """
        if self_priority > peer_priority:
            return True
        elif self_priority < peer_priority:
            return False

        # Priorities are equal: compare ETAs (lower ETA wins)
        if self_eta > 0 and peer_eta > 0 and abs(self_eta - peer_eta) > 0.05:
            return self_eta < peer_eta

        # Deterministic lexicographical tie-breaker: smaller robot_id wins
        return self_id < peer_id
