"""WebSocket fan-out with one retained latest payload per message type."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass
class Client:
    websocket: WebSocket
    pending: dict[str, str]
    wake: asyncio.Event
    sender: asyncio.Task | None = None


class WebSocketManager:
    def __init__(self, queue_size: int = 4) -> None:
        self.queue_size = max(1, queue_size)
        self.clients: dict[int, Client] = {}
        self.lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self.clients)

    async def connect(self, websocket: WebSocket) -> Client:
        await websocket.accept()
        client = Client(websocket=websocket, pending={}, wake=asyncio.Event())
        client.sender = asyncio.create_task(self._sender(client))
        async with self.lock:
            self.clients[id(client)] = client
        return client

    async def disconnect(self, client: Client) -> None:
        async with self.lock:
            self.clients.pop(id(client), None)
        if client.sender:
            client.sender.cancel()
            try:
                await client.sender
            except (asyncio.CancelledError, Exception):
                pass

    async def _sender(self, client: Client) -> None:
        while True:
            await client.wake.wait()
            while client.pending:
                key = next(iter(client.pending))
                payload = client.pending.pop(key)
                await client.websocket.send_text(payload)
            client.wake.clear()

    def _put_latest(self, client: Client, key: str, payload: str) -> None:
        # Replacing by key means a slow browser can never accumulate old RGB,
        # tactile or hand frames. Memory remains bounded by message types.
        if key not in client.pending and len(client.pending) >= self.queue_size:
            client.pending.pop(next(iter(client.pending)))
        client.pending[key] = payload
        client.wake.set()

    async def send(self, client: Client, data: dict[str, Any]) -> None:
        key = str(data.get("type", "message"))
        self._put_latest(client, key, json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    async def broadcast(self, data: dict[str, Any]) -> None:
        key = str(data.get("type", "message"))
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        async with self.lock:
            clients = list(self.clients.values())
        for client in clients:
            self._put_latest(client, key, payload)

    async def close_all(self) -> None:
        async with self.lock:
            clients = list(self.clients.values())
        for client in clients:
            await self.disconnect(client)
