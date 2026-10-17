"""
Web 服务与 REST API 单元测试 (基于内存 Mock 隔离，零端口与网络依赖)
"""

import unittest
import json
from io import BytesIO
from smart_agent.web.server import SmartAgentHTTPRequestHandler, AgentServiceHolder
from smart_agent.tools.todo_tool import _db_manager


class MockHTTPConnection:
    """基于内存 BytesIO 的 HTTP 传输流模拟器"""
    def __init__(self, request_bytes: bytes):
        self.rfile = BytesIO(request_bytes)
        self.wfile = BytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "b" in mode:
            if "r" in mode:
                return self.rfile
            return self.wfile
        raise ValueError("Only binary mode is supported")

    def sendall(self, data):
        self.wfile.write(data)


def simulate_http_request(method: str, path: str, body: dict = None) -> tuple:
    """模拟单次完整的 HTTP 请求与响应解析"""
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

    # 实例化并执行 Handler
    handler = SmartAgentHTTPRequestHandler(mock_conn, ("127.0.0.1", 8000), None)

    # 解析响应
    resp_raw = mock_conn.wfile.getvalue().decode("utf-8", errors="ignore")
    lines = resp_raw.split("\r\n")
    status_line = lines[0]
    status_code = int(status_line.split(" ")[1])

    # 寻找空行提取 JSON 正文
    empty_idx = -1
    for i, line in enumerate(lines):
        if line == "":
            empty_idx = i
            break

    body_str = "\r\n".join(lines[empty_idx + 1:]) if empty_idx != -1 else ""
    parsed_json = json.loads(body_str) if body_str else {}
    return status_code, parsed_json


class TestWebServerAndAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        AgentServiceHolder.initialize()

    def setUp(self):
        with _db_manager.get_connection() as conn:
            conn.execute("DELETE FROM todos")
            conn.commit()

    def test_status_endpoint(self):
        status, data = simulate_http_request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "online")
        self.assertEqual(len(data["team"]), 3)

    def test_tools_endpoint(self):
        status, data = simulate_http_request("GET", "/api/tools")
        self.assertEqual(status, 200)
        tools = data["tools"]
        self.assertGreater(len(tools), 5)
        names = [t["name"] for t in tools]
        self.assertIn("todo_add", names)
        self.assertIn("weather_query", names)
        self.assertIn("calculate", names)

    def test_todos_crud_api(self):
        # 1. POST 添加
        status, res = simulate_http_request("POST", "/api/todos", {
            "title": "测试待办项目",
            "priority": "high",
            "category": "study"
        })
        self.assertEqual(status, 200)
        task_id = res["id"]

        # 2. GET 列表
        status, res = simulate_http_request("GET", "/api/todos")
        self.assertEqual(status, 200)
        self.assertEqual(len(res["todos"]), 1)
        self.assertEqual(res["todos"][0]["title"], "测试待办项目")

        # 3. PATCH 更新
        status, res = simulate_http_request("PATCH", f"/api/todos/{task_id}", {"status": "completed"})
        self.assertEqual(status, 200)
        self.assertEqual(res["new_status"], "completed")

        # 4. DELETE 删除
        status, res = simulate_http_request("DELETE", f"/api/todos/{task_id}")
        self.assertEqual(status, 200)
        self.assertEqual(res["status"], "deleted")

    def test_chat_and_tool_execution(self):
        # 测试 /api/chat 发送自然语言指令
        status, data = simulate_http_request("POST", "/api/chat", {
            "message": "添加任务：提交软件工程博客，优先级高"
        })
        self.assertEqual(status, 200)
        self.assertIn("answer", data)
        self.assertGreater(len(data["traces"]), 0)

        # 验证数据库中确实产生了任务
        status, res = simulate_http_request("GET", "/api/todos")
        self.assertEqual(status, 200)
        self.assertEqual(len(res["todos"]), 1)
        self.assertIn("提交软件工程博客", res["todos"][0]["title"])


if __name__ == "__main__":
    unittest.main()
