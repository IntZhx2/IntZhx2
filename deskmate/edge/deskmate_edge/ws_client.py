"""DeskMate Edge WebSocket 客户端 (ws_client.py)
维护与后端长连接通道、握手 edge.hello、自动心跳、指令分发与指数退避断线重连
遵循 CONTRACTS.md §1 与 §3 规范
"""

import asyncio
import json
import logging
from typing import Any
import websockets
from websockets.client import WebSocketClientProtocol
from .config import settings
from .protocol import EdgeHelloPayload, WsEnvelope
from .tool_registry import registry

logger = logging.getLogger("deskmate_edge.ws_client")


class EdgeWsClient:
    """边缘端 WebSocket 通信客户端"""

    def __init__(self, backend_url: str | None = None, token: str | None = None):
        self.backend_url = backend_url or settings.BACKEND_WS_URL
        self.token = token or settings.EDGE_TOKEN
        self._ws: WebSocketClientProtocol | None = None
        self._running = False
        self._heartbeat_task: asyncio.Task | None = None

    async def start(self):
        """启动连接主循环（包含指数退避重连）"""
        self._running = True
        backoff = 1.0

        while self._running:
            url = f"{self.backend_url.rstrip('/')}?token={self.token}"
            logger.info(f"正在连接后端 WebSocket: {self.backend_url} ...")

            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    backoff = 1.0
                    logger.info("WebSocket 连接建立成功！")

                    # 1. 建立成功后发送第一条握手包 edge.hello
                    await self._send_edge_hello()

                    # 2. 启动 20 秒定时心跳保活任务
                    self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

                    # 3. 消息接收与处理循环
                    async for raw_msg in ws:
                        await self._handle_message(raw_msg)

            except (websockets.ConnectionClosed, ConnectionError, OSError) as e:
                logger.warning(f"WebSocket 连接断开: {e}")
            except Exception as e:
                logger.exception(f"WebSocket 运行时发生异常: {e}")
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    self._heartbeat_task = None
                self._ws = None

            if self._running:
                logger.info(f"{backoff:.1f} 秒后尝试重新连接...")
                await asyncio.sleep(backoff)
                # 指数退避：1, 2, 4, 8, 16, 30...
                backoff = min(backoff * 2, 30.0)

    async def stop(self):
        """停止客户端"""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def send_event(self, name: str, payload: dict[str, Any]):
        """向上发送事件通知 (type='event')"""
        if not self._ws:
            logger.warning(f"连接未建立，事件已丢弃: {name}")
            return
        envelope = WsEnvelope(type="event", name=name, payload=payload)
        await self._ws.send(envelope.model_dump_json())

    async def _send_edge_hello(self):
        """上报设备初始状态与 ToolSpec 清单"""
        hello = EdgeHelloPayload(
            edge_version="0.2.0",
            platform="windows" if not settings.MOCK_MODE else "mock",
            dpi_scale=1.5,
            devices={
                "lamp": {"online": True, "on": False, "brightness": 80, "color_temp": 4000},
                "plug": {"online": True, "on": False, "power_w": 0.0},
                "ac": {"online": True, "on": False, "mode": "cool", "temperature": 26, "inferred": True},
                "motion": {"online": True, "illuminance": "weak"},
                "climate": {"online": True, "temperature": 26.0, "humidity": 50.0},
                "speaker": {"online": True, "voice_bridge_ok": True, "ir_supported": True}
            },
            capabilities={
                "lamp": {"color_temp_min": 2600, "color_temp_max": 5000},
                "ac": {"temp_min": 16, "temp_max": 30, "modes": ["cool", "heat", "fan", "dry"]}
            },
            tools=registry.get_all_specs()
        )
        await self.send_event("edge.hello", hello.model_dump())
        logger.info(f"已完成 edge.hello 握手，上报了 {len(hello.tools)} 个工具")

    async def _heartbeat_loop(self):
        """每 20 秒发送一次 ping 心跳"""
        while self._running:
            await asyncio.sleep(20)
            if self._ws:
                ping_env = WsEnvelope(type="ping")
                try:
                    await self._ws.send(ping_env.model_dump_json())
                except Exception as e:
                    logger.warning(f"发送心跳失败: {e}")
                    break

    async def _handle_message(self, raw_msg: str | bytes):
        """处理收到的 WebSocket 消息"""
        try:
            data = json.loads(raw_msg)
            msg = WsEnvelope.model_validate(data)
        except Exception as e:
            logger.warning(f"收到非合规信封消息，安全忽略: {raw_msg[:100]} | {e}")
            return

        # 1. 心跳响应
        if msg.type == "ping":
            pong_env = WsEnvelope(type="pong")
            if self._ws:
                await self._ws.send(pong_env.model_dump_json())
            return
        elif msg.type == "pong":
            return

        # 2. 指令处理 (type="cmd", name="tool.call")
        if msg.type == "cmd" and msg.name == "tool.call":
            tool_name = msg.payload.get("tool", "")
            args = msg.payload.get("args", {})
            call_id = msg.id

            logger.info(f"收到后端工具调用指令: {tool_name}({args}) [call_id={call_id}]")
            ok, result_data, error_code = await registry.dispatch(tool_name, args)

            # 回复结果 (type="result", name="tool.result")
            res_envelope = WsEnvelope(
                type="result",
                name="tool.result",
                payload={
                    "call_id": call_id,
                    "ok": ok,
                    "data": result_data,
                    "error": error_code
                }
            )
            if self._ws:
                await self._ws.send(res_envelope.model_dump_json())
                logger.info(f"工具调用结果已回复: call_id={call_id}, ok={ok}")
            return

        # 3. 未知消息记录 Warning 安全忽略，严禁抛错崩溃 (CONTRACTS §1)
        logger.warning(f"收到未处理的未知消息类型: {msg.type}/{msg.name}")
