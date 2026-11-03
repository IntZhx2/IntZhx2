"""FastAPI 生命周期、契约 REST 路由、鉴权及双向 WebSocket 入口。"""

import asyncio
import hmac
import json
import logging
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any
from zoneinfo import ZoneInfo

import anyio
import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field, ValidationError
from sqlmodel import Session, select

from app.agent.tools import ToolError
from app.auth import Auth
from app.clock import Clock, SystemClock, parse_time
from app.config import Config
from app.db import (
    Database,
    User,
    UserSettings,
    VoiceLog,
    WorkspaceProfile,
    hash_password,
    verify_password,
)
from app.integrations import WellbeingEngine
from app.runtime import Runtime
from app.schemas.contracts import Settings, StrictModel, WorkspaceIn, merge_dict
from app.ws.envelope import Envelope, envelope

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


class LoginIn(StrictModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class FocusIn(StrictModel):
    workspace_id: int | None = None
    goal: str = Field(default="", max_length=500)
    minutes: int | None = Field(default=None, ge=1, le=240)


class ChatIn(StrictModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=100)


class InjectIn(StrictModel):
    kind: str
    value: Any = None


def create_app(
    config: Config | None = None,
    clock: Clock | None = None,
    wellbeing_factory: Callable[[int], WellbeingEngine] | None = None,
    wellbeing_router: Any = None,
    run_scheduler: bool = True,
) -> FastAPI:
    clock = clock or SystemClock()
    runtimes: dict[int, Runtime] = {}
    login_attempts: OrderedDict[str, tuple[float, int]] = OrderedDict()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        cfg = config or Config()
        db = Database(cfg.database_url)
        db.migrate_and_seed(cfg)
        application.state.config, application.state.db = cfg, db
        application.state.clock = clock
        application.state.auth = Auth(cfg, db, clock)
        application.state.http = httpx.AsyncClient()
        application.state.dummy_password = hash_password("unused-constant-time-check")
        application.state.runtimes = runtimes
        try:
            yield
        finally:
            for runtime in runtimes.values():
                await runtime.close()
            await application.state.http.aclose()
            db.engine.dispose()

    application = FastAPI(title="DeskMate 后端 API", version="0.1.0", lifespan=lifespan)

    @application.middleware("http")
    async def limit_body(request: Request, call_next: Any) -> Any:
        # 所有 JSON 入口大小受限，既检查 Content-Length 也检查实际请求体。
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 65536:
            return JSONResponse({"detail": "请求体过大"}, status_code=413)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                return JSONResponse({"detail": "请求体过大"}, status_code=413)
        request._body = bytes(body)
        return await call_next(request)

    @application.exception_handler(ToolError)
    async def tool_error_handler(request: Request, exc: ToolError) -> JSONResponse:
        code = 403 if exc.code == "NOT_ALLOWED" else 422 if exc.code == "BAD_ARGS" else 503
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=code)

    @application.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse({"detail": "字段类型或取值无效"}, status_code=422)

    def current_user(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> User:
        if credentials is None:
            raise HTTPException(401, "请先登录")
        return request.app.state.auth.resolve(credentials.credentials)

    UserDep = Annotated[User, Depends(current_user)]

    def runtime_for(user: User) -> Runtime:
        if user.id not in runtimes:
            runtime = Runtime(
                user,
                application.state.db,
                application.state.config,
                clock,
                application.state.http,
                wellbeing_factory,
            )
            runtimes[user.id] = runtime
            if run_scheduler:
                runtime.spawn(runtime.schedule())
        return runtimes[user.id]

    application.state.runtime_for = runtime_for

    @application.get("/api/health")
    async def health() -> dict[str, Any]:
        cfg = application.state.config
        live = next((rt for rt in runtimes.values() if not rt.user.is_demo), None)
        return {
            "ok": True,
            "edge_online": bool(live and live.edge.ws),
            "demo_mode": cfg.demo_mode or not (live and live.edge.ws),
        }

    @application.post("/api/auth/login")
    async def login(body: LoginIn, request: Request) -> dict[str, Any]:
        key = (request.client.host if request.client else "unknown") + ":" + body.username
        since, attempts = login_attempts.get(key, (clock.monotonic(), 0))
        if clock.monotonic() - since >= 60:
            since, attempts = clock.monotonic(), 0
        login_attempts[key] = (since, attempts + 1)
        login_attempts.move_to_end(key)
        while len(login_attempts) > 1024:
            login_attempts.popitem(last=False)
        if attempts >= 10:
            raise HTTPException(429, "登录请求过多，请一分钟后重试")
        with Session(application.state.db.engine) as session:
            user = session.exec(select(User).where(User.username == body.username)).first()
        valid = await asyncio.to_thread(
            verify_password,
            body.password,
            user.password_hash if user else application.state.dummy_password,
        )
        if not valid or user is None:
            raise HTTPException(401, "账号或密码错误")
        return {
            "token": application.state.auth.issue(user),
            "user": user.model_dump(include={"id", "username", "is_demo"}),
        }

    @application.get("/api/state")
    async def state(user: UserDep) -> dict[str, Any]:
        return runtime_for(user).store.snapshot()

    @application.post("/api/devices/{device}/command")
    async def device_command(device: str, body: dict[str, Any], user: UserDep) -> dict[str, Any]:
        if device not in {"lamp", "plug", "ac"}:
            raise HTTPException(404, "设备不存在或只读")
        rt = runtime_for(user)
        async with rt.lock:
            result = await rt.edge.call(device + "_set", body)
        return {"ok": True, "state": result}

    @application.get("/api/workspaces")
    async def workspaces(user: UserDep) -> list[dict[str, Any]]:
        return runtime_for(user).workspaces()

    @application.post("/api/workspaces", status_code=201)
    async def create_workspace(body: WorkspaceIn, user: UserDep) -> dict[str, Any]:
        with Session(application.state.db.engine) as session:
            row = WorkspaceProfile(user_id=user.id, **body.model_dump(exclude_none=True))
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.model_dump(exclude={"user_id"})

    def owned_workspace(session: Session, item_id: int, user: User) -> WorkspaceProfile:
        row = session.get(WorkspaceProfile, item_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(404, "工作台不存在")
        return row

    @application.put("/api/workspaces/{item_id}")
    async def update_workspace(item_id: int, body: WorkspaceIn, user: UserDep) -> dict[str, Any]:
        with Session(application.state.db.engine) as session:
            row = owned_workspace(session, item_id, user)
            for key, value in body.model_dump().items():
                setattr(row, key, value)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.model_dump(exclude={"user_id"})

    @application.delete("/api/workspaces/{item_id}")
    async def delete_workspace(item_id: int, user: UserDep) -> dict[str, bool]:
        with Session(application.state.db.engine) as session:
            row = owned_workspace(session, item_id, user)
            session.delete(row)
            session.commit()
        return {"ok": True}

    @application.post("/api/focus/start")
    async def focus_start(body: FocusIn, user: UserDep) -> dict[str, Any]:
        rt = runtime_for(user)
        workspace = (
            next((w for w in rt.workspaces() if w["id"] == body.workspace_id), None)
            if (body.workspace_id is not None)
            else rt.match_workspace("")
        )
        if workspace is None:
            raise HTTPException(404, "工作台不存在")
        async with rt.lock:
            return (await rt.workspace.start(workspace, body.goal, body.minutes))["focus"]

    @application.post("/api/focus/stop")
    async def focus_stop(user: UserDep) -> dict[str, Any]:
        rt = runtime_for(user)
        async with rt.lock:
            return {"session": rt.focus.stop()}

    @application.get("/api/focus/sessions")
    async def sessions(
        user: UserDep,
        from_day: Annotated[date | None, Query(alias="from")] = None,
        to: date | None = None,
    ) -> list[dict[str, Any]]:
        if from_day and to and from_day > to:
            raise HTTPException(422, "日期范围无效")
        zone = ZoneInfo(application.state.config.tz)
        result = []
        for row in runtime_for(user).focus.sessions():
            local_day = parse_time(row.started_at).astimezone(zone).date()
            if (from_day is None or local_day >= from_day) and (to is None or local_day <= to):
                result.append(row.model_dump(exclude={"user_id"}))
        return result

    @application.get("/api/logs/voice")
    async def logs(
        user: UserDep, limit: int = Query(default=50, ge=1, le=200)
    ) -> list[dict[str, Any]]:
        with Session(application.state.db.engine) as session:
            return [
                row.model_dump(exclude={"user_id"})
                for row in session.exec(
                    select(VoiceLog)
                    .where(VoiceLog.user_id == user.id)
                    .order_by(VoiceLog.id.desc())
                    .limit(limit)
                )
            ]

    @application.get("/api/settings")
    async def get_settings(user: UserDep) -> dict[str, Any]:
        return runtime_for(user).settings

    @application.put("/api/settings")
    async def put_settings(body: dict[str, Any], user: UserDep) -> dict[str, Any]:
        rt = runtime_for(user)
        async with rt.lock:
            values = Settings.model_validate(merge_dict(rt.settings, body)).model_dump()
            with Session(application.state.db.engine) as session:
                row = session.get(UserSettings, user.id)
                row.values = values
                session.add(row)
                session.commit()
            rt.settings = rt.edge.settings = values
            try:
                await rt.edge.call(
                    "edge_config_update",
                    {
                        "app_whitelist": values["app_whitelist"],
                        "study_apps": values["study_categories"],
                        "entertainment_apps": values["entertainment_categories"],
                        "voice_takeover_prefixes": values["voice_takeover_prefixes"],
                    },
                )
            except ToolError:
                await rt.web.publish(
                    "notify",
                    {
                        "level": "warn",
                        "title": "配置待同步",
                        "text": "设置已保存，现场端重连后重新同步",
                        "action": "none",
                    },
                )
            await rt.presence.tick()
            return values

    @application.post("/api/demo/inject")
    async def inject(body: InjectIn, user: UserDep) -> dict[str, Any]:
        return await runtime_for(user).inject(body.kind, body.value)

    @application.post("/api/chat")
    async def chat(body: ChatIn, user: UserDep, request: Request) -> StreamingResponse:
        rt = runtime_for(user)

        async def stream() -> AsyncIterator[str]:
            queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue(maxsize=128)

            async def sink(kind: str, data: dict[str, Any]) -> None:
                await queue.put((kind, data))

            async def work() -> None:
                try:
                    result = await rt.handle(body.message, body.conversation_id, sink)
                    await sink("done", {k: result[k] for k in ("reply", "conversation_id")})
                finally:
                    await queue.put(None)

            task = asyncio.create_task(work())
            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if item is None:
                        break
                    kind, data = item
                    yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.websocket("/ws/web")
    async def web_socket(ws: WebSocket, token: str = "") -> None:
        try:
            user = application.state.auth.resolve(token)
        except HTTPException:
            await ws.close(code=4401)
            return
        rt = runtime_for(user)
        await ws.accept()
        rt.web.attach(ws, rt.store.snapshot())
        sender = asyncio.create_task(rt.web.sender(ws))

        async def heartbeat() -> None:
            while True:
                await clock.sleep(application.state.config.heartbeat_s)
                try:
                    application.state.auth.resolve(token)
                except HTTPException:
                    await ws.close(code=4401)
                    return
                queue = rt.web.clients.get(ws)
                if queue:
                    await queue.put(envelope(clock, "", {}, "ping"))

        heart = asyncio.create_task(heartbeat())
        try:
            while True:
                raw = await asyncio.wait_for(
                    ws.receive_text(), application.state.config.edge_stale_s
                )
                if len(raw) > 65536:
                    await ws.close(code=1009)
                    break
                try:
                    message = Envelope.model_validate_json(raw)
                    if message.type == "ping":
                        queue = rt.web.clients.get(ws)
                        if queue:
                            await queue.put(envelope(clock, "", {}, "pong"))
                    elif message.type == "event" and message.name == "rest.skip":
                        if rt.focus.state["state"] == "short_break":
                            state = rt.focus.state
                            state["phase_ends_at"] = clock.now().isoformat()
                            rt.store.update(focus=state)
                            await rt.tick()
                    elif message.type != "pong":
                        logger.warning("忽略未知 Web 事件: %s", message.name)
                except ValidationError:
                    logger.warning("忽略无效 Web 消息")
        except (WebSocketDisconnect, TimeoutError, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            with anyio.CancelScope(shield=True):
                rt.web.detach(ws)
                for task in (sender, heart):
                    task.cancel()
                await asyncio.gather(sender, heart, return_exceptions=True)

    @application.websocket("/ws/edge")
    async def edge_socket(ws: WebSocket, token: str = "") -> None:
        cfg = application.state.config
        if not hmac.compare_digest(token, cfg.edge_token.get_secret_value()) or cfg.demo_mode:
            await ws.close(code=4401)
            return
        with Session(application.state.db.engine) as session:
            admin = session.exec(select(User).where(User.username == "admin")).one()
        rt = runtime_for(admin)
        await ws.accept()
        registered = False

        async def heartbeat() -> None:
            while True:
                await clock.sleep(cfg.heartbeat_s)
                if clock.monotonic() - rt.edge.last_seen >= cfg.edge_stale_s:
                    await ws.close(code=1001)
                    return
                if registered:
                    await rt.edge.send(envelope(clock, "", {}, "ping"))

        heart = asyncio.create_task(heartbeat())
        try:
            while True:
                raw = await asyncio.wait_for(ws.receive_text(), cfg.edge_stale_s)
                if len(raw) > 12_000_000:
                    await ws.close(code=1009)
                    break
                try:
                    message = Envelope.model_validate_json(raw)
                    rt.edge.last_seen = clock.monotonic()
                    if not registered:
                        if message.type != "event" or message.name != "edge.hello":
                            raise ToolError("BAD_ARGS")
                        await rt.edge.register(ws, message.payload)
                        registered = True
                        rt.spawn(
                            rt.edge.call(
                                "edge_config_update",
                                {
                                    "app_whitelist": rt.settings["app_whitelist"],
                                    "study_apps": rt.settings["study_categories"],
                                    "entertainment_apps": rt.settings["entertainment_categories"],
                                    "voice_takeover_prefixes": rt.settings[
                                        "voice_takeover_prefixes"
                                    ],
                                },
                            )
                        )
                    elif message.type == "result" and message.name == "tool.result":
                        rt.edge.resolve(message.payload)
                    elif message.type == "ping":
                        await rt.edge.send(envelope(clock, "", {}, "pong"))
                    elif message.type == "event":
                        # 事件可能触发反向 RPC，接收循环必须继续读取 tool.result。
                        rt.spawn(rt.event(message.name, message.payload))
                except (ValidationError, ValueError):
                    logger.warning("忽略无效 Edge 消息")
                except ToolError:
                    if not registered:
                        await ws.close(code=4403)
                        break
                    logger.warning("Edge 事件处理失败")
        except (WebSocketDisconnect, TimeoutError, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            with anyio.CancelScope(shield=True):
                heart.cancel()
                await asyncio.gather(heart, return_exceptions=True)
                rt.edge.disconnect(ws)

    if wellbeing_router is not None:
        application.include_router(wellbeing_router)
    else:

        @application.get("/api/reports/daily")
        @application.get("/api/reports/weekly")
        @application.post("/api/reports/daily/generate")
        @application.get("/api/timeline")
        async def unavailable_c_module(user: UserDep) -> None:
            raise HTTPException(503, "成员 C 的健康报告模块尚未接入")

    return application


app = create_app()
