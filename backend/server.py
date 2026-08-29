"""
High-Performance Async HTTP & WebSocket Server for AMR Fleet Control Center.
Provides REST APIs, WebSocket live event streaming, and static UI file delivery on http://localhost:8000.
"""

from __future__ import annotations
import asyncio
import base64
import hashlib
import json
import logging
import mimetypes
import os
import struct
import sys
import time
import urllib.parse
from typing import Dict, Any, Optional, Tuple, Set

# Ensure /data/sih/robot and /data/sih are in sys.path
if "/data/sih/robot" not in sys.path:
    sys.path.insert(0, "/data/sih/robot")
if "/data/sih" not in sys.path:
    sys.path.insert(0, "/data/sih")

from control_center.backend.websocket.manager import ws_manager
from control_center.backend.bridge.robot_bridge import fleet_bridge
from control_center.backend.api import tasks as tasks_api
from control_center.backend.api import robots as robots_api
from control_center.backend.api import fleet as fleet_api
from control_center.backend.api import system as system_api
from control_center.backend.api import shelves as shelves_api

logger = logging.getLogger("control_center.server")

WS_MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class AsyncControlCenterServer:
    """
    Asynchronous Control Center Server serving REST APIs, WebSockets, and UI.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8000, static_dir: Optional[str] = None):
        self.host = host
        self.port = port
        self.static_dir = static_dir or os.path.join(os.path.dirname(__file__), "static")
        self.is_running = False
        self._server: Optional[asyncio.Server] = None

    async def start(self) -> None:
        """Start Control Center API & WebSocket Server."""
        if self.is_running:
            return

        # Start fleet bridge
        await fleet_bridge.start(spawn_embedded=True)

        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self.is_running = True
        logger.info(f"🚀 AMR Web Control Center running at: http://localhost:{self.port}")

    async def stop(self) -> None:
        """Stop server gracefully."""
        self.is_running = False
        await fleet_bridge.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        logger.info("Control Center server stopped.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")
        remote_addr = f"{addr[0]}:{addr[1]}" if addr else "unknown"

        try:
            # Read HTTP request header lines
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

            # Parse request line: METHOD PATH HTTP/VERSION
            parts = request_lines[0].split(" ")
            if len(parts) < 2:
                writer.close()
                return

            method = parts[0].upper()
            url_path = parts[1]

            # Parse headers
            headers: Dict[str, str] = {}
            for line in request_lines[1:]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    headers[key.strip().lower()] = val.strip()

            # Handle WebSocket Upgrade on /ws
            if headers.get("upgrade", "").lower() == "websocket":
                await self._handle_websocket_upgrade(reader, writer, headers, remote_addr)
                return

            # Read HTTP Body if Content-Length present
            content_length = int(headers.get("content-length", 0))
            body_bytes = b""
            if content_length > 0:
                body_bytes = await reader.readexactly(content_length)

            # Route HTTP Request
            await self._route_http_request(writer, method, url_path, headers, body_bytes)

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            logger.debug(f"HTTP handler error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _route_http_request(
        self,
        writer: asyncio.StreamWriter,
        method: str,
        path: str,
        headers: Dict[str, str],
        body_bytes: bytes,
    ) -> None:
        parsed_url = urllib.parse.urlparse(path)
        clean_path = parsed_url.path.rstrip("/")
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Handle CORS Options preflight
        if method == "OPTIONS":
            self._send_cors_response(writer)
            return

        body_json = {}
        if body_bytes:
            try:
                body_json = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                pass

        # --- REST API ROUTES ---
        if clean_path.startswith("/api"):
            # GET /api/fleet
            if clean_path == "/api/fleet" and method == "GET":
                res = fleet_api.handle_get_fleet()
                self._send_json_response(writer, res)

            # GET /api/robots
            elif clean_path == "/api/robots" and method == "GET":
                res = robots_api.handle_get_robots()
                self._send_json_response(writer, res)

            # GET /api/robots/{robot_id}
            elif clean_path.startswith("/api/robots/") and method == "GET":
                robot_id = clean_path.split("/api/robots/")[1]
                res = robots_api.handle_get_robot(robot_id)
                status_code = res[1] if isinstance(res, tuple) else 200
                data = res[0] if isinstance(res, tuple) else res
                self._send_json_response(writer, data, status_code)

            # POST /api/robots/{robot_id}/pause
            elif clean_path.startswith("/api/robots/") and clean_path.endswith("/pause") and method == "POST":
                robot_id = clean_path.split("/api/robots/")[1].split("/pause")[0]
                res = robots_api.handle_pause_robot(robot_id)
                self._send_json_response(writer, res)

            # POST /api/robots/{robot_id}/resume
            elif clean_path.startswith("/api/robots/") and clean_path.endswith("/resume") and method == "POST":
                robot_id = clean_path.split("/api/robots/")[1].split("/resume")[0]
                res = robots_api.handle_resume_robot(robot_id)
                self._send_json_response(writer, res)

            # GET /api/tasks
            elif clean_path == "/api/tasks" and method == "GET":
                res = tasks_api.handle_get_tasks()
                self._send_json_response(writer, res)

            # POST /api/tasks
            elif clean_path == "/api/tasks" and method == "POST":
                res = tasks_api.handle_create_task(body_json)
                status_code = res[1] if isinstance(res, tuple) else 200
                data = res[0] if isinstance(res, tuple) else res
                self._send_json_response(writer, data, status_code)

            # GET /api/tasks/{task_id}
            elif clean_path.startswith("/api/tasks/") and method == "GET":
                task_id = clean_path.split("/api/tasks/")[1]
                res = tasks_api.handle_get_task(task_id)
                status_code = res[1] if isinstance(res, tuple) else 200
                data = res[0] if isinstance(res, tuple) else res
                self._send_json_response(writer, data, status_code)

            # POST /api/tasks/{task_id}/cancel
            elif clean_path.startswith("/api/tasks/") and clean_path.endswith("/cancel") and method == "POST":
                task_id = clean_path.split("/api/tasks/")[1].split("/cancel")[0]
                res = tasks_api.handle_cancel_task(task_id)
                status_code = res[1] if isinstance(res, tuple) else 200
                data = res[0] if isinstance(res, tuple) else res
                self._send_json_response(writer, data, status_code)

            # GET /api/shelves
            elif clean_path == "/api/shelves" and method == "GET":
                res = shelves_api.handle_get_shelves()
                self._send_json_response(writer, res)

            # GET /api/shelves/{shelf_id}
            elif clean_path.startswith("/api/shelves/") and method == "GET":
                shelf_id = clean_path.split("/api/shelves/")[1]
                res = shelves_api.handle_get_shelf(shelf_id)
                status_code = res[1] if isinstance(res, tuple) else 200
                data = res[0] if isinstance(res, tuple) else res
                self._send_json_response(writer, data, status_code)

            # GET /api/events
            elif clean_path == "/api/events" and method == "GET":
                limit = int(query_params.get("limit", ["50"])[0])
                res = system_api.handle_get_events(limit=limit)
                self._send_json_response(writer, res)

            # GET /api/system
            elif clean_path == "/api/system" and method == "GET":
                res = system_api.handle_get_system()
                self._send_json_response(writer, res)

            else:
                self._send_json_response(writer, {"status": "error", "message": "Endpoint not found"}, 404)

            return

        # --- STATIC FILE SERVING ---
        await self._serve_static_file(writer, clean_path)

    async def _serve_static_file(self, writer: asyncio.StreamWriter, clean_path: str) -> None:
        """Serve HTML/CSS/JS frontend files."""
        if clean_path == "" or clean_path == "/":
            rel_path = "index.html"
        else:
            rel_path = clean_path.lstrip("/")

        file_path = os.path.join(self.static_dir, rel_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            # Fallback to index.html for Single-Page Application (SPA) routing
            file_path = os.path.join(self.static_dir, "index.html")

        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                with open(file_path, "rb") as f:
                    content = f.read()

                content_type, _ = mimetypes.guess_type(file_path)
                content_type = content_type or "application/octet-stream"

                header = (
                    "HTTP/1.1 200 OK\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Length: {len(content)}\r\n"
                    "Access-Control-Allow-Origin: *\r\n"
                    "Connection: close\r\n\r\n"
                )
                writer.write(header.encode("utf-8") + content)
                await writer.drain()
                return
            except Exception as e:
                logger.debug(f"Static file read error: {e}")

        # 404 Default
        not_found = b"<h1>404 Not Found</h1>"
        header = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(not_found)}\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(header.encode("utf-8") + not_found)
        await writer.drain()

    def _send_json_response(self, writer: asyncio.StreamWriter, data: Any, status_code: int = 200) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        status_text = "OK" if status_code == 200 else ("Created" if status_code == 201 else "Error")
        header = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(header.encode("utf-8") + body)

    def _send_cors_response(self, writer: asyncio.StreamWriter) -> None:
        header = (
            "HTTP/1.1 204 No Content\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
            "Connection: close\r\n\r\n"
        )
        writer.write(header.encode("utf-8"))

    # =========================================================================
    # WebSocket Protocol Handling
    # =========================================================================

    async def _handle_websocket_upgrade(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        headers: Dict[str, str],
        remote_addr: str,
    ) -> None:
        sec_key = headers.get("sec-websocket-key")
        if not sec_key:
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
            return

        accept_raw = hashlib.sha1((sec_key + WS_MAGIC_GUID).encode("utf-8")).digest()
        accept_key = base64.b64encode(accept_raw).decode("utf-8")

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()

        # Connect client into ws_manager
        client_conn = WebClientConnection(reader, writer, remote_addr)
        await ws_manager.connect(client_conn)

        # Send initial snapshot of fleet & tasks
        init_snapshot = {
            "type": "SNAPSHOT",
            "fleet": fleet_bridge.get_fleet_summary(),
            "tasks": fleet_bridge.get_tasks(),
            "system": fleet_bridge.get_system_status(),
        }
        await client_conn.send_json(init_snapshot)

        # Read loop
        try:
            await self._read_ws_frame_loop(client_conn)
        finally:
            await ws_manager.disconnect(client_conn)
            await client_conn.close()

    async def _read_ws_frame_loop(self, client: WebClientConnection) -> None:
        reader = client.reader
        while self.is_running and not client.is_closed:
            head = await reader.readexactly(2)
            b1, b2 = head[0], head[1]
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

            if opcode == 0x1:  # Text frame from browser
                try:
                    data = json.loads(payload.decode("utf-8"))
                    # If client requests an action
                    action = data.get("action")
                    if action == "PING":
                        await client.send_json({"type": "PONG", "timestamp": time.time()})
                except Exception:
                    pass

            elif opcode == 0x8:  # Close
                break
            elif opcode == 0x9:  # Ping
                pong = bytes([0x8A, len(payload)]) + payload
                client.writer.write(pong)
                await client.writer.drain()


class WebClientConnection:
    """Represents a WebSocket connection to a browser."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, remote_addr: str):
        self.reader = reader
        self.writer = writer
        self.remote_addr = remote_addr
        self.is_closed = False
        self._lock = asyncio.Lock()

    async def send_text(self, text: str) -> None:
        if self.is_closed:
            return
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(127)
            header.extend(struct.pack("!Q", length))

        frame = bytes(header) + payload
        async with self._lock:
            try:
                self.writer.write(frame)
                await self.writer.drain()
            except Exception:
                self.is_closed = True

    async def send_json(self, data: Dict[str, Any]) -> None:
        await self.send_text(json.dumps(data))

    async def close(self) -> None:
        self.is_closed = True
        try:
            self.writer.write(bytes([0x88, 0x00]))
            await self.writer.drain()
            self.writer.close()
        except Exception:
            pass
