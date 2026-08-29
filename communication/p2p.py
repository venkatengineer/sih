"""
Decentralized P2P UDP Communicator.
Enables peer-to-peer exchange of robot state, intent, and reservations without a central server.
"""

import socket
import asyncio
import logging
from typing import Callable, Optional, Dict, Any
from communication.protocol import MessageFactory

logger = logging.getLogger(__name__)

class P2PCommunicator:
    def __init__(self, robot_id: str, p2p_port: int = 5005, broadcast_ip: str = "255.255.255.255"):
        self.robot_id = robot_id
        self.p2p_port = p2p_port
        self.broadcast_ip = broadcast_ip
        self.running = False
        self.message_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Sockets
        self.send_sock: Optional[socket.socket] = None
        self.recv_sock: Optional[socket.socket] = None
        self._loop_task: Optional[asyncio.Task] = None

    def setup_sockets(self):
        # Create broadcast socket for sending
        self.send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Create receiving socket
        self.recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass  # SO_REUSEPORT not available on Windows
            
        try:
            self.recv_sock.bind(('', self.p2p_port))
            self.recv_sock.setblocking(False)
        except Exception as e:
            logger.warning(f"Could not bind P2P socket on port {self.p2p_port}: {e}")

    def broadcast(self, message: Dict[str, Any]):
        if not self.send_sock:
            self.setup_sockets()
        try:
            data = MessageFactory.serialize(message)
            self.send_sock.sendto(data, (self.broadcast_ip, self.p2p_port))
        except Exception as e:
            logger.debug(f"P2P Broadcast exception: {e}")

    def direct_send_in_memory(self, target_communicator: 'P2PCommunicator', message: Dict[str, Any]):
        """Helper for in-memory multi-robot unit testing without network loopback restrictions."""
        if target_communicator.message_callback:
            target_communicator.message_callback(message)

    async def start_listening(self, callback: Callable[[Dict[str, Any]], None]):
        self.message_callback = callback
        self.running = True
        if not self.recv_sock:
            self.setup_sockets()
            
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.recv_sock, 4096)
                msg = MessageFactory.deserialize(data)
                # Ignore self broadcast
                if msg.get("robot_id") != self.robot_id:
                    if self.message_callback:
                        self.message_callback(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(0.1)

    def stop(self):
        self.running = False
        if self._loop_task:
            self._loop_task.cancel()
        if self.send_sock:
            self.send_sock.close()
        if self.recv_sock:
            self.recv_sock.close()
