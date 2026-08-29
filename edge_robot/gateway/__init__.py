"""
Frontend Gateway package for Edge Robot.
Provides WebSocket interface connecting independent RobotAgent instances to external visual simulations.
"""

from edge_robot.gateway.frontend_protocol import (
    FrontendMessageType,
    CommandAction,
    FrontendCommand,
    FrontendDecisionEvent,
    format_state_message,
    format_path_message,
)
from edge_robot.gateway.websocket_server import AsyncWebSocketServer, WebSocketConnection
from edge_robot.gateway.session import FrontendGateway

__all__ = [
    "FrontendMessageType",
    "CommandAction",
    "FrontendCommand",
    "FrontendDecisionEvent",
    "format_state_message",
    "format_path_message",
    "AsyncWebSocketServer",
    "WebSocketConnection",
    "FrontendGateway",
]
