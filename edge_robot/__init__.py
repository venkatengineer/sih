"""
Edge Robot Agent Package - Decentralized AMR Edge Node
"""

from edge_robot.core.enums import (
    RobotStatus,
    RobotIntent,
    TaskStatus,
    ConflictAction,
    ObstacleType,
    MessageType,
)
from edge_robot.core.state import RobotState
from edge_robot.core.robot import RobotAgent
from edge_robot.config import RobotConfig, load_config
from edge_robot.gateway.frontend_protocol import (
    FrontendMessageType,
    CommandAction,
    FrontendCommand,
    FrontendDecisionEvent,
)
from edge_robot.gateway.session import FrontendGateway

__version__ = "1.0.0"

__all__ = [
    "RobotAgent",
    "RobotState",
    "RobotConfig",
    "RobotStatus",
    "RobotIntent",
    "TaskStatus",
    "ConflictAction",
    "ObstacleType",
    "MessageType",
    "FrontendMessageType",
    "CommandAction",
    "FrontendCommand",
    "FrontendDecisionEvent",
    "FrontendGateway",
    "load_config",
]
