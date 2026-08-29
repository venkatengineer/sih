"""
Integration tests for Frontend Gateway WebSocket connectivity and closed-loop control.
"""

import unittest
import asyncio
import base64
import json
import os
import struct
from typing import Optional, Dict, Any, List, Tuple

from edge_robot.config import RobotConfig
from edge_robot.core.robot import RobotAgent
from edge_robot.gateway.session import FrontendGateway
from edge_robot.gateway.frontend_protocol import FrontendMessageType, CommandAction


class TestWebSocketClient:
    """Zero-dependency test client implementing RFC 6455 client handshake and framing."""

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

        # Read response headers until empty line
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
            header.append(0x80 | length)  # Mask bit set
        elif length <= 65535:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))

        header.extend(mask)

        # Apply client mask
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

            if opcode == 0x1:  # Text
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


class TestFrontendGateway(unittest.TestCase):
    def test_frontend_init_and_goal_flow(self):
        async def _run():
            cfg = RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 2.0),
                network_port=7701,
                peer_endpoints=[],
                loop_rate_hz=20.0,
                max_speed=2.0,
                static_obstacles=[],
            )
            agent = RobotAgent(cfg)
            gateway = FrontendGateway(agent=agent, host="127.0.0.1", port=9701)

            await agent.start()
            await gateway.start()

            client = TestWebSocketClient(host="127.0.0.1", port=9701)
            await client.connect()

            try:
                # 1. Connected client receives initial state update
                init_state = await client.receive_json(timeout=1.0)
                self.assertIsNotNone(init_state)
                self.assertIn(init_state["type"], ("STATE", "STATE_UPDATE"))
                self.assertEqual(init_state["robot_id"], "AMR-01")

                # 2. Send INIT command
                await client.send_json({
                    "type": "INIT",
                    "robot_id": "AMR-01",
                    "position": [2.0, 2.0],
                    "goal": [5.0, 2.0],
                })

                # Receive INIT_ACK
                ack = await client.receive_json(timeout=1.0)
                self.assertIsNotNone(ack)
                self.assertEqual(ack["type"], "INIT_ACK")
                self.assertEqual(agent.state.position, (2.0, 2.0))

                # Receive PATH message for newly planned route
                path_msg = None
                for _ in range(5):
                    msg = await client.receive_json(timeout=0.5)
                    if msg and msg.get("type") in ("PATH", "PATH_UPDATE"):
                        path_msg = msg
                        break

                self.assertIsNotNone(path_msg)
                self.assertEqual(path_msg["robot_id"], "AMR-01")
                self.assertEqual(path_msg["path"][0], [2, 2])
                self.assertEqual(path_msg["path"][-1], [5, 2])

                # 3. Simulate frontend visual position feedback
                await client.send_json({
                    "type": "POSITION",
                    "position": [3.0, 2.0],
                    "heading": 0.0,
                })
                await asyncio.sleep(0.1)
                self.assertEqual(agent.state.position, (3.0, 2.0))

            finally:
                await client.close()
                await gateway.stop()
                await agent.stop()

        asyncio.run(_run())

    def test_dynamic_obstacle_reroute_via_frontend(self):
        async def _run():
            cfg = RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 2.0),
                network_port=7702,
                peer_endpoints=[],
                loop_rate_hz=20.0,
                max_speed=2.0,
                static_obstacles=[],
            )
            agent = RobotAgent(cfg)
            gateway = FrontendGateway(agent=agent, host="127.0.0.1", port=9702)

            await agent.start()
            await gateway.start()

            client = TestWebSocketClient(host="127.0.0.1", port=9702)
            await client.connect()

            try:
                # Set goal straight across y=2
                agent.set_goal((6.0, 2.0))
                await asyncio.sleep(0.1)

                # Send dynamic obstacle right in the path at (3, 2)
                await client.send_json({
                    "type": "WORLD_UPDATE",
                    "obstacles": [
                        {"id": "OBS-99", "position": [3.0, 2.0], "radius": 0.5}
                    ]
                })

                # Allow agent loop to detect invalid path and reroute around obstacle
                await asyncio.sleep(0.3)

                # Path must not contain (3, 2)
                for node in agent.state.current_path:
                    self.assertNotEqual(node, (3, 2))

            finally:
                await client.close()
                await gateway.stop()
                await agent.stop()

        asyncio.run(_run())

    def test_two_robots_frontend_and_p2p_conflict(self):
        async def _run():
            # AMR-01 at (2, 2) targeting (6, 2) with high priority
            cfg1 = RobotConfig(
                robot_id="AMR-01",
                initial_position=(2.0, 2.0),
                network_port=7703,
                peer_endpoints=[("127.0.0.1", 7703), ("127.0.0.1", 7704)],
                default_goal=(6.0, 2.0),
                loop_rate_hz=20.0,
                max_speed=2.0,
                safety_distance=0.8,
                static_obstacles=[],
            )

            # AMR-02 at (6, 2) targeting (2, 2) with lower priority
            cfg2 = RobotConfig(
                robot_id="AMR-02",
                initial_position=(6.0, 2.0),
                network_port=7704,
                peer_endpoints=[("127.0.0.1", 7703), ("127.0.0.1", 7704)],
                default_goal=(2.0, 2.0),
                loop_rate_hz=20.0,
                max_speed=2.0,
                safety_distance=0.8,
                static_obstacles=[],
            )

            agent1 = RobotAgent(cfg1)
            agent2 = RobotAgent(cfg2)

            gateway1 = FrontendGateway(agent=agent1, host="127.0.0.1", port=9703)
            gateway2 = FrontendGateway(agent=agent2, host="127.0.0.1", port=9704)

            await agent1.start()
            await agent2.start()
            await gateway1.start()
            await gateway2.start()

            client1 = TestWebSocketClient(host="127.0.0.1", port=9703)
            client2 = TestWebSocketClient(host="127.0.0.1", port=9704)

            await client1.connect()
            await client2.connect()

            try:
                # Allow robots to run, communicate P2P, and negotiate head-on conflict
                await asyncio.sleep(1.5)

                # Verify peer discovery via P2P network
                self.assertIn("AMR-02", agent1.peer_table.get_all_active_peers())
                self.assertIn("AMR-01", agent2.peer_table.get_all_active_peers())

                # Collect messages streamed to frontend client 1 and client 2
                msg1 = await client1.receive_json(timeout=0.2)
                msg2 = await client2.receive_json(timeout=0.2)

                self.assertIsNotNone(msg1)
                self.assertIsNotNone(msg2)

            finally:
                await client1.close()
                await client2.close()
                await gateway1.stop()
                await gateway2.stop()
                await agent1.stop()
                await agent2.stop()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
