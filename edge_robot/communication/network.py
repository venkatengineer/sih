"""
Asyncio UDP P2P Network Node for direct inter-robot communication.
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Tuple, Optional, Callable, Dict, Any

from edge_robot.communication.protocol import NetworkMessage


logger = logging.getLogger("edge_robot.network")


class P2PProtocol(asyncio.DatagramProtocol):
    """Underlying asyncio UDP datagram protocol handler."""

    def __init__(self, message_queue: asyncio.Queue[Tuple[NetworkMessage, Tuple[str, int]]]):
        self.message_queue = message_queue
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport):  # type: ignore
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        msg = NetworkMessage.from_json(data)
        if msg:
            try:
                self.message_queue.put_nowait((msg, addr))
            except asyncio.QueueFull:
                pass

    def error_received(self, exc: Exception):
        logger.warning(f"UDP error received: {exc}")


class P2PNetworkNode:
    """
    Decentralized P2P node.
    Listens on local UDP port and sends direct state / intent / obstacle messages to peers.
    """

    def __init__(
        self,
        robot_id: str,
        host: str = "127.0.0.1",
        port: int = 5001,
        peer_endpoints: Optional[List[Tuple[str, int]]] = None,
    ):
        self.robot_id = robot_id
        self.host = host
        self.port = port
        self.peer_endpoints: List[Tuple[str, int]] = peer_endpoints or []
        self._message_queue: asyncio.Queue[Tuple[NetworkMessage, Tuple[str, int]]] = asyncio.Queue(maxsize=1000)
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[P2PProtocol] = None
        self._is_running = False

    async def start(self) -> None:
        """Start UDP listener."""
        if self._is_running:
            return

        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: P2PProtocol(self._message_queue),
            local_addr=(self.host, self.port),
            allow_broadcast=True,
            reuse_port=True,
        )
        self._transport = transport
        self._protocol = protocol
        self._is_running = True
        logger.info(f"[{self.robot_id}] P2P Network Node listening on UDP {self.host}:{self.port}")

    async def stop(self) -> None:
        """Close UDP transport."""
        if self._transport:
            self._transport.close()
            self._transport = None
        self._is_running = False

    def send_to(self, message: NetworkMessage, host: str, port: int) -> None:
        """Send message directly to a target peer."""
        if not self._transport or not self._is_running:
            return
        payload = message.to_json().encode("utf-8")
        self._transport.sendto(payload, (host, port))

    def broadcast(self, message: NetworkMessage) -> None:
        """Broadcast message to all configured peer endpoints."""
        if not self._transport or not self._is_running:
            return

        payload = message.to_json().encode("utf-8")
        for (p_host, p_port) in self.peer_endpoints:
            # Do not send to self
            if p_host == self.host and p_port == self.port:
                continue
            try:
                self._transport.sendto(payload, (p_host, p_port))
            except Exception as e:
                logger.debug(f"Failed to send to {p_host}:{p_port}: {e}")

    def get_incoming_messages(self) -> List[Tuple[NetworkMessage, Tuple[str, int]]]:
        """Fetch all queued incoming messages without blocking."""
        messages: List[Tuple[NetworkMessage, Tuple[str, int]]] = []
        while not self._message_queue.empty():
            try:
                msg, addr = self._message_queue.get_nowait()
                messages.append((msg, addr))
            except asyncio.QueueEmpty:
                break
        return messages
