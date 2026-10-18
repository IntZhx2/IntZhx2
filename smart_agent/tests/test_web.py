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


if __name__ == "__main__":
    unittest.main()
