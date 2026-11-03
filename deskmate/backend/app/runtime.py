"""组装用户隔离的运行环境、调度器和事件入口，不承担 C 的算法职责。"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from uuid import uuid4

import httpx
from sqlmodel import Session, delete, select

from app.agent.llm import LLMClient
from app.agent.orchestrator import Orchestrator
from app.agent.tools import ToolError, speech
from app.agent.voice_router import VoiceRouter
from app.agent.workspace_exec import WorkspaceExecutor
from app.clock import Clock, iso, parse_time
from app.config import Config
from app.db import Database, User, VoiceLog, WorkspaceProfile
from app.engine.focus import FocusEngine
from app.engine.presence import PresenceEngine
from app.engine.state_store import StateStore
from app.integrations import WellbeingEngine
from app.schemas.contracts import InputMinute
from app.sim.virtual_edge import VirtualEdge
from app.ws.edge_hub import EdgeHub
from app.ws.web_hub import WebHub

logger = logging.getLogger(__name__)
Sink = Callable[[str, dict[str, Any]], Awaitable[None]]


class Runtime:
    def __init__(
        self,
        user: User,
        db: Database,
        config: Config,
        clock: Clock,
        http: httpx.AsyncClient,
        wellbeing_factory: Callable[[int], WellbeingEngine] | None = None,
    ) -> None:
        self.user, self.db, self.config, self.clock, self.http = user, db, config, clock, http
        self.settings = db.settings(user.id)
        self.wellbeing = wellbeing_factory(user.id) if wellbeing_factory else None
        self.web = WebHub(clock, config.web_patch_interval_s)
        self.store = StateStore(clock, self.web, True)
        self.virtual = VirtualEdge(self.store, clock)
        self.edge = EdgeHub(
            self.store,
            clock,
            self.virtual,
            self.settings,
            demo_only=user.is_demo or config.demo_mode,
        )
        self.focus = FocusEngine(user.id, db, clock, self.store, config, self.wellbeing)
        self.presence = PresenceEngine(self)
        self.workspace = WorkspaceExecutor(self)
        self.llm = LLMClient(config, http)
        self.orchestrator = Orchestrator(self)
        self.voice = VoiceRouter(self)
        self.lock = asyncio.Lock()
        self.sink: Sink | None = None
        self.traces: list[dict[str, Any]] = []
        self.confirmation: dict[str, Any] | None = None
        self.default_conversation_id: str | None = None
        self.tasks: set[asyncio.Task[Any]] = set()
        self.workspace_task: asyncio.Task[Any] | None = None
        self.last_stats = clock.now()
        self.typing_rate = 100.0
        self.virtual_present = True
        self.last_cleanup = clock.now()

    def spawn(self, coroutine: Awaitable[Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(self._task_finished)
        return task

    @staticmethod
    def _task_finished(task: asyncio.Task[Any]) -> None:
        if not task.cancelled() and task.exception():
            logger.error("后台任务失败: %s", type(task.exception()).__name__)

    def workspaces(self) -> list[dict[str, Any]]:
        with Session(self.db.engine) as session:
            return [
                row.model_dump(exclude={"user_id"})
                for row in session.exec(
                    select(WorkspaceProfile)
                    .where(WorkspaceProfile.user_id == self.user.id)
                    .order_by(WorkspaceProfile.id)
                )
            ]

    def match_workspace(self, name: str) -> dict[str, Any] | None:
        profiles = self.workspaces()
        if not name:
            current_name = self.focus.state["workspace_name"]
            return next(
                (w for w in profiles if w["name"] == current_name),
                profiles[0] if profiles else None,
            )
        exact = [w for w in profiles if name in [w["name"], *w["aliases"]]]
        if exact:
            return exact[0]
        matches = [
            w
            for w in profiles
            if any(
                name in candidate or candidate in name
                for candidate in [w["name"], *w["aliases"]]
                if candidate
            )
        ]
        return matches[0] if len(matches) == 1 else None

    def expect_confirmation(self, question: str, tool: str, args: dict[str, Any]) -> None:
        self.confirmation = {
            "question": question,
            "tool": tool,
            "args": args,
            "until": self.clock.monotonic() + 30,
        }

    def background_workspace(self, workspace: dict[str, Any]) -> None:
        if self.workspace_task and not self.workspace_task.done():
            raise ToolError("BUSY", "工作台正在配置，请稍候")

        async def prepare() -> None:
            async with self.lock:
                try:
                    await self.workspace.start(workspace)
                except Exception:
                    await self.web.publish(
                        "notify",
                        {
                            "level": "warn",
                            "title": "工作台配置失败",
                            "text": "请检查设备连接后重试",
                            "action": "none",
                        },
                    )

        self.workspace_task = self.spawn(prepare())

    async def trace(self, agent: str, tool: str, args: dict[str, Any], status: str) -> None:
        # 图像与剪贴板内容不进入持久化轨迹。
        redacted = {
            k: ("[内容已省略]" if k in {"text", "content", "image_b64"} else v)
            for k, v in args.items()
        }
        trace = {"agent": agent, "tool": tool, "args": redacted, "status": status}
        self.traces.append(trace)
        if self.sink:
            await self.sink("tool", trace)

    async def delta(self, text: str) -> None:
        if self.sink:
            await self.sink("delta", {"text": text})

    async def speak(self, text: str) -> None:
        try:
            await self.edge.call("speaker_tts", {"text": speech(text)})
        except ToolError:
            await self.web.publish(
                "notify",
                {
                    "level": "warn",
                    "title": "语音输出不可用",
                    "text": speech(text),
                    "action": "none",
                },
            )

    async def handle(
        self, text: str, conversation_id: str | None = None, sink: Sink | None = None
    ) -> dict[str, Any]:
        if self.lock.locked():
            reply = "正在处理上一条任务，请稍候再试"
            if sink:
                await sink("error", {"message": reply})
            with Session(self.db.engine) as session:
                row = VoiceLog(
                    user_id=self.user.id,
                    at=iso(self.clock),
                    text=text,
                    route="busy",
                    trace=[],
                    reply=reply,
                    ok=False,
                    latency_ms=0,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                await self.web.publish("voice.log", row.model_dump(exclude={"user_id"}))
            return {"reply": reply, "conversation_id": conversation_id, "ok": False}
        async with self.lock:
            self.traces, self.sink = [], sink
            conversation_id = conversation_id or self.default_conversation_id
            started = self.clock.monotonic()
            route, ok = "orchestrator", True

            async def acknowledge() -> None:
                await self.clock.sleep(self.config.acknowledgement_s)
                await self.speak("好的，正在为你处理，稍等片刻")

            ack = asyncio.create_task(acknowledge())
            try:
                async with asyncio.timeout(self.config.agent_timeout_s):
                    reply, route, conversation_id = await self.voice.route(text, conversation_id)
                if conversation_id is None:
                    conversation_id = str(uuid4())
                    self.orchestrator.histories[conversation_id] = [
                        {"role": "user", "content": text},
                        {"role": "assistant", "content": reply},
                    ]
                self.default_conversation_id = conversation_id
                if route == "fast":
                    self.spawn(self.speak(reply))
                else:
                    await self.speak(reply)
            except ToolError as exc:
                ok, reply = False, exc.message
                if sink:
                    await sink("error", {"message": reply})
            except Exception as exc:
                ok = False
                reply = "模型或工具暂时不可用，请稍后重试"
                logger.warning("智能体调用失败: %s", type(exc).__name__)
                if sink:
                    await sink("error", {"message": reply})
            finally:
                ack.cancel()
                await asyncio.gather(ack, return_exceptions=True)
                self.sink = None
            with Session(self.db.engine) as session:
                row = VoiceLog(
                    user_id=self.user.id,
                    at=iso(self.clock),
                    text=text,
                    route=route,
                    trace=list(self.traces),
                    reply=reply,
                    ok=ok,
                    latency_ms=int((self.clock.monotonic() - started) * 1000),
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                await self.web.publish("voice.log", row.model_dump(exclude={"user_id"}))
            return {"reply": reply, "conversation_id": conversation_id, "ok": ok}

    async def event(self, name: str, payload: dict[str, Any]) -> None:
        if name == "device.state":
            device, state = payload.get("device"), payload.get("state")
            if device not in self.store.data["devices"] or not isinstance(state, dict):
                raise ValueError("无效设备状态")
            self.store.device(device, state)
            if device == "motion" and state.get("last_motion_at"):
                at = parse_time(state["last_motion_at"])
                self.presence.last_motion = min(at, self.clock.now())
        elif name == "pc.session":
            self.presence.pc_session(payload)
            await self.presence.tick()
        elif name == "pc.input_stats":
            stat = InputMinute.model_validate(payload).model_dump()
            self.store.update(current_input_stats=stat)
            if stat["active_seconds"]:
                self.presence.last_input = self.clock.now()
            if self.wellbeing:
                action = self.wellbeing.on_minute_stats(
                    stat, self.focus.state, self.store.data["devices"]["climate"]["temperature"]
                )
                if action:
                    await self.apply_wellbeing_action(action)
        elif name == "voice.heard":
            text = payload.get("text")
            if not isinstance(text, str) or not 0 < len(text) <= 4000:
                raise ValueError("无效语音文本")
            self.spawn(self.handle(text))
        elif name == "edge.log":
            logger.warning("Edge 上报异常（详细日志请查看现场端）")
        else:
            logger.warning("忽略未知 Edge 事件: %s", name)

    async def apply_wellbeing_action(self, action: Any) -> None:
        data = action.model_dump() if hasattr(action, "model_dump") else action
        kind = data.get("action_type")
        if kind == "lamp_breathe":
            await self.edge.call("lamp_effect", {"effect": "breathe", "duration_s": 10})
        elif kind == "voice_care":
            await self.speak(data.get("speech_text") or "专注很久了，要起来走走吗")
        elif kind == "force_break":
            self.focus.force_break()
            await self.edge.call("lamp_set", {"on": True, **self.settings["relax_lamp"]})
            await self.web.publish(
                "notify",
                {
                    "level": "alert",
                    "title": "建议休息",
                    "text": data.get("speech_text") or "起来活动一下吧",
                    "action": "rest_overlay",
                },
            )
        elif kind == "flow_extended":
            await self.edge.call("lamp_effect", {"effect": "breathe", "duration_s": 10})
        # 疲劳分由 C 发布，B 不自行实现评分。

    async def inject(self, kind: str, value: Any) -> dict[str, Any]:
        if not self.user.is_demo:
            raise ToolError("NOT_ALLOWED", "只有演示账号可以注入")
        if kind == "voice":
            if not isinstance(value, str) or not 0 < len(value) <= 4000:
                raise ToolError("BAD_ARGS")
            return await self.handle(value)
        if kind == "temperature":
            if type(value) not in {float, int} or not -20 <= value <= 60:
                raise ToolError("BAD_ARGS")
            climate = {
                **self.store.data["devices"]["climate"],
                "temperature": float(value),
                "updated_at": iso(self.clock),
            }
            self.store.device("climate", climate)
        elif kind == "typing_rate":
            if type(value) not in {float, int} or not 0 <= value <= 1000:
                raise ToolError("BAD_ARGS")
            self.typing_rate = float(value)
        elif kind == "lock":
            if type(value) is not bool:
                raise ToolError("BAD_ARGS")
            self.presence.locked = value
            if not value:
                self.virtual_present = True
                self.presence.last_input = self.clock.now()
        elif kind == "leave":
            self.virtual_present = False
            threshold = max(self.settings["absent_confirm_min"], self.settings["motion_window_min"])
            before = self.clock.now() - timedelta(minutes=threshold)
            self.presence.last_input = self.presence.last_motion = before
        elif kind == "motion":
            self.virtual_present = True
            self.presence.last_motion = self.clock.now()
            self.store.device(
                "motion",
                {**self.store.data["devices"]["motion"], "last_motion_at": iso(self.clock)},
            )
        else:
            raise ToolError("BAD_ARGS", "未知注入类型")
        await self.tick()
        return {"ok": True}

    async def tick(self) -> None:
        if self.store.data["demo_mode"] and self.virtual_present and not self.presence.locked:
            self.presence.last_motion = self.clock.now()
            if self.typing_rate > 0:
                self.presence.last_input = self.clock.now()
        if (self.clock.now() - self.last_stats).total_seconds() >= 60 and self.store.data[
            "demo_mode"
        ]:
            self.last_stats = self.clock.now()
            await self.event(
                "pc.input_stats",
                {
                    "minute": iso(self.clock),
                    "keys": int(self.typing_rate) if self.virtual_present else 0,
                    "clicks": 0,
                    "scrolls": 0,
                    "active_seconds": 45 if self.virtual_present and self.typing_rate else 0,
                    "app_switches": 0,
                    "front_process": "Code.exe",
                    "front_title_category": "study",
                    "activity_rate": self.typing_rate if self.virtual_present else 0.0,
                },
            )
        await self.presence.tick()
        action = self.focus.tick(self.settings)
        if action == "break":
            await self.edge.call("lamp_set", {"on": True, **self.settings["relax_lamp"]})
            await self.speak("专注阶段结束，休息一下吧")
        elif action == "focus":
            await self.edge.call("lamp_set", {"on": True, **self.settings["focus_lamp"]})
            await self.speak("休息结束，继续加油")
        elif action == "flow_extended":
            await self.edge.call("lamp_effect", {"effect": "breathe", "duration_s": 10})
        if (self.clock.now() - self.last_cleanup).total_seconds() >= 3600:
            self.last_cleanup = self.clock.now()
            cutoff = (
                self.clock.now() - timedelta(days=self.config.session_retention_days)
            ).isoformat()
            with Session(self.db.engine) as session:
                session.exec(
                    delete(VoiceLog).where(VoiceLog.user_id == self.user.id, VoiceLog.at < cutoff)
                )
                session.commit()

    async def schedule(self) -> None:
        while True:
            await self.clock.sleep(self.config.scheduler_interval_s)
            try:
                # 智能体等待网络期间仍可及时处理锁屏和倒计时。
                await self.tick()
            except Exception:
                logger.exception("调度循环异常，本轮跳过")

    async def close(self) -> None:
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.focus.pause()
        await self.web.close()
