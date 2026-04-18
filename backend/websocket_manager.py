"""
WebSocket connection manager for real-time staff notifications.

Each authenticated IT staff member who has the dashboard open holds
a WebSocket connection. When a relevant event occurs (ticket assigned,
comment added), the server pushes a JSON message to all connected
sessions for that user.
"""
import logging
from typing import Dict, List

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # username → list of active WebSocket connections (multiple tabs)
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, username: str) -> None:
        await websocket.accept()
        self._connections.setdefault(username, []).append(websocket)
        logger.debug("WS connected: %s (%d sessions)", username,
                     len(self._connections[username]))

    def disconnect(self, websocket: WebSocket, username: str) -> None:
        conns = self._connections.get(username, [])
        self._connections[username] = [ws for ws in conns if ws is not websocket]
        if not self._connections[username]:
            del self._connections[username]
        logger.debug("WS disconnected: %s", username)

    async def push(self, username: str, payload: dict) -> None:
        """Push a JSON payload to all open sessions for a given user."""
        dead: List[WebSocket] = []
        for ws in self._connections.get(username, []):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        # Clean up stale connections
        for ws in dead:
            self.disconnect(ws, username)

    async def broadcast_to_users(self, usernames: List[str], payload: dict) -> None:
        """Push to multiple users at once (e.g. all technicians on a ticket)."""
        for username in set(usernames):
            await self.push(username, payload)


# Singleton — imported by main.py and routers
ws_manager = ConnectionManager()
