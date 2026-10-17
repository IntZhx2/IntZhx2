"""
轻量高性能 Web 服务端 (Web HTTP & REST Server)
纯原生 Python 标准库实现，零第三方依赖，提供完整的 Agent 交互 API 与静态资源托管。
"""

import http.server
import json
import logging
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional
from smart_agent.config import SERVER_HOST, SERVER_PORT, BASE_DIR
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.agent.core import SmartAgent
from smart_agent.tools import create_default_tools
from smart_agent.tools.todo_tool import _db_manager

logger = logging.getLogger("web.server")
STATIC_DIR = BASE_DIR / "web" / "static"


class AgentServiceHolder:
    """智能体与 MCP 服务单例持有者"""
    mcp_server: MCPServer
    mcp_client: MCPClient
    llm_client: LLMClient
    agent: SmartAgent
    memory: ConversationMemory

    @classmethod
    def initialize(cls):
        cls.mcp_server = MCPServer(name="SmartAgent-Web-Server")
        for tool in create_default_tools():
            cls.mcp_server.register_tool(tool)

        cls.mcp_client = MCPClient(cls.mcp_server)
        cls.llm_client = LLMClient()
        cls.memory = ConversationMemory(session_id="web_default")
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
        # 简化控制台请求日志
        pass

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
            self._send_json(200, {
                "status": "online",
                "server": "SmartAgent-Web-Server",
                "tools_count": len(tools),
                "model": AgentServiceHolder.llm_client.model,
                "team": [
                    {"name": "赵海翔", "id": "3124004113", "role": "架构设计与智能体内核"},
                    {"name": "何卓文", "id": "3124004132", "role": "MCP 服务端与工具生态"},
                    {"name": "吴与同", "id": "3124004018", "role": "Web 交互与多模态语音工程"},
                ]
            })
            return

        elif path == "/api/tools":
            tools = [t.to_dict() for t in AgentServiceHolder.mcp_client.get_tools()]
            self._send_json(200, {"tools": tools})
            return

        elif path == "/api/todos":
            try:
                with _db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM todos ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id DESC")
                    rows = [dict(r) for r in cursor.fetchall()]
                self._send_json(200, {"todos": rows})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        elif path == "/api/history":
            history = AgentServiceHolder.memory.get_history_summary()
            self._send_json(200, {"history": history})
            return

        elif path == "/api/config":
            client = AgentServiceHolder.llm_client
            has_key = bool(client.api_key and len(client.api_key.strip()) > 5)
            masked = ""
            if has_key:
                k = client.api_key.strip()
                masked = k[:3] + "..." + k[-4:] if len(k) > 7 else "***"
            self._send_json(200, {
                "api_base": client.api_base,
                "model": client.model,
                "has_key": has_key,
                "masked_key": masked,
                "engine_mode": "online_llm" if has_key else "local_fallback",
            })
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
                self._send_json(400, {"error": "message 不能为空"})
                return

            try:
                res = AgentServiceHolder.agent.run(message)
                self._send_json(200, res.to_dict())
            except Exception as e:
                self._send_json(500, {"error": f"Agent 执行异常: {str(e)}"})
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
                client.model = model.strip()

            has_key = bool(client.api_key and len(client.api_key.strip()) > 5)
            engine_mode = "online_llm" if has_key else "local_fallback"
            self._send_json(200, {
                "status": "success",
                "message": "大模型与 API 配置已生效！" if has_key else "已切换为本地离线智能兜底引擎。",
                "engine_mode": engine_mode,
                "model": client.model,
                "api_base": client.api_base,
            })
            return

        elif path == "/api/clear":
            AgentServiceHolder.memory.clear()
            self._send_json(200, {"status": "cleared", "message": "会话历史已清空"})
            return

        elif path == "/api/todos":
            title = payload.get("title", "").strip()
            priority = payload.get("priority", "medium")
            category = payload.get("category", "general")
            due_date = payload.get("due_date", "")

            if not title:
                self._send_json(400, {"error": "title 不能为空"})
                return

            try:
                with _db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO todos (title, priority, category, due_date, status) VALUES (?, ?, ?, ?, 'pending')",
                        (title, priority, category, due_date),
                    )
                    conn.commit()
                    new_id = cursor.lastrowid
                self._send_json(200, {"status": "created", "id": new_id})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        self._send_json(404, {"error": "Not Found"})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/todos/"):
            try:
                task_id = int(path.split("/")[-1])
            except ValueError:
                self._send_json(400, {"error": "无效的 task_id"})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            new_status = payload.get("status", "completed")

            try:
                with _db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE todos SET status = ? WHERE id = ?", (new_status, task_id))
                    conn.commit()
                self._send_json(200, {"status": "updated", "id": task_id, "new_status": new_status})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        self._send_json(404, {"error": "Not Found"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/todos/"):
            try:
                task_id = int(path.split("/")[-1])
            except ValueError:
                self._send_json(400, {"error": "无效的 task_id"})
                return

            try:
                with _db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM todos WHERE id = ?", (task_id,))
                    conn.commit()
                self._send_json(200, {"status": "deleted", "id": task_id})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return

        self._send_json(404, {"error": "Not Found"})


def run_server(host: str = SERVER_HOST, port: int = SERVER_PORT):
    """启动轻量 HTTP 智能体交互服务器"""
    AgentServiceHolder.initialize()
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, SmartAgentHTTPRequestHandler)
    print("=" * 65)
    print(f"🚀 SmartAgent 智能体 Web 服务已启动！")
    print(f"👉 本地访问地址: http://{host}:{port}")
    print(f"👥 开发团队: 赵海翔 (3124004113) 何卓文 (3124004132) 吴与同 (3124004018)")
    print(f"🛠️ 已注册 MCP 工具: {len(AgentServiceHolder.mcp_client.get_tools())} 个")
    print(f"💡 加分项就绪: 多轮对话记忆 | 语音输入输出 (STT/TTS) | SQLite 数据库 | Web 交互端")
    print("=" * 65)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务正常停止。")
        httpd.server_close()
