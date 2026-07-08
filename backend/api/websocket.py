"""
TREDO — WebSocket Manager
Manages WebSocket connections for live event streaming to Electron.
Subscribes to Event Bus and broadcasts all events to connected clients.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from backend.core.messages import BaseMessage

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections.
    Subscribes to Event Bus so any published event gets forwarded
    to all connected WebSocket clients.

    Usage:
        manager = WebSocketManager()

        # In WebSocket endpoint:
        await manager.connect(websocket)
        # ... client receives events until disconnect
        manager.disconnect(websocket)

        # From Event Bus handler:
        await manager.broadcast({"type": "trade", "data": {...}})
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WebSocket connected — total: %d", self.connection_count)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WebSocket disconnected — total: %d", self.connection_count)

    async def broadcast(self, data: dict[str, Any]) -> int:
        """
        Send data to ALL connected clients.
        Returns number of clients that received the message.
        Silently removes dead connections.
        """
        if not self._connections:
            return 0

        dead: list[WebSocket] = []
        sent = 0
        payload = json.dumps(data, default=str)

        for ws in self._connections:
            try:
                await ws.send_text(payload)
                sent += 1
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

        return sent

    async def broadcast_event(self, message: BaseMessage) -> None:
        """
        Broadcast a BaseMessage from the Event Bus to all WS clients.
        This is the handler subscribed to all event types.
        """
        data = {
            "type": message.type_name,
            "source": message.source,
            "timestamp": message.timestamp,
        }
        # Add all public fields from the message
        for key, value in message.__dict__.items():
            if not key.startswith("_") and key not in data:
                data[key] = value

        await self.broadcast(data)

    async def close_all(self) -> None:
        """Close all WebSocket connections. For shutdown."""
        for ws in list(self._connections):
            try:
                await ws.close()
            except Exception:
                pass
        self._connections.clear()
