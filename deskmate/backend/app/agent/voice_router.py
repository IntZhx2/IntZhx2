"""严格按 CONTRACTS §7 顺序匹配快速路径，确认窗口先于模型处理。"""

import asyncio
import re
from typing import TYPE_CHECKING

from app.agent.tools import ToolError

if TYPE_CHECKING:
    from app.runtime import Runtime


FAST_PATH = [
    (r"^(我要开始(学习|专注|工作|写作业)|开始学习)", "start"),
    (r"^(结束(学习|专注|工作)|退出专注)", "stop"),
    (r"^(开灯|把灯打开)", "lamp_on"),
    (r"^(关灯|把灯关了)", "lamp_off"),
    (r"^(调亮|亮一点)", "brighter"),
    (r"^(调暗|暗一点)", "dimmer"),
    (r"^(开空调|把空调打开)", "ac_on"),
    (r"^(关空调|把空调关了)", "ac_off"),
    (r"^(空调.*(?P<temp>\d{2})度)", "ac_temp"),
    (r"^(现在多少度|室内温湿度)", "climate"),
    (r"^(还剩多久|学了多久)", "remaining"),
]


class VoiceRouter:
    def __init__(self, runtime: "Runtime") -> None:
        self.rt = runtime

    async def route(
        self, text: str, conversation_id: str | None = None
    ) -> tuple[str, str, str | None]:
        rt = self.rt
        pending = rt.confirmation
        if pending and rt.clock.monotonic() <= pending["until"]:
            if text.strip() in {"好", "好的", "是", "确认", "打开", "可以"}:
                rt.confirmation = None
                await rt.edge.call(pending["tool"], pending["args"])
                return "已按你的确认执行", "confirmation", conversation_id
            if text.strip() in {"不", "不要", "取消", "否"}:
                rt.confirmation = None
                return "已取消", "confirmation", conversation_id
        elif pending:
            rt.confirmation = None
        for pattern, action in FAST_PATH:
            match = re.match(pattern, text)
            if not match:
                continue
            async with asyncio.timeout(rt.config.fast_path_timeout_s):
                return await self.execute_fast(action, match, conversation_id)
        if conversation_id and conversation_id not in rt.orchestrator.histories:
            raise ToolError("NOT_ALLOWED", "会话不属于当前用户")
        reply, key = await rt.orchestrator.run(text, conversation_id)
        return reply, "orchestrator", key

    async def execute_fast(
        self, action: str, match: re.Match[str], conversation_id: str | None
    ) -> tuple[str, str, str | None]:
        rt = self.rt
        reply = "已完成"
        lamp = rt.store.data["devices"]["lamp"]
        if action == "start":
            # 快速路径只派发灯光与后台工作台任务，避免等待窗口/TTS阻塞 3 秒指标。
            workspace = rt.match_workspace("")
            if workspace is None:
                raise ToolError("BAD_ARGS", "请先创建工作台")
            await rt.edge.call("lamp_set", {"on": True, **workspace["lamp"]})
            rt.background_workspace(workspace)
            reply = "台灯已进入专注模式，正在准备工作台"
        elif action == "stop":
            result = rt.focus.stop()
            reply = (
                f"本次专注{result['focus_seconds'] // 60}分钟，辛苦了"
                if result
                else "当前没有专注会话"
            )
        elif action in {"lamp_on", "lamp_off"}:
            await rt.edge.call("lamp_set", {"on": action == "lamp_on"})
        elif action in {"brighter", "dimmer"}:
            brightness = min(
                100, max(1, lamp["brightness"] + (20 if action == "brighter" else -20))
            )
            await rt.edge.call("lamp_set", {"brightness": brightness})
            reply = f"亮度已调到百分之{brightness}"
        elif action in {"ac_on", "ac_off", "ac_temp"}:
            args = (
                {"on": action == "ac_on"}
                if action != "ac_temp"
                else {"temperature": int(match.group("temp"))}
            )
            if action == "ac_on":
                args["temperature"] = rt.settings["ac"]["summer_temp"]
            await rt.edge.call("ac_set", args)
        elif action == "climate":
            climate = rt.store.data["devices"]["climate"]
            reply = f"室温{climate['temperature']}度，湿度百分之{climate['humidity']}"
        elif action == "remaining":
            rt.focus.tick(rt.settings)
            reply = f"当前还剩{(rt.focus.state['remaining_seconds'] + 59) // 60}分钟"
        return reply, "fast", conversation_id
