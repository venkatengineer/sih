"""
Session manager connecting an individual RobotAgent to the Frontend Simulation WebSocket Gateway.
Translates incoming observations and task requests into agent actions,
and streams outgoing commands, paths, state updates, decision events, and task auction events to Godot.
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:
    from edge_robot.core.robot import RobotAgent

from edge_robot.core.state import RobotState
from edge_robot.gateway.frontend_protocol import (
    FrontendMessageType,
    FrontendCommand,
    FrontendDecisionEvent,
    FrontendConflictEvent,
    FrontendNetworkEvent,
    format_state_message,
    format_path_message,
)
from edge_robot.gateway.websocket_server import AsyncWebSocketServer, WebSocketConnection
from edge_robot.tasks.task import Task

logger = logging.getLogger("edge_robot.gateway")


class FrontendGateway:
    """
    Bridge connecting ONE RobotAgent to the Godot 3D Warehouse Simulation via WebSocket.
    Translates incoming Godot observations into agent state updates,
    and streams outgoing agent commands, paths, states, and decisions to Godot.
    """

    def __init__(self, agent: RobotAgent, host: str = "127.0.0.1", port: int = 8001):
        self.agent = agent
        self.host = host
        self.port = port
        self.server = AsyncWebSocketServer(
            host=host,
            port=port,
            message_handler=self._handle_frontend_message,
            connect_handler=self._handle_client_connect,
            disconnect_handler=self._handle_client_disconnect,
        )

        # Attach agent output listeners
        self.agent.on_command(self._on_agent_command)
        self.agent.on_state(self._on_agent_state)
        self.agent.on_path(self._on_agent_path)
        self.agent.on_event(self._on_agent_event)
        self.agent.task_manager.on_task_event(self._on_agent_task_event)

    async def start(self) -> None:
        """Start the frontend WebSocket gateway."""
        await self.server.start()
        logger.info(f"[{self.agent.robot_id}] FRONTEND_CONNECTED ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the frontend WebSocket gateway."""
        await self.server.stop()
        logger.info(f"[{self.agent.robot_id}] FRONTEND_DISCONNECTED")

    # =========================================================================
    # Outbound Handlers (Agent -> Godot)
    # =========================================================================

    def _on_agent_command(self, cmd: FrontendCommand) -> None:
        """Forward agent action command to Godot simulation."""
        asyncio.create_task(self.server.broadcast(cmd.to_dict()))

    def _on_agent_state(self, state: RobotState) -> None:
        """Forward periodic state update to Godot simulation."""
        msg = format_state_message(
            robot_id=state.robot_id,
            position=state.position,
            velocity=state.velocity,
            heading=state.heading,
            status=state.status,
            battery=state.battery,
            intent=state.intent,
            current_task=state.current_task,
        )
        asyncio.create_task(self.server.broadcast(msg))

    def _on_agent_path(self, path: List[Tuple[int, int]]) -> None:
        """Forward calculated A* path to Godot simulation for rendering."""
        msg = format_path_message(self.agent.robot_id, path)
        asyncio.create_task(self.server.broadcast(msg))

    def _on_agent_event(self, event: Any) -> None:
        """Forward explainable decision/conflict/network event to Godot simulation."""
        if hasattr(event, "to_dict"):
            asyncio.create_task(self.server.broadcast(event.to_dict()))
        elif isinstance(event, dict):
            asyncio.create_task(self.server.broadcast(event))

    def _on_agent_task_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Forward structured decentralized task events to Godot simulation."""
        msg = {
            "type": "TASK_EVENT",
            "event": event_name,
            "robot_id": self.agent.robot_id,
            "task_id": payload.get("task_id"),
            "data": payload,
            "timestamp": time.time(),
        }
        asyncio.create_task(self.server.broadcast(msg))

    # =========================================================================
    # Inbound Handlers (Godot -> Agent)
    # =========================================================================

    async def _handle_client_connect(self, conn: WebSocketConnection) -> None:
        """Send current state and path immediately upon Godot connection."""
        state_msg = format_state_message(
            robot_id=self.agent.robot_id,
            position=self.agent.state.position,
            velocity=self.agent.state.velocity,
            heading=self.agent.state.heading,
            status=self.agent.state.status,
            battery=self.agent.state.battery,
            intent=self.agent.state.intent,
            current_task=self.agent.state.current_task,
        )
        await conn.send_json(state_msg)
        if self.agent.state.current_path:
            await conn.send_json(format_path_message(self.agent.robot_id, self.agent.state.current_path))

    async def _handle_client_disconnect(self, conn: WebSocketConnection) -> None:
        pass

    async def _handle_frontend_message(self, conn: WebSocketConnection, raw_message: str) -> None:
        """Parse and process incoming message from Godot simulation."""
        try:
            data = json.loads(raw_message)
            msg_type = data.get("type", "").upper()

            if msg_type == "INIT":
                pos = tuple(data.get("position", self.agent.config.initial_position))
                goal = tuple(data["goal"]) if "goal" in data and data["goal"] else None
                self.agent.reset(
                    initial_position=(float(pos[0]), float(pos[1])),
                    initial_heading=float(data.get("heading", 0.0)),
                )
                if goal:
                    self.agent.update_goal((float(goal[0]), float(goal[1])))

                ack = {
                    "type": "INIT_ACK",
                    "robot_id": self.agent.robot_id,
                    "status": "INITIALIZED",
                    "position": [pos[0], pos[1]],
                }
                await conn.send_json(ack)

            elif msg_type in ("POSITION_UPDATE", "POSITION"):
                pos = data.get("position")
                heading = data.get("heading")
                if pos:
                    self.agent.update_position((float(pos[0]), float(pos[1])), heading=heading)

            elif msg_type == "WORLD_UPDATE":
                obstacles = data.get("obstacles", [])
                robots = data.get("robots", [])
                self.agent.update_world(obstacles=obstacles, robots=robots)

            elif msg_type == "GOAL_UPDATE":
                goal = data.get("goal")
                if goal:
                    self.agent.update_goal((float(goal[0]), float(goal[1])))

            elif msg_type == "SENSOR_UPDATE":
                obstacles = data.get("obstacles", [])
                self.agent.update_obstacles(obstacles)

            elif msg_type == "TASK":
                # Originates task announcement into the decentralized P2P fleet
                p_raw = data.get("pickup", (4, 3))
                d_raw = data.get("dropoff", data.get("destination", (18, 8)))
                priority = int(data.get("priority", 5))
                task_id = data.get("task_id")

                pickup = (int(round(p_raw[0])), int(round(p_raw[1])))
                dropoff = (int(round(d_raw[0])), int(round(d_raw[1])))

                task = self.agent.submit_task(
                    pickup=pickup,
                    dropoff=dropoff,
                    priority=priority,
                    task_id=task_id,
                )
                logger.info(f"[{self.agent.robot_id}] Submitted task {task.task_id} into decentralized P2P fleet")

            elif msg_type == "RESET":
                self.agent.reset()

            else:
                logger.warning(f"[{self.agent.robot_id}] Unknown frontend message type: {msg_type}")

        except Exception as e:
            logger.error(f"[{self.agent.robot_id}] Error parsing frontend message: {e}", exc_info=True)
            err_msg = {
                "type": "ERROR",
                "robot_id": self.agent.robot_id,
                "error": str(e),
            }
            await conn.send_json(err_msg)
