"""
旅游规划 Web 服务与 REST API 单元测试 (基于内存 Mock 隔离)
"""

import unittest
import json
from io import BytesIO
from smart_agent.web.server import SmartAgentHTTPRequestHandler, AgentServiceHolder
from smart_agent.config import WORKSPACE_DIR


class MockHTTPConnection:
    def __init__(self, request_bytes: bytes):
        self.rfile = BytesIO(request_bytes)
        self.wfile = BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            return self.wfile
        raise ValueError("Only binary mode supported")

    def sendall(self, data):
        self.wfile.write(data)


def simulate_http_request(method: str, path: str, body: dict = None) -> tuple:
    body_bytes = json.dumps(body).encode("utf-8") if body else b""
    headers = [
        f"{method} {path} HTTP/1.1",
        "Host: localhost",
        f"Content-Length: {len(body_bytes)}",
        "Content-Type: application/json",
        "",
        "",
    ]
    raw_req = "\r\n".join(headers).encode("utf-8") + body_bytes
    mock_conn = MockHTTPConnection(raw_req)

    handler = SmartAgentHTTPRequestHandler(mock_conn, ("127.0.0.1", 8000), None)

    resp_raw = mock_conn.wfile.getvalue().decode("utf-8", errors="ignore")
    lines = resp_raw.split("\r\n")
    status_code = int(lines[0].split(" ")[1])

    empty_idx = -1
    for i, line in enumerate(lines):
        if line == "":
            empty_idx = i
            break

    body_str = "\r\n".join(lines[empty_idx + 1:]) if empty_idx != -1 else ""
    parsed_json = json.loads(body_str) if body_str else {}
    return status_code, parsed_json


class TestTravelWebServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from smart_agent.web.server import CONFIG_FILE
        cls._orig_config_bytes = CONFIG_FILE.read_bytes() if CONFIG_FILE.exists() else None
        AgentServiceHolder.initialize()

    @classmethod
    def tearDownClass(cls):
        from smart_agent.web.server import CONFIG_FILE
        if cls._orig_config_bytes is not None:
            CONFIG_FILE.write_bytes(cls._orig_config_bytes)
        elif CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        AgentServiceHolder.initialize()

    def test_status_endpoint(self):
        status, data = simulate_http_request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertIn("status", data)
        self.assertEqual(len(data["team"]), 3)

    def test_travel_tools_endpoint(self):
        status, data = simulate_http_request("GET", "/api/tools")
        self.assertEqual(status, 200)
        tools = data["tools"]
        names = [t["name"] for t in tools]
        self.assertIn("weather_query", names)
        self.assertIn("traffic_transit", names)
        self.assertIn("attraction_info", names)
        self.assertIn("itinerary_save", names)

    def test_config_api(self):
        # 1. 验证 GET /api/config
        status, cfg = simulate_http_request("GET", "/api/config")
        self.assertEqual(status, 200)
        self.assertIn("has_key", cfg)

        # 2. 验证 POST /api/config 配置 Key
        status, post_res = simulate_http_request("POST", "/api/config", {
            "api_key": "sk-test-valid-user-key-654321",
            "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen-plus"
        })
        self.assertEqual(status, 200)
        self.assertTrue(post_res["has_key"])

    def test_chat_without_api_key(self):
        # 将 Key 置空
        AgentServiceHolder.llm_client.api_key = ""
        status, data = simulate_http_request("POST", "/api/chat", {
            "message": "帮我规划广州2日游，周六下午3点必须到广州塔"
        })
        self.assertEqual(status, 400)
        self.assertIn("未配置大模型 API Key", data["error"])

    def test_itineraries_list_api(self):
        # 保存一份测试文档
        test_file = WORKSPACE_DIR / "test_api_travel.md"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# 广州2日游一条龙方案\n测试内容")

        status, data = simulate_http_request("GET", "/api/itineraries")
        self.assertEqual(status, 200)
        filenames = [item["filename"] for item in data["itineraries"]]
        self.assertIn("test_api_travel.md", filenames)

        if test_file.exists():
            test_file.unlink()


    def test_sessions_list_endpoint(self):
        status, data = simulate_http_request("GET", "/api/sessions")
        self.assertEqual(status, 200)
        self.assertIn("sessions", data)
        self.assertIn("active_session_id", data)

    def test_session_get_and_continuation_endpoint(self):
        # 创建一个测试会话
        from smart_agent.agent.session_manager import SessionManager
        sess = SessionManager.create_new_session("Web端测试广州游")
        sess_id = sess["session_id"]
        SessionManager.append_turn(
            session_id=sess_id,
            user_prompt="周六下午3点去广州塔",
            assistant_response="建议14:30到达广州塔",
            step_traces=[],
            llm_messages=[],
        )

        # 1. 正常获取并激活
        status, data = simulate_http_request("GET", f"/api/session?id={sess_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["session_id"], sess_id)
        self.assertEqual(len(data["turns"]), 1)
        self.assertEqual(AgentServiceHolder.current_session_id, sess_id)

        # 2. 缺少参数
        status, err_data = simulate_http_request("GET", "/api/session")
        self.assertEqual(status, 400)

        # 3. 不存在的会话
        status, not_found_data = simulate_http_request("GET", "/api/session?id=sess_not_exist_99999")
        self.assertEqual(status, 404)

        SessionManager.delete_session(sess_id)

    def test_mcp_jsonrpc_endpoint(self):
        # 测试通过 POST /api/mcp 外部接入标准 MCP JSON-RPC 2.0 协议
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "external-rpc-1"
        }
        status, data = simulate_http_request("POST", "/api/mcp", payload)
        self.assertEqual(status, 200)
        self.assertEqual(data.get("jsonrpc"), "2.0")
        self.assertIn("result", data)
        tools = data["result"].get("tools", [])
        tool_names = [t["name"] for t in tools]
        self.assertIn("weather_query", tool_names)
        self.assertIn("traffic_transit", tool_names)
        self.assertIn("attraction_info", tool_names)


if __name__ == "__main__":
    unittest.main()
