"""Local single-owner web interface with isolated, serialized conversations."""
import http.server
import json
import logging
import os
import secrets
import tempfile
import threading
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, quote

from smart_agent.config import SERVER_HOST, SERVER_PORT, BASE_DIR, WORKSPACE_DIR, DATA_DIR
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient, validate_api_base
from smart_agent.agent.core import SmartAgent
from smart_agent.agent.session_manager import SessionManager
from smart_agent.tools import create_default_tools

logger = logging.getLogger("web.server")
STATIC_DIR = BASE_DIR / "web" / "static"
CONFIG_FILE = DATA_DIR / "llm_config.json"
MAX_REQUEST_BYTES = 1024 * 1024
COOKIE_NAME = "travel_access"


class SessionContext:
    def __init__(self, session):
        self.lock = threading.Lock()
        self.memory = ConversationMemory(session_id=session["session_id"])
        self.memory.load_from_turns(session.get("turns", []))
        self.agent = SmartAgent(self.memory, AgentServiceHolder.mcp_client,
                                AgentServiceHolder.snapshot_client())


class AgentServiceHolder:
    """Global tools/configuration; conversation state belongs to SessionContext."""
    @classmethod
    def initialize(cls):
        cls.mcp_server = MCPServer(name="TravelAgent-Tools")
        for tool in create_default_tools():
            cls.mcp_server.register_tool(tool)
        cls.mcp_client = MCPClient(cls.mcp_server)
        cls.llm_client = LLMClient()
        cls.config_lock = threading.RLock()
        cls.context_lock = threading.RLock()
        cls.contexts = {}
        cls.verified = False
        cls.access_token = os.environ.get("AGENT_ACCESS_TOKEN") or secrets.token_urlsafe(32)
        if len(cls.access_token) < 24:
            raise ValueError("AGENT_ACCESS_TOKEN 至少需要 24 个字符")
        if CONFIG_FILE.exists():
            try:
                cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                cls.llm_client = LLMClient(validate_api_base(cfg["api_base"]),
                    cfg.get("api_key", ""), cfg.get("model", ""))
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("本地模型配置无效，使用环境变量配置")

    @classmethod
    def snapshot_client(cls):
        with cls.config_lock:
            c = cls.llm_client
            return LLMClient(c.api_base, c.api_key, c.model)

    @classmethod
    def context(cls, session_id):
        with cls.context_lock:
            session = SessionManager.get_session(session_id)
            if session is None:
                raise LookupError("会话不存在，请新建会话")
            if session_id not in cls.contexts:
                cls.contexts[session_id] = SessionContext(session)
            return cls.contexts[session_id]


def save_config(client):
    """Write a private file atomically; it remains plaintext and is gitignored."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".llm-", dir=CONFIG_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"api_base": client.api_base, "api_key": client.api_key,
                       "model": client.model}, stream, ensure_ascii=False, indent=2)
        os.replace(temp, CONFIG_FILE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class SmartAgentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt, *args):
        # Do not log request bodies, credentials or complete query strings.
        logger.info("%s %s", self.command, urlsplit(self.path).path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
            "default-src 'self'; script-src 'self'; connect-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        super().end_headers()

    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _guard(self, authenticate=True):
        host = self.headers.get("Host", "")
        try:
            parsed = urlsplit("//" + host)
            if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.username:
                raise ValueError()
        except ValueError:
            self._send_json(403, {"error": "不允许的 Host"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + host, "https://" + host}:
            self._send_json(403, {"error": "不允许跨站请求"})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._send_json(403, {"error": "不允许跨站请求"})
            return False
        if not authenticate:
            return True
        token = ""
        try:
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            if COOKIE_NAME in cookies:
                token = cookies[COOKIE_NAME].value
        except Exception:
            pass
        bearer = self.headers.get("Authorization", "")
        if bearer.startswith("Bearer "):
            token = bearer[7:]
        if not secrets.compare_digest(token, AgentServiceHolder.access_token):
            self._send_json(401, {"error": "请先从本机打开首页，或提供访问令牌"})
            return False
        return True

    def do_OPTIONS(self):
        self._send_json(403, {"error": "仅允许同源请求"})

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if not self._guard(authenticate=path.startswith("/api/")):
            return
        query = parse_qs(parsed.query)
        try:
            if path in {"/", "/index.html"}:
                content = (STATIC_DIR / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Set-Cookie", COOKIE_NAME + "=" + AgentServiceHolder.access_token
                                 + "; HttpOnly; SameSite=Strict; Path=/")
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            elif path in {"/api/status", "/api/config"}:
                with AgentServiceHolder.config_lock:
                    client = AgentServiceHolder.llm_client
                    self._send_json(200, {
                        "status": "configured" if client.has_valid_key() else "need_api_key",
                        "has_key": client.has_valid_key(), "verified": AgentServiceHolder.verified,
                        "model": client.model, "api_base": client.api_base,
                        "masked_key": "***" if client.has_valid_key() else "",
                        "tools_count": len(AgentServiceHolder.mcp_client.get_tools()),
                        "team": [{"name": "赵海翔", "id": "3124004113"},
                                 {"name": "何卓文", "id": "3124004132"},
                                 {"name": "吴与同", "id": "3124004018"}]})
            elif path == "/api/tools":
                self._send_json(200, {"tools": [t.to_dict() for t in AgentServiceHolder.mcp_client.get_tools()]})
            elif path == "/api/sessions":
                self._send_json(200, {"sessions": SessionManager.list_sessions()})
            elif path in {"/api/session", "/api/session/download", "/api/history"}:
                sid = query.get("id", [""])[0]
                session = SessionManager.get_session(sid)
                if session is None:
                    raise LookupError("会话不存在")
                if path == "/api/session/download":
                    self._download(SessionManager.export_markdown(sid).encode("utf-8"),
                                   "chat_" + sid + ".md")
                elif path == "/api/history":
                    self._send_json(200, {"history": session.get("turns", [])})
                else:
                    # Reading another session must never alter an in-flight Agent.
                    self._send_json(200, session)
            elif path == "/api/itineraries":
                files = [p for p in WORKSPACE_DIR.iterdir()
                         if p.suffix in {".md", ".txt"} and p.is_file() and not p.is_symlink()]
                self._send_json(200, {"itineraries": [
                    {"filename": p.name, "size": "%.1f KB" % (p.stat().st_size / 1024)}
                    for p in files]})
            elif path == "/api/itinerary/download":
                name = query.get("filename", [""])[0]
                if not name or Path(name).name != name or "/" in name or "\\" in name:
                    raise ValueError("无效文件名")
                file = WORKSPACE_DIR / name
                if file.is_symlink() or file.suffix not in {".md", ".txt"} or not file.is_file():
                    raise LookupError("文档不存在")
                self._download(file.read_bytes(), name)
            elif path.startswith("/api/"):
                self._send_json(404, {"error": "接口不存在"})
            else:
                super().do_GET()
        except LookupError as exc:
            self._send_json(404, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self._send_json(400, {"error": str(exc)})
        except OSError:
            self._send_json(500, {"error": "无法读取本地文件"})

    def _download(self, body, name):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(name))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _payload(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Content-Length 无效")
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("请求体大小必须在 0 到 1 MiB 之间")
        try:
            body = self.rfile.read(length)
            payload = json.loads(body) if body else {}
        except (ValueError, UnicodeError):
            raise ValueError("请求必须是有效 UTF-8 JSON")
        if not isinstance(payload, dict):
            raise ValueError("JSON 顶层必须为对象")
        return payload

    def do_POST(self):
        if not self._guard():
            return
        path = urlsplit(self.path).path
        try:
            payload = self._payload()
            if path == "/api/config":
                self._configure(payload)
            elif path == "/api/config/test":
                with AgentServiceHolder.config_lock:
                    client = AgentServiceHolder.snapshot_client()
                    AgentServiceHolder.verified = False
                reply = client.chat_completion([{"role": "user", "content": "仅回复 OK"}])
                if not reply.get("content"):
                    raise ValueError("模型没有返回测试文本")
                with AgentServiceHolder.config_lock:
                    live = AgentServiceHolder.llm_client
                    if (client.api_base, client.api_key, client.model) != (live.api_base, live.api_key, live.model):
                        raise ValueError("测试期间配置已变更，请重新测试")
                    AgentServiceHolder.verified = True
                self._send_json(200, {"verified": True, "message": "模型连接测试成功"})
            elif path == "/api/session/new":
                title = payload.get("title", "新旅游行程规划")
                if not isinstance(title, str) or len(title) > 120:
                    raise ValueError("标题必须为不超过 120 字符的文本")
                self._send_json(200, SessionManager.create_new_session(title))
            elif path == "/api/chat":
                self._chat(payload)
            elif path in {"/api/clear", "/api/session/delete"}:
                sid = payload.get("id") or payload.get("session_id")
                context = AgentServiceHolder.context(sid)
                if not context.lock.acquire(blocking=False):
                    self._send_json(409, {"error": "会话正在执行，请完成后重试"})
                    return
                try:
                    if SessionManager.get_session(sid) is None:
                        self._send_json(404, {"error": "会话不存在"})
                        return
                    if path == "/api/clear":
                        session = SessionManager.get_session(sid)
                        session.update(turns=[], llm_messages=[])
                        SessionManager.save_session(session)
                        context.memory.clear()
                    else:
                        SessionManager.delete_session(sid)
                    self._send_json(200, {"success": True, "status": "cleared"})
                finally:
                    context.lock.release()
            elif path == "/api/mcp":
                result = AgentServiceHolder.mcp_server.handle_request(payload)
                if result is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                else:
                    self._send_json(200, result)
            else:
                self._send_json(404, {"error": "接口不存在"})
        except LookupError as exc:
            self._send_json(404, {"error": str(exc)})
        except (ValueError, TypeError, RuntimeError) as exc:
            self._send_json(400, {"error": str(exc)})
        except OSError:
            self._send_json(500, {"error": "本地存储失败"})

    def _configure(self, payload):
        for key in ("api_base", "api_key", "model"):
            if key in payload and (not isinstance(payload[key], str) or len(payload[key]) > 4096):
                raise ValueError(key + " 必须为文本且长度不超过 4096")
        with AgentServiceHolder.config_lock:
            old = AgentServiceHolder.llm_client
            base = validate_api_base(payload.get("api_base", old.api_base))
            try:
                changed = base != validate_api_base(old.api_base)
            except ValueError:
                # A bad environment value must not prevent correcting the UI config.
                changed = True
            if changed and not payload.get("api_key", "").strip():
                raise ValueError("模型地址变更时必须重新填写对应 API Key")
            client = LLMClient(base, payload.get("api_key", old.api_key),
                               payload.get("model", old.model))
            if not client.has_valid_key() or not client.model:
                raise ValueError("请填写模型名称和有效长度的 API Key")
            save_config(client)
            AgentServiceHolder.llm_client = client
            AgentServiceHolder.verified = False
        self._send_json(200, {"status": "saved", "has_key": True, "verified": False,
            "message": "配置已保存；尚未验证连接", "api_base": client.api_base, "model": client.model})

    def _chat(self, payload):
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip() or len(message) > 20000:
            raise ValueError("message 必须为 1 到 20000 字符的文本")
        stream = payload.get("stream", True)
        if not isinstance(stream, bool):
            raise ValueError("stream 必须为布尔值")
        client = AgentServiceHolder.snapshot_client()
        if not client.has_valid_key():
            raise ValueError("未配置大模型 API Key")
        sid = payload.get("session_id")
        if sid is None:
            sid = SessionManager.create_new_session()["session_id"]
        context = AgentServiceHolder.context(sid)
        if not context.lock.acquire(blocking=False):
            self._send_json(409, {"error": "会话正在执行，请勿重复发送"})
            return
        started = False
        previous_memory = None
        persisted = False
        try:
            if SessionManager.get_session(sid) is None:
                self._send_json(404, {"error": "会话不存在，请新建会话"})
                return
            previous_memory = context.memory.export_messages()
            # A request keeps one immutable provider/key configuration for its lifetime.
            context.agent.llm_client = client
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Connection", "close")
                self.end_headers()
                started = True
                self._sse({"type": "session", "session_id": sid})
            callback = (lambda step: self._sse(step.to_dict())) if stream else None
            result = context.agent.run(message.strip(), on_step=callback)
            session = SessionManager.append_turn(sid, message.strip(), result.answer,
                [step.to_dict() for step in result.traces], context.memory.export_messages())
            persisted = True
            if stream:
                self._sse({"type": "done", "session_id": sid, "title": session["title"],
                           "result": result.to_dict()})
            else:
                body = result.to_dict()
                body.update(session_id=sid, title=session["title"])
                self._send_json(200, body)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            logger.warning("会话执行失败 (%s)", type(exc).__name__)
            if started:
                self._sse({"type": "error", "session_id": sid, "error": "执行失败，请检查模型配置或稍后重试"})
            else:
                self._send_json(400, {"error": "执行失败，请检查模型配置或稍后重试"})
        finally:
            if not persisted and previous_memory is not None:
                context.memory.load_from_messages(previous_memory)
            context.lock.release()
            if stream:
                self.close_connection = True

    def _sse(self, event):
        self.wfile.write(("data: " + json.dumps(event, ensure_ascii=False) + "\n\n").encode("utf-8"))
        self.wfile.flush()


def run_server(host=SERVER_HOST, port=SERVER_PORT):
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("当前版本为本机单用户服务，仅允许 --host 127.0.0.1 或 localhost")
    AgentServiceHolder.initialize()
    server = http.server.ThreadingHTTPServer((host, port), SmartAgentHTTPRequestHandler)
    print("TravelAgent：http://%s:%s（本机单用户，首次打开首页建立访问会话）" % (host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
