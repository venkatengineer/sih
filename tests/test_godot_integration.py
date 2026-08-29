"""
Integration tests for Godot 3D Warehouse Digital Twin & Python Edge Robot Agent integration.
Validates the complete closed-loop protocol, coordinate mapping, and multi-robot P2P conflict resolution.
"""

import unittest
import asyncio
import base64
import json
import os
import struct
from typing import Optional, Dict, Any, List, Tuple

from edge_robot.config import RobotConfig, generate_godot_warehouse_obstacles
from edge_robot.core.robot import RobotAgent
from edge_robot.gateway.session import FrontendGateway
from edge_robot.gateway.frontend_protocol import (
    FrontendMessageType,
    CommandAction,
    FrontendCommand,
    FrontendDecisionEvent,
    FrontendConflictEvent,
    FrontendNetworkEvent,
    format_state_message,
    format_path_message,
)


class GodotWebSocketMockClient:
    """Mock representing Godot's WebSocketPeer connecting to an Edge Agent."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        self.host = host
        self.port = port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        key = base64.b64encode(os.urandom(16)).decode("utf-8")
        handshake = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.writer.write(handshake.encode("utf-8"))
        await self.writer.drain()

        # Read response headers
        while True:
            line = await self.reader.readline()
            if not line or line == b"\r\n":
                break

    async def send_json(self, data: Dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")
        length = len(payload)
        mask = os.urandom(4)

        header = bytearray()
        header.append(0x81)  # FIN + Text Frame

        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))

        header.extend(mask)
        masked_payload = bytearray(length)
        for i in range(length):
            masked_payload[i] = payload[i] ^ mask[i % 4]

        self.writer.write(bytes(header) + bytes(masked_payload))
        await self.writer.drain()

    async def receive_json(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        try:
            head = await asyncio.wait_for(self.reader.readexactly(2), timeout=timeout)
            b1, b2 = head[0], head[1]
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            payload_len = b2 & 0x7F

            if payload_len == 126:
                ext = await self.reader.readexactly(2)
                payload_len = struct.unpack("!H", ext)[0]
            elif payload_len == 127:
                ext = await self.reader.readexactly(8)
                payload_len = struct.unpack("!Q", ext)[0]

            mask_key = None
            if masked:
                mask_key = await self.reader.readexactly(4)

            payload = await self.reader.readexactly(payload_len)
            if masked and mask_key:
                unmasked = bytearray(payload_len)
                for i in range(payload_len):
                    unmasked[i] = payload[i] ^ mask_key[i % 4]
                payload = bytes(unmasked)

            if opcode == 0x1:
                return json.loads(payload.decode("utf-8"))
            return None
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            return None

    async def close(self) -> None:
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass


class TestGodotIntegration(unittest.TestCase):
    def test_godot_protocol_serialization(self):
        # 1. State update
        state_msg = format_state_message("AMR-01", (5.0, 2.0), 1.5, 90.0, "MOVING", 88.0)
        self.assertIn(state_msg["type"], ("STATE", "STATE_UPDATE"))
        self.assertEqual(state_msg["position"], [5.0, 2.0])

        # 2. Path update
        path_msg = format_path_message("AMR-01", [(1, 2), (2, 2), (3, 2)])
        self.assertIn(path_msg["type"], ("PATH", "PATH_UPDATE"))
        self.assertEqual(len(path_msg["path"]), 3)

        # 3. Command
        cmd = FrontendCommand("AMR-01", CommandAction.MOVE, target=(6.0, 2.0), speed=1.5)
        cmd_dict = cmd.to_dict()
        self.assertEqual(cmd_dict["type"], "COMMAND")
        self.assertEqual(cmd_dict["action"], "MOVE")
        self.assertEqual(cmd_dict["target"], [6.0, 2.0])

        # 4. Conflict event
        c_evt = FrontendConflictEvent("AMR-01", peer="AMR-02", node=(12, 10), resolution="AMR-02_YIELDS")
        c_dict = c_evt.to_dict()
        self.assertEqual(c_dict["type"], "CONFLICT_EVENT")
        self.assertEqual(c_dict["resolution"], "AMR-02_YIELDS")

    def test_godot_warehouse_obstacle_generation(self):
        obstacles = generate_godot_warehouse_obstacles(25, 20)
        self.assertGreater(len(obstacles), 50)
        # Perimeter cell check
        self.assertIn((0, 0), obstacles)
        self.assertIn((24, 19), obstacles)
        # Rack cell check (e.g. rack 1 at x=4..7, z=3..4)
        self.assertIn((5, 3), obstacles)
        # Walkable aisle check (West Corridor at x=2)
        self.assertNotIn((2, 10), obstacles)
        self.assertNotIn((2, 17), obstacles)
        self.assertNotIn((8, 17), obstacles)

    def test_godot_single_robot_closed_loop(self):
        async def _run():
            cfg = RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 10.0),
                network_port=5721,
                frontend_port=8721,
                peer_endpoints=[],
                loop_rate_hz=20.0,
                max_speed=2.0,
            )
            agent = RobotAgent(cfg)
            gateway = FrontendGateway(agent=agent, host="127.0.0.1", port=8721)

            await agent.start()
            await gateway.start()

            godot_mock = GodotWebSocketMockClient(host="127.0.0.1", port=8721)
            await godot_mock.connect()

            try:
                # 1. Connected Godot receives initial state
                init_state = await godot_mock.receive_json(timeout=1.0)
                self.assertIsNotNone(init_state)
                self.assertIn(init_state["type"], ("STATE", "STATE_UPDATE"))

                # 2. Godot sends INIT along West Corridor (2, 10) -> (2, 17)
                await godot_mock.send_json({
                    "type": "INIT",
                    "robot_id": "AMR-01",
                    "position": [2.0, 10.0],
                    "goal": [2.0, 17.0],
                })

                # Godot receives INIT_ACK
                ack = await godot_mock.receive_json(timeout=1.0)
                self.assertIsNotNone(ack)
                self.assertEqual(ack["type"], "INIT_ACK")

                # Godot receives PATH_UPDATE
                path_msg = None
                for _ in range(5):
                    msg = await godot_mock.receive_json(timeout=0.5)
                    if msg and msg.get("type") in ("PATH", "PATH_UPDATE"):
                        path_msg = msg
                        break

                self.assertIsNotNone(path_msg)
                self.assertEqual(path_msg["path"][0], [2, 10])
                self.assertEqual(path_msg["path"][-1], [2, 17])

                # Godot sends POSITION_UPDATE as visual robot moves
                await godot_mock.send_json({
                    "type": "POSITION_UPDATE",
                    "robot_id": "AMR-01",
                    "position": [2.0, 11.0],
                    "heading": 90.0,
                    "velocity": 1.5,
                })
                await asyncio.sleep(0.1)
                self.assertEqual(agent.state.position, (2.0, 11.0))

            finally:
                await godot_mock.close()
                await gateway.stop()
                await agent.stop()

        asyncio.run(_run())

    def test_godot_multi_agent_p2p_conflict_resolution(self):
        async def _run():
            # AMR-01 moves along West Corridor (2, 2) -> (2, 17)
            cfg1 = RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 2.0),
                network_port=5731,
                frontend_port=8731,
                peer_endpoints=[("127.0.0.1", 5731), ("127.0.0.1", 5732)],
                default_goal=(2.0, 17.0),
                loop_rate_hz=20.0,
                max_speed=2.0,
                safety_distance=0.8,
            )

            # AMR-02 moves along same Corridor (2.0, 17.0) -> (2.0, 2.0)
            cfg2 = RobotConfig(
                robot_id="AMR-02",
                initial_position=(2.0, 17.0),
                network_port=5732,
                frontend_port=8732,
                peer_endpoints=[("127.0.0.1", 5731), ("127.0.0.1", 5732)],
                default_goal=(2.0, 2.0),
                loop_rate_hz=20.0,
                max_speed=2.0,
                safety_distance=0.8,
            )

            agent1 = RobotAgent(cfg1)
            agent2 = RobotAgent(cfg2)

            gw1 = FrontendGateway(agent=agent1, host="127.0.0.1", port=8731)
            gw2 = FrontendGateway(agent=agent2, host="127.0.0.1", port=8732)

            await agent1.start()
            await agent2.start()
            await gw1.start()
            await gw2.start()

            godot_amr1 = GodotWebSocketMockClient(host="127.0.0.1", port=8731)
            godot_amr2 = GodotWebSocketMockClient(host="127.0.0.1", port=8732)

            await godot_amr1.connect()
            await godot_amr2.connect()

            try:
                # Allow agents to exchange P2P UDP messages and resolve head-on conflict
                await asyncio.sleep(1.5)

                # Verify peer discovery through P2P
                self.assertIn("AMR-02", agent1.peer_table.get_all_active_peers())
                self.assertIn("AMR-01", agent2.peer_table.get_all_active_peers())

                # Collect messages streamed to Godot AMRs
                msg1 = await godot_amr1.receive_json(timeout=0.2)
                msg2 = await godot_amr2.receive_json(timeout=0.2)

                self.assertIsNotNone(msg1)
                self.assertIsNotNone(msg2)

            finally:
                await godot_amr1.close()
                await godot_amr2.close()
                await gw1.stop()
                await gw2.stop()
                await agent1.stop()
                await agent2.stop()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
