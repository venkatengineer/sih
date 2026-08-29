"""
Predictive Conflict Detection and Decentralized Resolution.
Classifies Head-On, Intersection, Same-Cell, Following, and Choke-Point conflicts.
Calculates explicit safe waiting cells preceding the conflict zone for graceful decentralized yielding.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import math
import time
from typing import List, Tuple, Optional, Dict, Any

from edge_robot.core.enums import ConflictAction, ConflictType
from edge_robot.core.state import RobotState
from edge_robot.coordination.priority import PriorityCalculator
from edge_robot.coordination.intent import RobotIntentData


def compute_safe_wait_node(current_grid: Tuple[int, int], path: List[Tuple[int, int]], contested: Tuple[int, int]) -> Tuple[int, int]:
    """Calculate the safe waypoint immediately preceding the contested zone in the planned trajectory."""
    if contested in path:
        idx = path.index(contested)
        if idx > 0:
            return path[idx - 1]
    return current_grid


@dataclass
class Conflict:
    """Structured conflict representation between two robots."""
    conflict_id: str
    peer_id: str
    conflict_type: str  # "HEAD_ON_SWAP", "INTERSECTION", "SAME_NEXT_NODE", "FOLLOWING", "CHOKE_POINT", "PROXIMITY"
    contested_node: Tuple[int, int]
    self_priority: float
    peer_priority: float
    safe_wait_node: Optional[Tuple[int, int]] = None
    eta_self: float = 0.0
    eta_peer: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "peer_id": self.peer_id,
            "conflict_type": self.conflict_type,
            "contested_node": list(self.contested_node),
            "safe_wait_node": list(self.safe_wait_node) if self.safe_wait_node else None,
            "self_priority": self.self_priority,
            "peer_priority": self.peer_priority,
            "eta_self": round(self.eta_self, 2),
            "eta_peer": round(self.eta_peer, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class ConflictResolution:
    """Decision made locally to resolve a conflict."""
    conflict: Conflict
    action: ConflictAction
    reason: str
    winner_id: str
    yielding_id: str


class ConflictDetector:
    """
    Evaluates self state & intent against peer states & intents to detect
    spatial and temporal conflicts before physical close encounter occurs.
    """

    @staticmethod
    def detect_conflicts(
        self_state: RobotState,
        peer_states: Dict[str, RobotState],
        peer_intents: Optional[Dict[str, RobotIntentData]] = None,
        safe_distance: float = 1.2,
        time_window_seconds: float = 2.0,
    ) -> List[Conflict]:
        conflicts: List[Conflict] = []
        self_grid = (int(round(self_state.position[0])), int(round(self_state.position[1])))
        self_next = self_state.next_node
        self_path = self_state.current_path
        intents = peer_intents or {}

        for peer_id, peer in peer_states.items():
            if peer.robot_id == self_state.robot_id:
                continue

            peer_grid = (int(round(peer.position[0])), int(round(peer.position[1])))
            peer_next = peer.next_node
            peer_path = peer.current_path

            peer_intent = intents.get(peer_id)
            if peer_intent:
                peer_priority = peer_intent.priority
                peer_eta = peer_intent.eta
                if not peer_path and peer_intent.path:
                    peer_path = peer_intent.path
                if not peer_next and peer_intent.next_waypoint:
                    peer_next = peer_intent.next_waypoint
            else:
                peer_priority = peer.priority
                peer_eta = 0.0

            # 1. TYPE 1 — HEAD ON (Opposite directions / swap)
            if self_next is not None and peer_next is not None:
                if self_next == peer_grid and peer_next == self_grid:
                    conflicts.append(Conflict(
                        conflict_id=f"swap-{self_state.robot_id}-{peer_id}-{int(time.time()*1000)}",
                        peer_id=peer_id,
                        conflict_type=ConflictType.HEAD_ON.value,
                        contested_node=self_next,
                        safe_wait_node=compute_safe_wait_node(self_grid, self_path, self_next),
                        self_priority=self_state.priority,
                        peer_priority=peer_priority,
                    ))
                    continue

                # Check if paths are heading directly towards each other in next 2 cells
                if len(self_path) >= 2 and len(peer_path) >= 2:
                    if self_path[0] == peer_grid and peer_path[0] == self_grid:
                        c_node = self_next or self_grid
                        conflicts.append(Conflict(
                            conflict_id=f"headon-{self_state.robot_id}-{peer_id}-{int(time.time()*1000)}",
                            peer_id=peer_id,
                            conflict_type=ConflictType.HEAD_ON.value,
                            contested_node=c_node,
                            safe_wait_node=compute_safe_wait_node(self_grid, self_path, c_node),
                            self_priority=self_state.priority,
                            peer_priority=peer_priority,
                        ))
                        continue

            # 2. TYPE 3 — SAME CELL (Both targeting same immediate next cell)
            if self_next is not None and peer_next is not None and self_next == peer_next:
                conflicts.append(Conflict(
                    conflict_id=f"node-{self_state.robot_id}-{peer_id}-{int(time.time()*1000)}",
                    peer_id=peer_id,
                    conflict_type=ConflictType.SAME_CELL.value,
                    contested_node=self_next,
                    safe_wait_node=compute_safe_wait_node(self_grid, self_path, self_next),
                    self_priority=self_state.priority,
                    peer_priority=peer_priority,
                ))
                continue

            # 3. TYPE 2 — INTERSECTION / PREDICTIVE PATH OVERLAP
            if self_path and peer_path:
                # Build lookahead with approximate cell index (time steps)
                self_timed = {cell: idx for idx, cell in enumerate(self_path[:6])}
                peer_timed = {cell: idx for idx, cell in enumerate(peer_path[:6])}

                for cell, self_step in self_timed.items():
                    if cell in peer_timed:
                        peer_step = peer_timed[cell]
                        # Overlap in time window (within ~2 steps)
                        if abs(self_step - peer_step) <= 2:
                            c_type = ConflictType.INTERSECTION.value if (self_step > 0 or peer_step > 0) else ConflictType.SAME_CELL.value
                            conflicts.append(Conflict(
                                conflict_id=f"intersect-{self_state.robot_id}-{peer_id}-{int(time.time()*1000)}",
                                peer_id=peer_id,
                                conflict_type=c_type,
                                contested_node=cell,
                                safe_wait_node=compute_safe_wait_node(self_grid, self_path, cell),
                                self_priority=self_state.priority,
                                peer_priority=peer_priority,
                                eta_self=self_step * 1.0,
                                eta_peer=peer_step * 1.0,
                            ))
                            break

                if conflicts and conflicts[-1].peer_id == peer_id:
                    continue

            # 4. TYPE 4 — FOLLOWING / REAR-END PROXIMITY
            dist = math.hypot(self_state.position[0] - peer.position[0], self_state.position[1] - peer.position[1])
            if dist < safe_distance:
                # Check if moving in same direction (following)
                if self_next and peer_next and self_next == peer_grid:
                    c_type = ConflictType.FOLLOWING.value
                else:
                    c_type = ConflictType.PROXIMITY.value

                conflicts.append(Conflict(
                    conflict_id=f"prox-{self_state.robot_id}-{peer_id}-{int(time.time()*1000)}",
                    peer_id=peer_id,
                    conflict_type=c_type,
                    contested_node=self_grid,
                    safe_wait_node=self_grid,
                    self_priority=self_state.priority,
                    peer_priority=peer_priority,
                ))

        return conflicts


class ConflictResolver:
    """
    Decentralized conflict resolution engine.
    Applies deterministic priority and tie-breaking rules to produce PROCEED, YIELD, WAIT, or REROUTE.
    """

    @staticmethod
    def resolve_conflict(self_id: str, conflict: Conflict) -> ConflictResolution:
        """
        Determines the appropriate action for self_id given a conflict.
        """
        if self_id == conflict.peer_id:
            my_priority = conflict.peer_priority
            my_eta = conflict.eta_peer
            other_id = conflict.conflict_id.split("-")[1] if "-" in conflict.conflict_id else "PEER"
            other_priority = conflict.self_priority
            other_eta = conflict.eta_self
        else:
            my_priority = conflict.self_priority
            my_eta = conflict.eta_self
            other_id = conflict.peer_id
            other_priority = conflict.peer_priority
            other_eta = conflict.eta_peer

        self_wins = PriorityCalculator.compare_precedence(
            self_id=self_id,
            self_priority=my_priority,
            self_eta=my_eta,
            peer_id=other_id,
            peer_priority=other_priority,
            peer_eta=other_eta,
        )

        winner_id = self_id if self_wins else other_id
        yielding_id = other_id if self_wins else self_id

        if self_wins:
            return ConflictResolution(
                conflict=conflict,
                action=ConflictAction.PROCEED,
                reason=f"Higher precedence ({my_priority:.1f} vs {other_priority:.1f}) -> Proceed through {conflict.contested_node}",
                winner_id=winner_id,
                yielding_id=yielding_id,
            )
        else:
            safe_loc = conflict.safe_wait_node or conflict.contested_node
            # Action when yielding depends on conflict type
            if conflict.conflict_type in (ConflictType.HEAD_ON.value, "HEAD_ON_SWAP"):
                action = ConflictAction.REROUTE
                reason = f"Lower precedence in head-on corridor -> Reroute around peer {other_id}"
            elif conflict.conflict_type == ConflictType.FOLLOWING.value:
                action = ConflictAction.WAIT
                reason = f"Following {other_id} -> Maintaining safe headway at {safe_loc}"
            elif conflict.conflict_type == ConflictType.INTERSECTION.value:
                action = ConflictAction.YIELD
                reason = f"Lower precedence at intersection ({my_priority:.1f} vs {other_priority:.1f}) -> Safe wait at {safe_loc} for {other_id}"
            else:
                action = ConflictAction.YIELD
                reason = f"Lower precedence ({my_priority:.1f} vs {other_priority:.1f}) -> Safe wait at {safe_loc} for {other_id}"

            return ConflictResolution(
                conflict=conflict,
                action=action,
                reason=reason,
                winner_id=winner_id,
                yielding_id=yielding_id,
            )
