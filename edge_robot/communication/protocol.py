"""
P2P Network Message Protocol, Schemas, Task Auction Serialization, and Coordination Messages.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import time
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING

from edge_robot.core.enums import MessageType, RobotStatus, RobotIntent, TaskStatus, ConflictType, ConflictAction

if TYPE_CHECKING:
    from edge_robot.tasks.task import Task
    from edge_robot.tasks.bid import TaskBid
    from edge_robot.coordination.intent import RobotIntentData


@dataclass
class NetworkMessage:
    """Base envelope for all P2P network messages."""
    type: MessageType
    sender_id: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        data = {
            "type": self.type.value if isinstance(self.type, MessageType) else str(self.type),
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: str | bytes) -> Optional[NetworkMessage]:
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            data = json.loads(raw)
            msg_type = MessageType(data["type"])
            return cls(
                type=msg_type,
                sender_id=data["sender_id"],
                timestamp=float(data.get("timestamp", time.time())),
                payload=data.get("payload", {}),
            )
        except Exception:
            return None


def create_state_message(
    robot_id: str,
    position: Tuple[float, float],
    heading: float,
    velocity: float,
    battery: float,
    status: RobotStatus,
    intent: RobotIntent,
    priority: float,
    current_path: List[Tuple[int, int]],
    next_node: Optional[Tuple[int, int]],
    current_task: Optional[str] = None,
) -> NetworkMessage:
    """Helper to create ROBOT_STATE message."""
    payload = {
        "robot_id": robot_id,
        "position": list(position),
        "heading": round(heading, 2),
        "velocity": round(velocity, 2),
        "battery": round(battery, 1),
        "status": status.value if isinstance(status, RobotStatus) else str(status),
        "intent": intent.value if isinstance(intent, RobotIntent) else str(intent),
        "priority": round(priority, 2),
        "current_path": [list(p) for p in current_path],
        "next_node": list(next_node) if next_node else None,
        "current_task": current_task,
    }
    return NetworkMessage(
        type=MessageType.ROBOT_STATE,
        sender_id=robot_id,
        payload=payload,
    )


def create_robot_intent_message(
    robot_id: str,
    position: Tuple[float, float],
    velocity: Tuple[float, float],
    current_cell: Tuple[int, int],
    path: List[Tuple[int, int]],
    next_waypoint: Optional[Tuple[int, int]],
    eta: float,
    priority: float,
    task_id: Optional[str] = None,
    status: str = "MOVING",
    sequence: int = 0,
) -> NetworkMessage:
    """Helper to create rich ROBOT_INTENT message."""
    payload = {
        "robot_id": robot_id,
        "position": [round(position[0], 2), round(position[1], 2)],
        "velocity": [round(velocity[0], 2), round(velocity[1], 2)],
        "current_cell": list(current_cell),
        "path": [list(p) for p in path],
        "next_waypoint": list(next_waypoint) if next_waypoint else None,
        "eta": round(eta, 2),
        "priority": round(priority, 2),
        "task_id": task_id,
        "status": status,
        "sequence": sequence,
    }
    return NetworkMessage(
        type=MessageType.ROBOT_INTENT,
        sender_id=robot_id,
        payload=payload,
    )


def create_intent_message(
    robot_id: str,
    intent: RobotIntent,
    current_node: Tuple[int, int],
    next_nodes: List[Tuple[int, int]],
    priority: float,
) -> NetworkMessage:
    """Helper to create legacy INTENT message."""
    payload = {
        "robot_id": robot_id,
        "intent": intent.value if isinstance(intent, RobotIntent) else str(intent),
        "current_node": list(current_node),
        "next_nodes": [list(n) for n in next_nodes],
        "priority": round(priority, 2),
    }
    return NetworkMessage(
        type=MessageType.INTENT,
        sender_id=robot_id,
        payload=payload,
    )


def create_conflict_detected_message(
    robot_id: str,
    peer_id: str,
    conflict_type: str,
    zone: Tuple[int, int],
    eta_self: float,
    eta_peer: float,
) -> NetworkMessage:
    """Helper to create CONFLICT_DETECTED message."""
    payload = {
        "robot_id": robot_id,
        "peer_id": peer_id,
        "conflict_type": conflict_type,
        "zone": list(zone),
        "eta_self": round(eta_self, 2),
        "eta_peer": round(eta_peer, 2),
    }
    return NetworkMessage(
        type=MessageType.CONFLICT_DETECTED,
        sender_id=robot_id,
        payload=payload,
    )


def create_conflict_resolution_message(
    robot_id: str,
    peer_id: str,
    decision: str,
    reason: str,
    zone: Tuple[int, int],
) -> NetworkMessage:
    """Helper to create CONFLICT_RESOLUTION message."""
    payload = {
        "robot_id": robot_id,
        "peer_id": peer_id,
        "decision": decision,
        "reason": reason,
        "zone": list(zone),
    }
    return NetworkMessage(
        type=MessageType.CONFLICT_RESOLUTION,
        sender_id=robot_id,
        payload=payload,
    )


def create_reservation_request_message(
    robot_id: str,
    node: Tuple[int, int],
    enter_time: float,
    exit_time: float,
    priority: float,
) -> NetworkMessage:
    """Helper to create RESERVATION_REQUEST message."""
    payload = {
        "robot_id": robot_id,
        "node": list(node),
        "enter_time": round(enter_time, 2),
        "exit_time": round(exit_time, 2),
        "priority": round(priority, 2),
    }
    return NetworkMessage(
        type=MessageType.RESERVATION_REQUEST,
        sender_id=robot_id,
        payload=payload,
    )


def create_reservation_grant_message(
    robot_id: str,
    node: Tuple[int, int],
    priority: float,
    ttl_seconds: float = 3.0,
) -> NetworkMessage:
    """Helper to create RESERVATION_GRANT message."""
    payload = {
        "robot_id": robot_id,
        "node": list(node),
        "priority": round(priority, 2),
        "ttl_seconds": ttl_seconds,
    }
    return NetworkMessage(
        type=MessageType.RESERVATION_GRANT,
        sender_id=robot_id,
        payload=payload,
    )


def create_reservation_release_message(robot_id: str, node: Tuple[int, int]) -> NetworkMessage:
    """Helper to create RESERVATION_RELEASE message."""
    payload = {
        "robot_id": robot_id,
        "node": list(node),
    }
    return NetworkMessage(
        type=MessageType.RESERVATION_RELEASE,
        sender_id=robot_id,
        payload=payload,
    )


def create_deadlock_detected_message(
    robot_id: str,
    cycle: List[str],
    victim_id: str,
) -> NetworkMessage:
    """Helper to create DEADLOCK_DETECTED message."""
    payload = {
        "robot_id": robot_id,
        "cycle": cycle,
        "victim_id": victim_id,
    }
    return NetworkMessage(
        type=MessageType.DEADLOCK_DETECTED,
        sender_id=robot_id,
        payload=payload,
    )


def create_obstacle_message(
    robot_id: str,
    obstacle_id: str,
    obstacle_type: str,
    position: Tuple[float, float],
    distance: float,
) -> NetworkMessage:
    """Helper to create OBSTACLE message."""
    payload = {
        "obstacle_id": obstacle_id,
        "obstacle_type": obstacle_type,
        "position": list(position),
        "distance": round(distance, 2),
    }
    return NetworkMessage(
        type=MessageType.OBSTACLE,
        sender_id=robot_id,
        payload=payload,
    )


def create_heartbeat_message(robot_id: str, status: RobotStatus, battery: float) -> NetworkMessage:
    """Helper to create HEARTBEAT message."""
    payload = {
        "status": status.value if isinstance(status, RobotStatus) else str(status),
        "battery": round(battery, 1),
    }
    return NetworkMessage(
        type=MessageType.HEARTBEAT,
        sender_id=robot_id,
        payload=payload,
    )


# =============================================================================
# Decentralized Task Auction Message Creators
# =============================================================================

def create_task_announcement_message(
    robot_id: str,
    task: Any,
    auction_round: int = 1,
) -> NetworkMessage:
    """Helper to broadcast a new task announcement to all peer AMRs."""
    task_dict = task.to_dict() if hasattr(task, "to_dict") else task
    payload = {
        "task": task_dict,
        "auction_round": auction_round,
    }
    return NetworkMessage(
        type=MessageType.TASK_ANNOUNCEMENT,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_bid_message(robot_id: str, bid: Any) -> NetworkMessage:
    """Helper to broadcast a local task bid to all peer AMRs."""
    bid_dict = bid.to_dict() if hasattr(bid, "to_dict") else bid
    return NetworkMessage(
        type=MessageType.TASK_BID,
        sender_id=robot_id,
        payload=bid_dict,
    )


def create_task_award_message(
    robot_id: str,
    task_id: str,
    winner_id: str,
    auction_round: int = 1,
) -> NetworkMessage:
    """Helper to broadcast winning task allocation consensus."""
    payload = {
        "task_id": task_id,
        "winner_id": winner_id,
        "auction_round": auction_round,
    }
    return NetworkMessage(
        type=MessageType.TASK_AWARD,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_accept_message(robot_id: str, task_id: str, auction_round: int = 1) -> NetworkMessage:
    """Helper for winner to broadcast task acceptance."""
    payload = {
        "task_id": task_id,
        "robot_id": robot_id,
        "auction_round": auction_round,
    }
    return NetworkMessage(
        type=MessageType.TASK_ACCEPT,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_reject_message(robot_id: str, task_id: str, reason: str = "") -> NetworkMessage:
    """Helper to reject a task assignment."""
    payload = {
        "task_id": task_id,
        "robot_id": robot_id,
        "reason": reason,
    }
    return NetworkMessage(
        type=MessageType.TASK_REJECT,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_progress_message(
    robot_id: str,
    task_id: str,
    status: TaskStatus,
    progress: float = 0.0,
) -> NetworkMessage:
    """Helper to broadcast task execution progress."""
    payload = {
        "task_id": task_id,
        "robot_id": robot_id,
        "status": status.value if isinstance(status, TaskStatus) else str(status),
        "progress": round(progress, 2),
    }
    return NetworkMessage(
        type=MessageType.TASK_PROGRESS,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_complete_message(robot_id: str, task_id: str) -> NetworkMessage:
    """Helper to broadcast successful task completion."""
    payload = {
        "task_id": task_id,
        "robot_id": robot_id,
        "completed_at": time.time(),
    }
    return NetworkMessage(
        type=MessageType.TASK_COMPLETE,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_failed_message(robot_id: str, task_id: str, reason: str = "") -> NetworkMessage:
    """Helper to broadcast task execution failure."""
    payload = {
        "task_id": task_id,
        "robot_id": robot_id,
        "reason": reason,
    }
    return NetworkMessage(
        type=MessageType.TASK_FAILED,
        sender_id=robot_id,
        payload=payload,
    )


def create_task_release_message(
    robot_id: str,
    task_id: str,
    reason: str = "",
    new_round: int = 2,
) -> NetworkMessage:
    """Helper to release a task for peer re-auction."""
    payload = {
        "task_id": task_id,
        "released_by": robot_id,
        "reason": reason,
        "new_round": new_round,
    }
    return NetworkMessage(
        type=MessageType.TASK_RELEASE,
        sender_id=robot_id,
        payload=payload,
    )
