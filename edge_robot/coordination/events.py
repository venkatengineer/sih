"""
Coordination Event Definitions and Logger for Observability.
Allows judges, operators, and tests to trace every decentralized decision.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Dict, Any, Optional, List


@dataclass
class CoordinationEvent:
    """A single observable decentralized coordination event."""
    event: str
    robot_id: str
    timestamp: float = field(default_factory=time.time)
    task_id: Optional[str] = None
    peer_id: Optional[str] = None
    conflict_type: Optional[str] = None
    zone: Optional[List[int]] = None
    decision: Optional[str] = None
    reason: Optional[str] = None
    eta_self: Optional[float] = None
    eta_peer: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "event": self.event,
            "robot_id": self.robot_id,
            "timestamp": self.timestamp,
        }
        if self.task_id: d["task_id"] = self.task_id
        if self.peer_id: d["peer_id"] = self.peer_id
        if self.conflict_type: d["conflict_type"] = self.conflict_type
        if self.zone: d["zone"] = self.zone
        if self.decision: d["decision"] = self.decision
        if self.reason: d["reason"] = self.reason
        if self.eta_self is not None: d["eta_self"] = self.eta_self
        if self.eta_peer is not None: d["eta_peer"] = self.eta_peer
        if self.details: d["details"] = self.details
        return d
