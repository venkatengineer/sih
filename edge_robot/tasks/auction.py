"""
AuctionManager - Deterministic Decentralized Task Auction Coordinator.
Collects peer bids, enforces round-based stale message filtering,
and calculates winning allocations identically across all independent nodes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Tuple

from edge_robot.tasks.task import Task
from edge_robot.tasks.bid import TaskBid


@dataclass
class TaskAuction:
    """State tracking for a single task auction round."""
    task_id: str
    auction_round: int
    task: Task
    bids: Dict[str, TaskBid] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    timeout_seconds: float = 1.0
    is_finalized: bool = False
    winner_id: Optional[str] = None
    winning_bid: Optional[TaskBid] = None

    def is_expired(self) -> bool:
        return (time.time() - self.start_time) >= self.timeout_seconds


class AuctionManager:
    """
    Local Auction Manager running onboard each AMR.
    Every robot runs an identical instance to independently reach consensus on task awards.
    """

    def __init__(self, default_timeout_seconds: float = 1.0):
        self.default_timeout_seconds = default_timeout_seconds
        # task_id -> TaskAuction
        self.active_auctions: Dict[str, TaskAuction] = {}

    def start_auction(
        self,
        task: Task,
        auction_round: int = 1,
        timeout_seconds: Optional[float] = None,
    ) -> TaskAuction:
        """Create or restart an auction round for a task."""
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        auction = TaskAuction(
            task_id=task.task_id,
            auction_round=auction_round,
            task=task,
            timeout_seconds=timeout,
            start_time=time.time(),
        )
        self.active_auctions[task.task_id] = auction
        return auction

    def record_bid(self, bid: TaskBid) -> bool:
        """
        Record an incoming bid (local or from a peer).
        Rejects bids from outdated rounds to maintain consensus integrity.
        """
        auction = self.active_auctions.get(bid.task_id)
        if not auction:
            # Create auction container if not existing yet
            temp_task = Task(task_id=bid.task_id, pickup=(0, 0), dropoff=(0, 0), auction_round=bid.auction_round)
            auction = self.start_auction(temp_task, auction_round=bid.auction_round)

        # Stale bid protection: ignore bids from older rounds
        if bid.auction_round < auction.auction_round:
            return False

        # If incoming bid has a higher auction round, update auction round
        if bid.auction_round > auction.auction_round:
            auction.auction_round = bid.auction_round
            auction.bids.clear()
            auction.start_time = time.time()
            auction.is_finalized = False
            auction.winner_id = None
            auction.winning_bid = None

        auction.bids[bid.robot_id] = bid
        return True

    def evaluate_winner(self, task_id: str) -> Tuple[Optional[str], Optional[TaskBid]]:
        """
        Deterministically select the auction winner:
        1. Lowest valid cost wins.
        2. Tie-breaker: lexicographical robot_id (e.g. AMR-01 < AMR-02).
        """
        auction = self.active_auctions.get(task_id)
        if not auction or not auction.bids:
            return None, None

        # Filter valid bids with finite cost
        valid_bids = [
            b for b in auction.bids.values()
            if b.is_valid and b.cost != float("inf")
        ]

        if not valid_bids:
            return None, None

        # Deterministic sort: cost ASC, then robot_id ASC
        sorted_bids = sorted(valid_bids, key=lambda b: (b.cost, b.robot_id))
        winning_bid = sorted_bids[0]
        return winning_bid.robot_id, winning_bid

    def finalize_auction(self, task_id: str) -> Optional[str]:
        """Finalize auction and lock in the winning robot ID."""
        auction = self.active_auctions.get(task_id)
        if not auction:
            return None

        winner_id, winning_bid = self.evaluate_winner(task_id)
        auction.is_finalized = True
        auction.winner_id = winner_id
        auction.winning_bid = winning_bid
        return winner_id

    def get_auction(self, task_id: str) -> Optional[TaskAuction]:
        return self.active_auctions.get(task_id)

    def cancel_auction(self, task_id: str) -> None:
        self.active_auctions.pop(task_id, None)
