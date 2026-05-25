"""
WebSocket Manager — manages connected dashboard clients and broadcasts messages.

Architecture:
    - Maintains a set of active WebSocket connections
    - Broadcasts status snapshots, metrics, and events to all clients
    - Removes disconnected clients automatically
"""
import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info("WebSocket client connected. Total: %d", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info("WebSocket client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, message: dict) -> None:
        """Broadcast JSON message to all connected clients."""
        if not self._connections:
            return

        payload = json.dumps(message, default=str)
        dead: Set[WebSocket] = set()

        async with self._lock:
            targets = set(self._connections)

        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._connections -= dead
            logger.debug("Removed %d dead WebSocket connections", len(dead))

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton instance
ws_manager = WebSocketManager()
