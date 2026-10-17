"""
MCP 协议与服务端单元测试
"""

import unittest
from smart_agent.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    ToolDefinition,
    ToolCallResult,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
)
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.tools.base import BaseTool


class DummyEchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo_tool"

    @property
    def description(self) -> str:
        return "回显测试工具"

    @property
    def input_schema(self):
        return {
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        }

    def execute(self, **kwargs):
        return ToolCallResult.text(f"echo: {kwargs.get('msg')}")


class TestMCPProtocolAndServer(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer(name="Test-Server")
        self.tool = DummyEchoTool()
        self.server.register_tool(self.tool)
        self.client = MCPClient(self.server)

    def test_jsonrpc_request_parsing(self):
        valid = {"jsonrpc": "2.0", "method": "tools/list", "id": 1}
        req = JSONRPCRequest.from_dict(valid)
        self.assertEqual(req.method, "tools/list")
        self.assertEqual(req.id, 1)

        with self.assertRaises(ValueError):
            JSONRPCRequest.from_dict({"method": "tools/list"})  # 缺少 jsonrpc

    def test_tools_list(self):
        req = {"jsonrpc": "2.0", "method": "tools/list", "id": 100}
        resp = self.server.handle_request(req)
        self.assertIn("result", resp)
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "echo_tool")

    def test_tools_call_success(self):
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "echo_tool", "arguments": {"msg": "hello_mcp"}},
            "id": 101,
        }
        resp = self.server.handle_request(req)
        self.assertIn("result", resp)
        content = resp["result"]["content"]
        self.assertEqual(content[0]["text"], "echo: hello_mcp")
        self.assertFalse(resp["result"]["isError"])

    def test_tools_call_not_found(self):
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "non_exist_tool", "arguments": {}},
            "id": 102,
        }
        resp = self.server.handle_request(req)
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("未找到名为", resp["result"]["content"][0]["text"])

    def test_method_not_found(self):
        req = {"jsonrpc": "2.0", "method": "unknown_api", "id": 103}
        resp = self.server.handle_request(req)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], METHOD_NOT_FOUND)

    def test_ping(self):
        req = {"jsonrpc": "2.0", "method": "ping", "id": 104}
        resp = self.server.handle_request(req)
        self.assertEqual(resp["result"]["status"], "pong")

    def test_client_integration(self):
        tools = self.client.get_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "echo_tool")

        # 验证 LLM schema 格式化
        llm_tools = self.client.get_llm_tools_schema()
        self.assertEqual(llm_tools[0]["type"], "function")
        self.assertEqual(llm_tools[0]["function"]["name"], "echo_tool")

        # 客户端执行
        res = self.client.call_tool("echo_tool", {"msg": "client_call"})
        self.assertEqual(res.get_text(), "echo: client_call")


if __name__ == "__main__":
    unittest.main()
