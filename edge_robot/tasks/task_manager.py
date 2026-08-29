"""
TaskManager - Decentralized Task Manager running onboard each independent AMR.
Coordinates local task execution, bidding, deterministic auction resolution,
fault recovery / peer offline reallocation, and task state progression.
"""

from __future__ import annotations
import logging
import math
import time
from typing import Dict, List, Optional, Tuple, Any, Callable

from edge_robot.core.enums import TaskStatus, TaskPriority, MessageType
from edge_robot.tasks.task import Task
from edge_robot.tasks.bid import TaskBid
from edge_robot.tasks.cost import BidCostCalculator
from edge_robot.tasks.auction import AuctionManager, TaskAuction
from edge_robot.communication.protocol import (
    NetworkMessage,
    create_task_announcement_message,
    create_task_bid_message,
    create_task_award_message,
    create_task_accept_message,
    create_task_release_message,
    create_task_complete_message,
    create_task_failed_message,
)

logger = logging.getLogger("edge_robot.tasks")


class TaskManager:
    """
    Independent Task Manager for a single AMR.
    Zero central coordination — participates in distributed auctions and executes assigned transport jobs.
    """

    def __init__(
        self,
        robot_id: str,
        cost_calculator: Optional[BidCostCalculator] = None,
        auction_manager: Optional[AuctionManager] = None,
        max_active_tasks: int = 1,
    ):
        self.robot_id = robot_id
        self.cost_calculator = cost_calculator or BidCostCalculator()
        self.auction_manager = auction_manager or AuctionManager(default_timeout_seconds=1.0)
        self.max_active_tasks = max_active_tasks

        # Task storage
        self.active_task: Optional[Task] = None
        self.pending_tasks: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.failed_tasks: List[Task] = []
        self.known_tasks: Dict[str, Task] = {}

        # Event hooks for observers / frontend adapters
        self._event_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    # Backward compatibility properties
    @property
    def current_task(self) -> Optional[Task]:
        return self.active_task

    @current_task.setter
    def current_task(self, val: Optional[Task]) -> None:
        self.active_task = val

    @property
    def task_queue(self) -> List[Task]:
        return self.pending_tasks

    @task_queue.setter
    def task_queue(self, val: List[Task]) -> None:
        self.pending_tasks = val

    @property
    def active_auctions(self) -> Dict[str, Dict[str, TaskBid]]:
        result = {}
        for t_id, auction in self.auction_manager.active_auctions.items():
            result[t_id] = auction.bids
        return result

    # =========================================================================
    # Event System
    # =========================================================================

    def on_task_event(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register a callback for task lifecycle events."""
        self._event_callbacks.append(callback)

    def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Emit task event to registered listeners."""
        payload_with_meta = {
            "event": event_name,
            "robot_id": self.robot_id,
            "timestamp": time.time(),
            **payload,
        }
        for cb in self._event_callbacks:
            try:
                cb(event_name, payload_with_meta)
            except Exception as e:
                logger.debug(f"[{self.robot_id}] Error in task event callback: {e}")

    # =========================================================================
    # Task Creation & Announcement
    # =========================================================================

    def create_task(
        self,
        pickup: Tuple[int, int],
        dropoff: Tuple[int, int],
        priority: int = TaskPriority.NORMAL.value,
        task_id: Optional[str] = None,
        deadline: Optional[float] = None,
    ) -> Task:
        """Create a new local task object."""
        t_id = task_id or f"T-{int(time.time() * 1000) % 100000:05d}"
        task = Task(
            task_id=t_id,
            pickup=pickup,
            dropoff=dropoff,
            priority=priority,
            deadline=deadline,
            status=TaskStatus.CREATED,
            created_at=time.time(),
        )
        self.known_tasks[task.task_id] = task
        self._emit_event("TASK_CREATED", {"task": task.to_dict(), "task_id": task.task_id})
        return task

    def announce_task(self, task: Task, auction_round: int = 1) -> NetworkMessage:
        """Start a local auction and return P2P broadcast message."""
        task.auction_round = auction_round
        task.transition_to(TaskStatus.AUCTIONING)
        self.known_tasks[task.task_id] = task
        self.auction_manager.start_auction(task, auction_round=auction_round)

        self._emit_event("TASK_AUCTION_STARTED", {
            "task_id": task.task_id,
            "auction_round": auction_round,
            "pickup": list(task.pickup),
            "dropoff": list(task.dropoff),
        })

        return create_task_announcement_message(
            robot_id=self.robot_id,
            task=task,
            auction_round=auction_round,
        )

    # =========================================================================
    # Bid Calculation & Auction Processing
    # =========================================================================

    def create_bid(
        self,
        task: Task,
        current_position: Tuple[float, float],
        battery_percent: float,
        auction_round: int = 1,
    ) -> TaskBid:
        """Convenience method to calculate and record local bid for a task."""
        bid = self.cost_calculator.calculate_bid(
            task=task,
            robot_id=self.robot_id,
            current_position=current_position,
            battery_percent=battery_percent,
            active_task_count=1 if self.active_task else 0,
            pending_task_count=len(self.pending_tasks),
            auction_round=auction_round,
        )
        self.record_bid(bid)
        return bid

    def record_bid(self, bid: TaskBid) -> bool:
        """Record an incoming bid (local or peer)."""
        return self.auction_manager.record_bid(bid)

    def evaluate_auction(self, task_id: str) -> Optional[str]:
        """Evaluate winner for task auction."""
        winner_id, _ = self.auction_manager.evaluate_winner(task_id)
        return winner_id

    def handle_task_announcement(
        self,
        task_dict: Dict[str, Any],
        auction_round: int,
        current_position: Tuple[float, float],
        battery_percent: float,
        known_peer_positions: Optional[List[Tuple[float, float]]] = None,
    ) -> Tuple[Task, Optional[TaskBid]]:
        """
        Process incoming task announcement:
        1. Store task in known_tasks.
        2. Start local auction container.
        3. Independently calculate bid cost.
        4. Record own bid and return it for network broadcast.
        """
        task = Task.from_dict(task_dict)
        task.auction_round = auction_round
        task.transition_to(TaskStatus.AUCTIONING)
        self.known_tasks[task.task_id] = task

        self.auction_manager.start_auction(task, auction_round=auction_round)

        # Calculate bid
        bid = self.cost_calculator.calculate_bid(
            task=task,
            robot_id=self.robot_id,
            current_position=current_position,
            battery_percent=battery_percent,
            active_task_count=1 if self.active_task else 0,
            pending_task_count=len(self.pending_tasks),
            auction_round=auction_round,
            known_peer_positions=known_peer_positions,
        )

        self.auction_manager.record_bid(bid)
        self._emit_event("TASK_BID_SUBMITTED", {
            "task_id": task.task_id,
            "bid": bid.to_dict(),
            "cost": bid.cost,
            "is_valid": bid.is_valid,
        })

        return task, bid

    def handle_incoming_bid(self, bid_dict: Dict[str, Any]) -> Optional[TaskBid]:
        """Record a bid received from a peer AMR."""
        bid = TaskBid.from_dict(bid_dict)
        recorded = self.auction_manager.record_bid(bid)
        if recorded:
            logger.debug(f"[{self.robot_id}] Recorded bid from {bid.robot_id} on {bid.task_id}: cost={bid.cost}")
            return bid
        return None

    def finalize_auction(self, task_id: str) -> Tuple[Optional[str], Optional[Task]]:
        """
        Finalize local auction for task_id:
        1. Deterministically determine winner (lowest valid cost, tie-break robot_id).
        2. If self is winner: assign task to self and emit TASK_ASSIGNED.
        3. If peer is winner: update known task assignment.
        """
        winner_id = self.auction_manager.finalize_auction(task_id)
        task = self.known_tasks.get(task_id)

        if not winner_id or not task:
            logger.warning(f"[{self.robot_id}] Auction for {task_id} produced no winner.")
            return None, task

        task.assigned_robot = winner_id
        task.transition_to(TaskStatus.ASSIGNED)

        if winner_id == self.robot_id:
            self.assign_task(task)
            self._emit_event("TASK_ASSIGNED", {
                "task_id": task.task_id,
                "winner_id": self.robot_id,
                "is_self": True,
            })
        else:
            self._emit_event("TASK_ASSIGNED", {
                "task_id": task.task_id,
                "winner_id": winner_id,
                "is_self": False,
            })

        return winner_id, task

    def handle_task_award(self, task_id: str, winner_id: str, auction_round: int) -> Optional[Task]:
        """Process peer TASK_AWARD message."""
        task = self.known_tasks.get(task_id)
        if task and task.auction_round <= auction_round:
            task.assigned_robot = winner_id
            task.auction_round = auction_round
            task.transition_to(TaskStatus.ASSIGNED)
            if winner_id == self.robot_id and self.active_task != task:
                self.assign_task(task)
        return task

    # =========================================================================
    # Task Assignment & Execution Lifecycle
    # =========================================================================

    def assign_task(self, task: Task) -> None:
        """Assign task to self for execution."""
        task.assigned_robot = self.robot_id
        task.transition_to(TaskStatus.ASSIGNED)
        self.known_tasks[task.task_id] = task

        if self.active_task is None:
            self.active_task = task
            self.active_task.transition_to(TaskStatus.IN_PROGRESS)
            self._emit_event("TASK_STARTED", {"task_id": task.task_id, "pickup": list(task.pickup)})
        else:
            if task not in self.pending_tasks:
                self.pending_tasks.append(task)

    def get_next_navigation_target(self, current_pos: Tuple[float, float]) -> Optional[Tuple[int, int]]:
        """
        Coordinates task lifecycle steps:
        - Moving to pickup -> When reached, transitions to PICKED_UP -> targets dropoff.
        - Moving to dropoff -> When reached, transitions to COMPLETED.
        """
        if not self.active_task:
            return None

        task = self.active_task
        dist_to_pickup = math.hypot(current_pos[0] - task.pickup[0], current_pos[1] - task.pickup[1])
        dist_to_dropoff = math.hypot(current_pos[0] - task.dropoff[0], current_pos[1] - task.dropoff[1])

        # Step 1: Navigating to pickup
        if task.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
            if dist_to_pickup < 0.4:
                task.transition_to(TaskStatus.PICKED_UP)
                self._emit_event("TASK_PICKED_UP", {
                    "task_id": task.task_id,
                    "pickup": list(task.pickup),
                    "dropoff": list(task.dropoff),
                })
                logger.info(f"[{self.robot_id}] TASK_PICKED_UP task={task.task_id} at {task.pickup} -> heading to {task.dropoff}")
                return task.dropoff
            return task.pickup

        # Step 2: Navigating to dropoff
        elif task.status == TaskStatus.PICKED_UP:
            if dist_to_dropoff < 0.4:
                self.complete_current_task()
                return None
            return task.dropoff

        return None

    def complete_current_task(self) -> Optional[Task]:
        """Mark active task completed and promote next pending task."""
        if not self.active_task:
            return None

        finished = self.active_task
        finished.transition_to(TaskStatus.COMPLETED)
        self.completed_tasks.append(finished)
        self.known_tasks[finished.task_id] = finished

        logger.info(f"[{self.robot_id}] TASK_COMPLETED task={finished.task_id}")
        self._emit_event("TASK_COMPLETED", {
            "task_id": finished.task_id,
            "duration": finished.completed_at - (finished.started_at or finished.created_at),
        })

        # Advance queue
        if self.pending_tasks:
            self.active_task = self.pending_tasks.pop(0)
            self.active_task.transition_to(TaskStatus.IN_PROGRESS)
            self._emit_event("TASK_STARTED", {
                "task_id": self.active_task.task_id,
                "pickup": list(self.active_task.pickup),
            })
        else:
            self.active_task = None

        return finished

    # =========================================================================
    # Fault Tolerance & Re-Auction Handling
    # =========================================================================

    def handle_peer_offline(self, peer_id: str) -> List[Task]:
        """
        Detects uncompleted tasks assigned to a peer that went offline.
        Releases them for a new auction round.
        """
        reassignable_tasks: List[Task] = []

        for task in self.known_tasks.values():
            if task.assigned_robot == peer_id and task.status not in (
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.FAILED,
            ):
                task.assigned_robot = None
                task.auction_round += 1
                task.transition_to(TaskStatus.REASSIGNING, reason=f"Assigned peer {peer_id} went offline")
                reassignable_tasks.append(task)
                logger.warning(f"[{self.robot_id}] PEER_OFFLINE detected -> Task {task.task_id} released for Round {task.auction_round}")
                self._emit_event("TASK_RELEASED", {
                    "task_id": task.task_id,
                    "previous_robot": peer_id,
                    "reason": "PEER_OFFLINE",
                    "new_round": task.auction_round,
                })

        return reassignable_tasks

    def fail_current_task(self, reason: str = "") -> Optional[Task]:
        """Mark active task as failed and release for re-auction."""
        if not self.active_task:
            return None

        failed = self.active_task
        failed.transition_to(TaskStatus.FAILED, reason=reason)
        failed.assigned_robot = None
        failed.auction_round += 1
        self.failed_tasks.append(failed)
        self.active_task = None

        logger.warning(f"[{self.robot_id}] TASK_FAILED task={failed.task_id} reason={reason} -> Releasing for Round {failed.auction_round}")
        self._emit_event("TASK_FAILED", {
            "task_id": failed.task_id,
            "reason": reason,
            "new_round": failed.auction_round,
        })
        self._emit_event("TASK_RELEASED", {
            "task_id": failed.task_id,
            "previous_robot": self.robot_id,
            "reason": reason,
            "new_round": failed.auction_round,
        })

        return failed

    def release_task(self, task_id: str, reason: str = "") -> Optional[Task]:
        """Release an assigned task and return it."""
        if self.active_task and self.active_task.task_id == task_id:
            return self.fail_current_task(reason=reason)

        for i, t in enumerate(self.pending_tasks):
            if t.task_id == task_id:
                released = self.pending_tasks.pop(i)
                released.assigned_robot = None
                released.auction_round += 1
                released.transition_to(TaskStatus.REASSIGNING, reason=reason)
                self._emit_event("TASK_RELEASED", {
                    "task_id": released.task_id,
                    "reason": reason,
                    "new_round": released.auction_round,
                })
                return released

        return None

    # =========================================================================
    # Query API
    # =========================================================================

    def get_active_task(self) -> Optional[Task]:
        return self.active_task

    def get_pending_tasks(self) -> List[Task]:
        return list(self.pending_tasks)

    def get_completed_tasks(self) -> List[Task]:
        return list(self.completed_tasks)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.known_tasks.get(task_id)
