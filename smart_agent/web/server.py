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
from smart_agent.config import SERVER_HOST, SERVER_PORT, BASE_DIR, WORKSPACE_DIR
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.agent.core import SmartAgent
from smart_agent.tools import create_default_tools

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
        cls.mcp_server = MCPServer(name="SmartAgent-Travel-Server")
        for tool in create_default_tools():
            cls.mcp_server.register_tool(tool)

        cls.mcp_client = MCPClient(cls.mcp_server)
        cls.llm_client = LLMClient()
        cls.memory = ConversationMemory(session_id="travel_web_session")
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

            try:
                res = AgentServiceHolder.agent.run(message)
                self._send_json(200, res.to_dict())
            except Exception as e:
                self._send_json(400, {"error": str(e)})
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

            has_key = client.has_valid_key()
            if not has_key:
                self._send_json(400, {"error": "API Key 格式无效或过短，请检查填写的密钥"})
                return

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
