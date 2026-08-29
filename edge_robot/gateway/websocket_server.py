"""
Zero-dependency Asyncio WebSocket Server (RFC 6455).
Provides high-performance, edge-friendly WebSocket connectivity to frontend simulations.
"""

from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import logging
import struct
from typing import Callable, Optional, Set, Dict, Any, Awaitable

logger = logging.getLogger("edge_robot.gateway")

WS_MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketConnection:
    """Represents a single active WebSocket client connection."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, remote_addr: str):
        self.reader = reader
        self.writer = writer
        self.remote_addr = remote_addr
        self.is_closed = False
        self._write_lock = asyncio.Lock()

    async def send_text(self, message: str | Dict[str, Any]) -> None:
        """Send a UTF-8 text frame to this client."""
        if self.is_closed:
            return

        if isinstance(message, dict):
            text = json.dumps(message)
        else:
            text = str(message)

        payload = text.encode("utf-8")
        header = bytearray()
        # Fin bit set (0x80) + Text frame opcode (0x01) = 0x81
        header.append(0x81)

        length = len(payload)
        # Server frames are not masked (mask bit 0)
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))

        frame = bytes(header) + payload
        async with self._write_lock:
            try:
                self.writer.write(frame)
                await self.writer.drain()
            except Exception as e:
                logger.debug(f"Failed sending frame to {self.remote_addr}: {e}")
                self.is_closed = True

    async def send_json(self, data: Dict[str, Any]) -> None:
        """Helper to send JSON object."""
        await self.send_text(data)

    async def close(self) -> None:
        """Close connection."""
        if self.is_closed:
            return
        self.is_closed = True
        try:
            # Send Close frame (opcode 0x88)
            close_frame = bytes([0x88, 0x00])
            self.writer.write(close_frame)
            await self.writer.drain()
        except Exception:
            pass
        finally:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass


class AsyncWebSocketServer:
    """
    Lightweight, self-contained WebSocket server.
    Binds to (host, port) and calls message_handler(conn, message_str) on each incoming frame.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8001,
        message_handler: Optional[Callable[[WebSocketConnection, str], Awaitable[None]]] = None,
        connect_handler: Optional[Callable[[WebSocketConnection], Awaitable[None]]] = None,
        disconnect_handler: Optional[Callable[[WebSocketConnection], Awaitable[None]]] = None,
    ):
        self.host = host
        self.port = port
        self.message_handler = message_handler
        self.connect_handler = connect_handler
        self.disconnect_handler = disconnect_handler
        self.clients: Set[WebSocketConnection] = set()
        self._server: Optional[asyncio.Server] = None
        self.is_running = False

    async def start(self) -> None:
        """Start listening for incoming WebSocket connections."""
        if self.is_running:
            return

        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self.is_running = True
        logger.info(f"WebSocket Server listening on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop server and close all active client sessions."""
        self.is_running = False
        for client in list(self.clients):
            await client.close()
        self.clients.clear()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def broadcast(self, message: str | Dict[str, Any]) -> None:
        """Send message to all connected clients."""
        if not self.clients:
            return
        tasks = [client.send_text(message) for client in list(self.clients)]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming TCP connection and perform WebSocket handshake."""
        addr = writer.get_extra_info("peername")
        remote_addr = f"{addr[0]}:{addr[1]}" if addr else "unknown"

        try:
            # 1. Read HTTP handshake request headers
            request_lines = []
            while True:
                line_bytes = await reader.readline()
                if not line_bytes:
                    writer.close()
                    return
                line = line_bytes.decode("utf-8", errors="ignore").rstrip("\r\n")
                if line == "":
                    break
                request_lines.append(line)

            if not request_lines:
                writer.close()
                return

            headers: Dict[str, str] = {}
            for line in request_lines[1:]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    headers[key.strip().lower()] = val.strip()

            # Verify WebSocket upgrade request
            sec_key = headers.get("sec-websocket-key")
            if not sec_key:
                writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
                return

            # Compute Sec-WebSocket-Accept
            accept_raw = hashlib.sha1((sec_key + WS_MAGIC_GUID).encode("utf-8")).digest()
            accept_key = base64.b64encode(accept_raw).decode("utf-8")

            # Send HTTP 101 Switching Protocols response
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
            )
            writer.write(response.encode("utf-8"))
            await writer.drain()

            conn = WebSocketConnection(reader, writer, remote_addr)
            self.clients.add(conn)
            logger.info(f"Frontend simulation connected from {remote_addr}")

            if self.connect_handler:
                try:
                    await self.connect_handler(conn)
                except Exception as e:
                    logger.error(f"Error in connect_handler: {e}")

            # 2. Read WebSocket frames loop
            await self._read_frame_loop(conn)

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug(f"Client connection error ({remote_addr}): {e}")
        finally:
            if conn in self.clients:
                self.clients.remove(conn)
            await conn.close()
            if self.disconnect_handler:
                try:
                    await self.disconnect_handler(conn)
                except Exception:
                    pass
            logger.info(f"Frontend connection closed: {remote_addr}")

    async def _read_frame_loop(self, conn: WebSocketConnection) -> None:
        """Decode frames from client (masked according to RFC 6455)."""
        reader = conn.reader

        while self.is_running and not conn.is_closed:
            # Read first 2 bytes
            head = await reader.readexactly(2)
            b1, b2 = head[0], head[1]

            fin = (b1 & 0x80) != 0
            opcode = b1 & 0x0F
            masked = (b2 & 0x80) != 0
            payload_len = b2 & 0x7F

            if payload_len == 126:
                ext_len = await reader.readexactly(2)
                payload_len = struct.unpack("!H", ext_len)[0]
            elif payload_len == 127:
                ext_len = await reader.readexactly(8)
                payload_len = struct.unpack("!Q", ext_len)[0]

            mask_key = None
            if masked:
                mask_key = await reader.readexactly(4)

            payload = await reader.readexactly(payload_len)
            if masked and mask_key:
                unmasked = bytearray(payload_len)
                for i in range(payload_len):
                    unmasked[i] = payload[i] ^ mask_key[i % 4]
                payload = bytes(unmasked)

            # Process Opcode
            if opcode == 0x1:  # Text frame
                text_msg = payload.decode("utf-8", errors="replace")
                if self.message_handler:
                    try:
                        await self.message_handler(conn, text_msg)
                    except Exception as e:
                        logger.error(f"Error handling websocket message: {e}", exc_info=True)

            elif opcode == 0x8:  # Close frame
                await conn.close()
                break

            elif opcode == 0x9:  # Ping frame
                # Respond with Pong (opcode 0xA)
                pong_frame = bytes([0x8A, len(payload)]) + payload
                async with conn._write_lock:
                    conn.writer.write(pong_frame)
                    await conn.writer.drain()
