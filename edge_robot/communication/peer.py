"""
Peer tracking table and heartbeat timeout management.
Maintains rich peer state, intent, ETA, and priority for decentralized coordination.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, List, Optional, Tuple

from edge_robot.core.state import RobotState
from edge_robot.coordination.intent import RobotIntentData


@dataclass
class PeerEntry:
    """Record of an individual peer robot known on the P2P network."""
    robot_id: str
    state: RobotState
    intent: Optional[RobotIntentData] = None
    last_seen: float = field(default_factory=time.time)
    endpoint: Optional[Tuple[str, int]] = None
    sequence: int = 0

    def is_alive(self, timeout_seconds: float = 3.0, current_time: Optional[float] = None) -> bool:
        t = current_time or time.time()
        return (t - self.last_seen) <= timeout_seconds


class PeerTable:
    """
    Maintains decentralized knowledge of all active peer AMRs.
    Detects timeouts when peer fails to heartbeat.
    """

    def __init__(self, heartbeat_timeout: float = 3.0):
        self.heartbeat_timeout = heartbeat_timeout
        self.peers: Dict[str, PeerEntry] = {}

    def update_peer(
        self,
        state: RobotState,
        endpoint: Optional[Tuple[str, int]] = None,
        intent: Optional[RobotIntentData] = None,
        sequence: int = 0,
    ) -> None:
        """Update or insert peer entry."""
        existing = self.peers.get(state.robot_id)
        current_intent = intent or (existing.intent if existing else None)
        seq = sequence if sequence > 0 else (existing.sequence if existing else 0)

        self.peers[state.robot_id] = PeerEntry(
            robot_id=state.robot_id,
            state=state,
            intent=current_intent,
            last_seen=time.time(),
            endpoint=endpoint,
            sequence=seq,
        )

    def update_peer_intent(
        self,
        intent: RobotIntentData,
        endpoint: Optional[Tuple[str, int]] = None,
    ) -> None:
        """Update intent information received from peer."""
        if intent.robot_id in self.peers:
            entry = self.peers[intent.robot_id]
            entry.intent = intent
            entry.last_seen = time.time()
            entry.sequence = intent.sequence
            # Synchronize state attributes
            entry.state.position = intent.position
            entry.state.priority = intent.priority
            entry.state.current_path = list(intent.path)
            entry.state.next_node = intent.next_waypoint
            if endpoint:
                entry.endpoint = endpoint
        else:
            state = RobotState(
                robot_id=intent.robot_id,
                position=intent.position,
                priority=intent.priority,
                current_path=list(intent.path),
                next_node=intent.next_waypoint,
            )
            self.peers[intent.robot_id] = PeerEntry(
                robot_id=intent.robot_id,
                state=state,
                intent=intent,
                last_seen=time.time(),
                endpoint=endpoint,
                sequence=intent.sequence,
            )

    def record_heartbeat(self, robot_id: str, endpoint: Optional[Tuple[str, int]] = None) -> None:
        """Refresh last_seen timestamp on heartbeat message."""
        if robot_id in self.peers:
            self.peers[robot_id].last_seen = time.time()
            if endpoint:
                self.peers[robot_id].endpoint = endpoint

    def get_peer_state(self, robot_id: str) -> Optional[RobotState]:
        entry = self.peers.get(robot_id)
        if entry and entry.is_alive(self.heartbeat_timeout):
            return entry.state
        return None

    def get_peer_intent(self, robot_id: str) -> Optional[RobotIntentData]:
        entry = self.peers.get(robot_id)
        if entry and entry.is_alive(self.heartbeat_timeout):
            return entry.intent
        return None

    def get_all_active_peers(self) -> Dict[str, RobotState]:
        """Return dict of robot_id -> RobotState for all non-timed-out peers."""
        now = time.time()
        return {
            p_id: entry.state
            for p_id, entry in self.peers.items()
            if entry.is_alive(self.heartbeat_timeout, now)
        }

    def get_all_active_intents(self) -> Dict[str, RobotIntentData]:
        """Return dict of robot_id -> RobotIntentData for all non-timed-out peers."""
        now = time.time()
        return {
            p_id: entry.intent
            for p_id, entry in self.peers.items()
            if entry.is_alive(self.heartbeat_timeout, now) and entry.intent is not None
        }

    def prune_stale_peers(self) -> List[str]:
        """
        Detect and remove peers that have exceeded heartbeat timeout.
        Returns list of newly timed-out robot IDs.
        """
        now = time.time()
        stale_ids = [
            p_id for p_id, entry in self.peers.items()
            if not entry.is_alive(self.heartbeat_timeout, now)
        ]
        for p_id in stale_ids:
            del self.peers[p_id]
        return stale_ids
