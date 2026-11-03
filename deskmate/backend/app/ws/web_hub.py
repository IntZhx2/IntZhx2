"""为浏览器提供独立有界发送队列和 200ms 浅合并增量广播。"""

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

from app.clock import Clock
from app.ws.envelope import envelope

logger = logging.getLogger(__name__)


class WebHub:
    def __init__(self, clock: Clock, interval: float) -> None:
        self.clock, self.interval = clock, interval
        self.clients: dict[WebSocket, asyncio.Queue[dict[str, Any]]] = {}
        self.pending: dict[str, Any] = {}
        self.flush_task: asyncio.Task[None] | None = None

    def attach(self, ws: WebSocket, snapshot: dict[str, Any]) -> None:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=128)
        self.clients[ws] = queue
        queue.put_nowait(envelope(self.clock, "state.snapshot", snapshot))

    async def sender(self, ws: WebSocket) -> None:
        queue = self.clients[ws]
        while True:
            await asyncio.wait_for(ws.send_json(await queue.get()), timeout=5)

    def detach(self, ws: WebSocket) -> None:
        self.clients.pop(ws, None)

    async def publish(self, name: str, payload: dict[str, Any]) -> None:
        message = envelope(self.clock, name, payload)
        for ws, queue in list(self.clients.items()):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("断开无法及时消费状态的网页客户端")
                self.detach(ws)
                await ws.close(code=1013)

    def patch(self, changed: dict[str, Any]) -> None:
        self.pending.update(changed)
        if self.flush_task is None or self.flush_task.done():
            self.flush_task = asyncio.create_task(self._flush())

    async def _flush(self) -> None:
        await self.clock.sleep(self.interval)
        pending, self.pending = self.pending, {}
        await self.publish("state.patch", pending)

    async def close(self) -> None:
        if self.flush_task:
            self.flush_task.cancel()
            await asyncio.gather(self.flush_task, return_exceptions=True)
        for ws in list(self.clients):
            await ws.close(code=1001)
        self.clients.clear()
