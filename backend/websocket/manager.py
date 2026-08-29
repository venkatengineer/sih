"""
WebSocket Connection Manager for browser operator consoles.
Streams real-time fleet events, decentralized auction bids, consensus awards, and telemetry.
"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Set, Dict, Any, Optional

logger = logging.getLogger("control_center.websocket")


class ConnectionManager:
    """Manages active WebSocket connections from web browsers."""

    def __init__(self):
        self.active_connections: Set[Any] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: Any) -> None:
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"Operator Console connected (total: {len(self.active_connections)})")

    async def disconnect(self, websocket: Any) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"Operator Console disconnected (total: {len(self.active_connections)})")

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast a structured event message to all connected browsers."""
        msg = {
            "type": "EVENT",
            "event": event_type,
            "timestamp": time.time(),
            "data": data,
        }
        await self.broadcast_json(msg)

    async def broadcast_json(self, message: Dict[str, Any]) -> None:
        """Send JSON message to all connected clients."""
        if not self.active_connections:
            return

        json_str = json.dumps(message)
        dead_conns = []

        async with self._lock:
            for conn in list(self.active_connections):
                try:
                    if hasattr(conn, "send_text"):
                        await conn.send_text(json_str)
                    elif hasattr(conn, "send_json"):
                        await conn.send_json(message)
                except Exception as e:
                    logger.debug(f"Failed sending to web client: {e}")
                    dead_conns.append(conn)

            for d in dead_conns:
                if d in self.active_connections:
                    self.active_connections.remove(d)


# Global singleton instance
ws_manager = ConnectionManager()
