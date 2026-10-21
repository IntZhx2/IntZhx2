"""
智能旅游规划 Agent Web 服务端 (Web HTTP & REST Server)
原生 Python 标准库实现，提供旅游定制交互 API、MCP 规范分发及历史攻略归档托管。
"""

import http.server
import json
import logging
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional
from smart_agent.config import SERVER_HOST, SERVER_PORT, BASE_DIR, WORKSPACE_DIR, DATA_DIR
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.agent.core import SmartAgent, AgentStepTrace
from smart_agent.agent.session_manager import SessionManager
from smart_agent.tools import create_default_tools

logger = logging.getLogger("web.server")
STATIC_DIR = BASE_DIR / "web" / "static"


CONFIG_FILE = DATA_DIR / "llm_config.json"


class AgentServiceHolder:
    """智能体与 MCP 服务单例持有者"""
    mcp_server: MCPServer
    mcp_client: MCPClient
    llm_client: LLMClient
    agent: SmartAgent
    memory: ConversationMemory
    current_session_id: Optional[str] = None

    @classmethod
    def initialize(cls):
        cls.mcp_server = MCPServer(name="SmartAgent-Travel-Server")
        for tool in create_default_tools():
            cls.mcp_server.register_tool(tool)

        cls.mcp_client = MCPClient(cls.mcp_server)
        cls.llm_client = LLMClient()

        # 加载持久化的 API 配置
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("api_base"):
                    cls.llm_client.api_base = cfg["api_base"].strip()
                if cfg.get("api_key"):
                    cls.llm_client.api_key = cfg["api_key"].strip()
                if cfg.get("model"):
                    cls.llm_client.model = cfg["model"].strip()
            except Exception as e:
                logger.warning(f"读取配置失败: {e}")

        cls.memory = ConversationMemory(session_id="travel_web_session")
        cls.current_session_id = None
        cls.agent = SmartAgent(
            memory=cls.memory,
            mcp_client=cls.mcp_client,
            llm_client=cls.llm_client,
        )


class SmartAgentHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """自定义 HTTP 请求分发处理器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {self.command} {self.path} - {format % args}", flush=True)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, status_code: int, data: Any):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            index_path = STATIC_DIR / "index.html"
            if index_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                with open(index_path, "rb") as f:
                    content = f.read()
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        elif path == "/api/status":
            tools = AgentServiceHolder.mcp_client.get_tools()
            has_key = AgentServiceHolder.llm_client.has_valid_key()
            self._send_json(200, {
                "status": "ready" if has_key else "need_api_key",
                "has_key": has_key,
                "model": AgentServiceHolder.llm_client.model,
                "tools_count": len(tools),
                "team": [
                    {"name": "赵海翔", "id": "3124004113", "role": "架构设计与智能体内核"},
                    {"name": "何卓文", "id": "3124004132", "role": "MCP 服务端与旅游工具生态"},
                    {"name": "吴与同", "id": "3124004018", "role": "莫兰迪响应式 UI 与语音交互"},
                ]
            })
            return

        elif path == "/api/config":
            client = AgentServiceHolder.llm_client
            has_key = client.has_valid_key()
            masked = ""
            if has_key:
                k = client.api_key.strip()
                masked = k[:3] + "..." + k[-4:] if len(k) > 7 else "***"
            self._send_json(200, {
                "api_base": client.api_base,
                "model": client.model,
                "has_key": has_key,
                "masked_key": masked,
            })
            return

        elif path == "/api/tools":
            tools = [t.to_dict() for t in AgentServiceHolder.mcp_client.get_tools()]
            self._send_json(200, {"tools": tools})
            return

        elif path == "/api/sessions":
            sessions = SessionManager.list_sessions()
            self._send_json(200, {
                "sessions": sessions,
                "active_session_id": AgentServiceHolder.current_session_id
            })
            return

        elif path == "/api/session":
            query = urllib.parse.parse_qs(parsed.query)
            sess_id = query.get("id", [""])[0]
            if not sess_id:
                self._send_json(400, {"error": "缺少 session id 参数"})
                return
            session_data = SessionManager.get_session(sess_id)
            if not session_data:
                self._send_json(404, {"error": f"未找到会话 {sess_id}"})
                return
            # 激活该会话并将其完整消息注入内存上下文（实现无缝接续对话）
            AgentServiceHolder.current_session_id = sess_id
            AgentServiceHolder.memory.load_from_messages(session_data.get("llm_messages", []))
            self._send_json(200, session_data)
            return

        elif path == "/api/session/download":
            query = urllib.parse.parse_qs(parsed.query)
            sess_id = query.get("id", [""])[0]
            if not sess_id:
                self._send_json(400, {"error": "缺少 session id 参数"})
                return
            md_content = SessionManager.export_markdown(sess_id)
            md_bytes = md_content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="chat_{sess_id}.md"')
            self.send_header("Content-Length", str(len(md_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(md_bytes)
            return

        elif path == "/api/itineraries":
            try:
                files = list(WORKSPACE_DIR.glob("*.md")) + list(WORKSPACE_DIR.glob("*.txt"))
                result = []
                import time
                for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
                    mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
                    size_kb = round(f.stat().st_size / 1024, 1)
                    result.append({"filename": f.name, "size": f"{size_kb} KB", "updated_at": mtime})
                self._send_json(200, {"itineraries": result})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        elif path == "/api/history":
            history = AgentServiceHolder.memory.get_history_summary()
            self._send_json(200, {"history": history})
            return

        # 默认回退到静态资源托管
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                pass

        if path == "/api/chat":
            message = payload.get("message", "").strip()
            if not message:
                self._send_json(400, {"error": "出行需求描述 message 不能为空"})
                return

            if not AgentServiceHolder.llm_client.has_valid_key():
                self._send_json(400, {
                    "error": "【未配置大模型 API Key】当前系统已关闭伪离线模式，必须接入真实大模型 API！请在【⚙️ API 设置】中配置。"
                })
                return

            # 会话 ID 绑定与恢复 (支持多轮接续对话)
            session_id = payload.get("session_id")
            if not session_id:
                # 用户开启全新对话：初始化新会话，重置上下文记忆
                new_sess = SessionManager.create_new_session()
                session_id = new_sess["session_id"]
                AgentServiceHolder.current_session_id = session_id
                AgentServiceHolder.memory.clear()
            else:
                # 恢复指定历史会话上下文
                exist_sess = SessionManager.get_session(session_id)
                if exist_sess and AgentServiceHolder.current_session_id != session_id:
                    AgentServiceHolder.current_session_id = session_id
                    AgentServiceHolder.memory.load_from_messages(exist_sess.get("llm_messages", []))

            is_stream = payload.get("stream", True)
            if not is_stream:
                try:
                    res = AgentServiceHolder.agent.run(message)
                    saved_sess = SessionManager.append_turn(
                        session_id=session_id,
                        user_prompt=message,
                        assistant_response=res.answer,
                        step_traces=[s.to_dict() for s in res.traces],
                        llm_messages=AgentServiceHolder.memory.export_messages(),
                    )
                    res_dict = res.to_dict()
                    res_dict["session_id"] = session_id
                    res_dict["title"] = saved_sess.get("title", "")
                    self._send_json(200, res_dict)
                except Exception as e:
                    self._send_json(400, {"error": str(e)})
                return

            # SSE 流式实时推送 (调用什么就即时展示什么，拒绝盲等一次性输出)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                def send_sse(data_dict: dict):
                    msg = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
                    self.wfile.write(msg)
                    self.wfile.flush()

                collected_traces = []

                def on_step(trace: AgentStepTrace):
                    collected_traces.append(trace.to_dict())
                    send_sse(trace.to_dict())

                result = AgentServiceHolder.agent.run(message, on_step=on_step)

                # 自动持久化保存本轮多轮会话
                saved_sess = SessionManager.append_turn(
                    session_id=session_id,
                    user_prompt=message,
                    assistant_response=result.answer,
                    step_traces=collected_traces,
                    llm_messages=AgentServiceHolder.memory.export_messages(),
                )

                send_sse({
                    "type": "done",
                    "session_id": session_id,
                    "title": saved_sess.get("title", ""),
                    "result": result.to_dict(),
                })

            except Exception as e:
                logger.error(f"流式执行异常: {e}")
                err_dict = {"type": "error", "error": str(e)}
                try:
                    self.wfile.write(f"data: {json.dumps(err_dict, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except Exception:
                    pass
            return

        elif path == "/api/session/new":
            title = payload.get("title", "新旅游行程规划")
            new_sess = SessionManager.create_new_session(title)
            AgentServiceHolder.current_session_id = new_sess["session_id"]
            AgentServiceHolder.memory.clear()
            self._send_json(200, new_sess)
            return

        elif path == "/api/session/delete":
            sess_id = payload.get("id") or payload.get("session_id")
            if not sess_id:
                self._send_json(400, {"error": "缺少 session_id 参数"})
                return
            ok = SessionManager.delete_session(sess_id)
            if AgentServiceHolder.current_session_id == sess_id:
                AgentServiceHolder.current_session_id = None
                AgentServiceHolder.memory.clear()
            self._send_json(200, {"success": ok})
            return

        elif path == "/api/config":
            api_key = payload.get("api_key")
            api_base = payload.get("api_base")
            model = payload.get("model")
            client = AgentServiceHolder.llm_client

            if api_key is not None:
                client.api_key = api_key.strip()
            if api_base:
                client.api_base = api_base.strip().rstrip("/")
            if model:
                from smart_agent.agent.llm_client import normalize_model_name
                client.model = normalize_model_name(model.strip())

            has_key = client.has_valid_key()
            if not has_key:
                self._send_json(400, {"error": "API Key 格式无效或过短，请检查填写的密钥"})
                return

            # 持久化保存到本地，防止重启服务丢失密钥
            try:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "api_base": client.api_base,
                        "api_key": client.api_key,
                        "model": client.model,
                    }, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.warning(f"持久化保存配置异常: {e}")

            self._send_json(200, {
                "status": "success",
                "message": f"大模型配置成功！已连接 {client.model}",
                "has_key": True,
                "model": client.model,
                "api_base": client.api_base,
            })
            return

        elif path == "/api/clear":
            AgentServiceHolder.memory.clear()
            self._send_json(200, {"status": "cleared", "message": "行程会话上下文已重置"})
            return

        self._send_json(404, {"error": "Not Found"})


def run_server(host: str = SERVER_HOST, port: int = SERVER_PORT):
    """启动轻量 HTTP 旅游智能体服务器"""
    AgentServiceHolder.initialize()
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, SmartAgentHTTPRequestHandler)
    print("=" * 65)
    print(f"🌍 SmartAgent 智能旅游规划系统已启动！")
    print(f"👉 访问地址: http://{host}:{port}")
    print(f"👥 开发团队: 赵海翔 (3124004113) · 何卓文 (3124004132) · 吴与同 (3124004018)")
    print(f"🛠️ 已挂载专用 MCP 旅游工具: {len(AgentServiceHolder.mcp_client.get_tools())} 个")
    print(f"🎨 UI 风格: 极简白底 + 莫兰迪自然色系 (Morandi Aesthetic)")
    print(f"🔒 模式规范: 强制接入真实在线大模型 API (通义千问/DeepSeek/智谱/OpenAI)")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务正常停止。")
        httpd.server_close()
