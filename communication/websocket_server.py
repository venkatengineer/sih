"""
Async WebSocket Telemetry Gateway for Frontend Visualization.
Implements pure Python standard library WebSocket protocol (RFC 6455) server.
Broadcasts live fleet states, segment congestion, and explainable decision events.
"""

import asyncio
import json
import hashlib
import base64
import struct
import logging
from typing import Set, Dict, Any

logger = logging.getLogger(__name__)

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

class WebSocketServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Set[asyncio.StreamWriter] = set()
        self.server: Optional[asyncio.AbstractServer] = None
        self.on_message_callback: Optional[Any] = None

    async def start(self):
        try:
            self.server = await asyncio.start_server(self._handle_connection, self.host, self.port)
            logger.info(f"WebSocket server listening on ws://{self.host}:{self.port}")
        except Exception as e:
            logger.warning(f"Could not start WebSocket server on {self.port}: {e}")

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            # Perform HTTP WebSocket Handshake
            request_data = await reader.read(2048)
            request_text = request_data.decode('utf-8', errors='ignore')
            
            key = None
            for line in request_text.split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":")[1].strip()
                    break
                    
            if key:
                accept_key = base64.b64encode(
                    hashlib.sha1((key + GUID).encode('utf-8')).digest()
                ).decode('utf-8')
                
                response = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
                )
                writer.write(response.encode('utf-8'))
                await writer.drain()
                
                self.clients.add(writer)
                logger.info("WebSocket client connected.")
                
                # Keep connection open and process incoming control frames
                while True:
                    frame_hdr = await reader.read(2)
                    if not frame_hdr or len(frame_hdr) < 2:
                        break
                    opcode = frame_hdr[0] & 0x0F
                    if opcode == 0x8: # Connection Close
                        break
                    
                    payload_len = frame_hdr[1] & 0x7F
                    if payload_len == 126:
                        len_bytes = await reader.read(2)
                        payload_len = struct.unpack("!H", len_bytes)[0]
                    elif payload_len == 127:
                        len_bytes = await reader.read(8)
                        payload_len = struct.unpack("!Q", len_bytes)[0]
                        
                    is_masked = bool(frame_hdr[1] & 0x80)
                    mask = None
                    if is_masked:
                        mask = await reader.read(4)
                    payload = await reader.read(payload_len)

                    if payload and self.on_message_callback:
                        if is_masked and mask:
                            unmasked = bytearray(payload)
                            for i in range(len(payload)):
                                unmasked[i] ^= mask[i % 4]
                            msg_str = unmasked.decode('utf-8', errors='ignore')
                        else:
                            msg_str = payload.decode('utf-8', errors='ignore')

                        try:
                            msg_json = json.loads(msg_str)
                            if asyncio.iscoroutinefunction(self.on_message_callback):
                                asyncio.create_task(self.on_message_callback(msg_json))
                            else:
                                self.on_message_callback(msg_json)
                        except Exception as e:
                            logger.debug(f"WebSocket incoming JSON decode error: {e}")
        except Exception as e:
            logger.debug(f"WebSocket client disconnected: {e}")
        finally:
            self.clients.discard(writer)
            writer.close()

    def _encode_frame(self, message_str: str) -> bytes:
        payload = message_str.encode('utf-8')
        length = len(payload)
        
        if length <= 125:
            header = bytes([0x81, length])
        elif length <= 65535:
            header = bytes([0x81, 126]) + struct.pack("!H", length)
        else:
            header = bytes([0x81, 127]) + struct.pack("!Q", length)
            
        return header + payload

    async def broadcast(self, message: Dict[str, Any]):
        if not self.clients:
            return
        msg_str = json.dumps(message)
        frame = self._encode_frame(msg_str)
        
        clients_snapshot = list(self.clients)
        disconnected = set()
        for client in clients_snapshot:
            try:
                client.write(frame)
                await client.drain()
            except Exception:
                disconnected.add(client)
                
        for client in disconnected:
            self.clients.discard(client)

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
