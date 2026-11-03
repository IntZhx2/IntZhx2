"""管理单个真实 Edge 连接，Future 关联 RPC，断线取消且禁止执行中自动重放。"""

import asyncio
import logging
from typing import Any

from fastapi import WebSocket
from jsonschema import Draft202012Validator

from app.agent.tools import TOOL_SCHEMAS, ToolError, speech, validate_call
from app.clock import Clock
from app.engine.state_store import StateStore
from app.sim.virtual_edge import VirtualEdge
from app.ws.envelope import envelope

logger = logging.getLogger(__name__)


class EdgeHub:
    def __init__(
        self,
        store: StateStore,
        clock: Clock,
        virtual: VirtualEdge,
        settings: dict[str, Any],
        demo_only: bool,
    ) -> None:
        self.store, self.clock, self.virtual = store, clock, virtual
        self.settings, self.demo_only = settings, demo_only
        self.ws: WebSocket | None = None
        self.pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.registered: dict[str, dict[str, Any]] = {}
        self.send_lock = asyncio.Lock()
        self.last_seen = clock.monotonic()

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        return self.registered if self.ws else self.virtual.tools

    async def register(self, ws: WebSocket, payload: dict[str, Any]) -> None:
        if self.demo_only or (self.ws and self.ws is not ws):
            raise ToolError("NOT_ALLOWED", "已有 Edge 在线，或当前处于演示模式")
        devices = payload.get("devices")
        if not isinstance(devices, dict) or not isinstance(payload.get("tools"), list):
            raise ToolError("BAD_ARGS")
        tools = {}
        for raw in payload["tools"][:100]:
            function = raw.get("function", raw)
            name, parameters = function.get("name"), function.get("parameters")
            if name not in TOOL_SCHEMAS or not isinstance(parameters, dict):
                continue
            # 禁止远程引用及通过额外定义扩展到外部资源。
            if "$ref" in str(parameters) or len(str(parameters)) > 20000:
                continue
            try:
                Draft202012Validator.check_schema(parameters)
            except Exception:
                logger.warning("忽略无效 ToolSpec: %s", name)
                continue
            tools[name] = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": function.get("description", name)[:500],
                    "parameters": parameters,
                },
            }
        if not tools:
            raise ToolError("BAD_ARGS", "没有有效工具")
        for name, value in devices.items():
            if name in self.store.data["devices"] and isinstance(value, dict):
                self.store.device(name, value)
        self.ws, self.registered = ws, tools
        self.last_seen = self.clock.monotonic()
        self.store.update(edge_online=True, demo_mode=False)

    async def send(self, message: dict[str, Any]) -> None:
        async with self.send_lock:
            if self.ws is None:
                raise ToolError("DEVICE_OFFLINE")
            await asyncio.wait_for(self.ws.send_json(message), 5)

    async def call(  # noqa: ASYNC109 -- CONTRACTS 明确要求 timeout 参数
        self, tool: str, args: dict[str, Any], timeout: float | None = None
    ) -> dict[str, Any]:
        args = dict(args)
        if tool == "speaker_tts" and isinstance(args.get("text"), str):
            args["text"] = speech(args["text"])
        validate_call(tool, args, self.settings)
        if self.ws is None:
            # 只在调用前决定模拟路径。RPC 执行中断线绝不重放，以免真实设备执行两次。
            return await self.virtual.call(tool, args)
        if tool not in self.registered:
            raise ToolError("NOT_ALLOWED", "Edge 未注册该工具")
        schema = self.registered[tool]["function"]["parameters"]
        if list(Draft202012Validator(schema).iter_errors(args)):
            raise ToolError("BAD_ARGS")
        message = envelope(self.clock, "tool.call", {"tool": tool, "args": args}, "cmd")
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending[message["id"]] = future
        try:
            await self.send(message)
            data = await asyncio.wait_for(future, timeout or TOOL_SCHEMAS[tool][1])
            if tool in {"lamp_set", "ac_set", "plug_set"}:
                self.store.device(tool.removesuffix("_set"), data)
            return data
        except TimeoutError as exc:
            raise ToolError("TIMEOUT") from exc
        except (OSError, RuntimeError) as exc:
            raise ToolError("DEVICE_OFFLINE") from exc
        finally:
            self.pending.pop(message["id"], None)
            if not future.done():
                future.cancel()

    def resolve(self, payload: dict[str, Any]) -> None:
        future = self.pending.get(payload.get("call_id"))
        if future and not future.done():
            if payload.get("ok") is True and isinstance(payload.get("data"), dict):
                future.set_result(payload["data"])
            else:
                error = payload.get("error")
                future.set_exception(ToolError(str(error or "INTERNAL").split(":")[0]))

    def disconnect(self, ws: WebSocket) -> None:
        if self.ws is not ws:
            return
        self.ws = None
        self.registered = {}
        for future in self.pending.values():
            if not future.done():
                future.set_exception(ToolError("DEVICE_OFFLINE"))
        self.pending.clear()
        self.virtual.reset_devices()
        self.store.update(edge_online=False, demo_mode=True)
