"""
Frontend WebSocket Protocol Definitions and Schemas.
Handles bidirectional messaging between the Godot 3D Warehouse Simulation
and individual Edge Robot Agents.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from typing import List, Tuple, Dict, Any, Optional

from edge_robot.core.enums import RobotStatus, RobotIntent, ConflictAction


class FrontendMessageType(str, Enum):
    # Inbound from Godot Simulation
    INIT = "INIT"
    POSITION_UPDATE = "POSITION_UPDATE"
    POSITION = "POSITION"
    WORLD_UPDATE = "WORLD_UPDATE"
    GOAL_UPDATE = "GOAL_UPDATE"
    SENSOR_UPDATE = "SENSOR_UPDATE"
    TASK = "TASK"
    RESET = "RESET"

    # Outbound to Godot Simulation
    STATE_UPDATE = "STATE_UPDATE"
    STATE = "STATE"
    PATH_UPDATE = "PATH_UPDATE"
    PATH = "PATH"
    COMMAND = "COMMAND"
    DECISION_EVENT = "DECISION_EVENT"
    CONFLICT_EVENT = "CONFLICT_EVENT"
    NETWORK_EVENT = "NETWORK_EVENT"
    INIT_ACK = "INIT_ACK"
    ERROR = "ERROR"


class CommandAction(str, Enum):
    MOVE = "MOVE"
    STOP = "STOP"
    WAIT = "WAIT"
    YIELD = "YIELD"
    REROUTE = "REROUTE"
    EMERGENCY_STOP = "EMERGENCY_STOP"


@dataclass
class FrontendCommand:
    """Action command emitted by Python Edge Agent for Godot AMR to visually execute."""
    robot_id: str
    action: CommandAction
    target: Optional[Tuple[float, float]] = None
    speed: float = 1.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": FrontendMessageType.COMMAND.value,
            "robot_id": self.robot_id,
            "action": self.action.value if isinstance(self.action, CommandAction) else str(self.action),
            "target": list(self.target) if self.target else None,
            "speed": round(self.speed, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class FrontendDecisionEvent:
    """Explainable decision event emitted by Python Edge Agent."""
    robot_id: str
    event: str  # "YIELD", "PROCEED", "REROUTE", "SAFETY_STOP", "DEADLOCK_RECOVERY", "GOAL_REACHED"
    reason: str
    peer: Optional[str] = None
    node: Optional[Tuple[int, int]] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": FrontendMessageType.DECISION_EVENT.value,
            "robot_id": self.robot_id,
            "event": self.event,
            "reason": self.reason,
            "peer": self.peer,
            "node": list(self.node) if self.node else None,
            "timestamp": self.timestamp,
        }


@dataclass
class FrontendConflictEvent:
    """Conflict event emitted when multiple robots compete for shared space."""
    robot_id: str
    peer: str
    node: Tuple[int, int]
    resolution: str  # e.g. "AMR-02_YIELDS", "AMR-01_PROCEEDS"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": FrontendMessageType.CONFLICT_EVENT.value,
            "robot_id": self.robot_id,
            "peer": self.peer,
            "node": list(self.node),
            "resolution": self.resolution,
            "timestamp": self.timestamp,
        }


@dataclass
class FrontendNetworkEvent:
    """P2P mesh network topology/connection event."""
    robot_id: str
    event: str  # "PEER_CONNECTED", "PEER_DISCONNECTED", "PEER_TIMEOUT"
    peer: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": FrontendMessageType.NETWORK_EVENT.value,
            "robot_id": self.robot_id,
            "event": self.event,
            "peer": self.peer,
            "timestamp": self.timestamp,
        }


def format_state_message(
    robot_id: str,
    position: Tuple[float, float],
    velocity: float,
    heading: float,
    status: RobotStatus | str,
    battery: float,
    intent: RobotIntent | str = RobotIntent.MOVE,
    current_task: Optional[str] = None,
) -> Dict[str, Any]:
    """Format STATE_UPDATE message for Godot visual simulation."""
    return {
        "type": FrontendMessageType.STATE_UPDATE.value,
        "robot_id": robot_id,
        "position": [round(position[0], 2), round(position[1], 2)],
        "velocity": round(velocity, 2),
        "heading": round(heading, 1),
        "status": status.value if isinstance(status, RobotStatus) else str(status),
        "intent": intent.value if isinstance(intent, RobotIntent) else str(intent),
        "battery": round(battery, 1),
        "current_task": current_task,
        "timestamp": time.time(),
    }


def format_path_message(robot_id: str, path: List[Tuple[int, int]]) -> Dict[str, Any]:
    """Format PATH_UPDATE message for Godot path rendering."""
    return {
        "type": FrontendMessageType.PATH_UPDATE.value,
        "robot_id": robot_id,
        "path": [list(node) for node in path],
        "timestamp": time.time(),
    }
