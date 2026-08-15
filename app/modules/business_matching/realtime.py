import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ConversationHub:
    """Process-local WebSocket fan-out; use Redis pub/sub when scaling workers."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, conversation_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[conversation_id].add(websocket)

    async def disconnect(self, conversation_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(conversation_id)
            if sockets:
                sockets.discard(websocket)
                if not sockets:
                    self._connections.pop(conversation_id, None)

    async def broadcast(self, conversation_id: UUID, event: dict) -> None:
        async with self._lock:
            sockets = list(self._connections.get(conversation_id, ()))
        stale: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_json(event)
            except Exception:
                stale.append(socket)
        for socket in stale:
            await self.disconnect(conversation_id, socket)


conversation_hub = ConversationHub()
