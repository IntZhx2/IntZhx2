"""
Model Context Protocol (MCP) 客户端实现。
In-process partial MCP 2024-11-05 adapter, without an official SDK dependency.
Supports initialize/initialized and tools; no transport or full MCP lifecycle.
"""

from typing import Any, Dict, List, Optional
import json
import logging
from smart_agent.mcp.protocol import (
    JSONRPCRequest,
    ToolDefinition,
    ToolCallResult,
)
from smart_agent.mcp.server import MCPServer

logger = logging.getLogger("mcp.client")


class MCPClient:
    """MCP 客户端适配器"""

    def __init__(self, server: MCPServer):
        self._server = server
        self._cached_tools: Optional[List[ToolDefinition]] = None
        self._initialized = False
        self.server_info: Optional[Dict[str, Any]] = None

    def initialize(self) -> Dict[str, Any]:
        """Complete the handshake once, before listing or calling tools."""
        if self._initialized:
            return self.server_info
        req = JSONRPCRequest(
            method="initialize",
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "SmartAgent-MCP-Client", "version": "1.0.0"},
            },
            id="client-initialize",
        ).to_dict()
        resp = self._server.handle_request(req)
        if not isinstance(resp, dict) or "error" in resp:
            raise RuntimeError("MCP initialize failed")
        result = resp.get("result")
        if (not isinstance(result, dict) or result.get("protocolVersion") != "2024-11-05"
                or not isinstance(result.get("serverInfo"), dict)
                or not isinstance(result.get("capabilities"), dict)
                or not isinstance(result.get("capabilities", {}).get("tools"), dict)):
            raise RuntimeError("MCP initialize returned an unsupported server response")
        self._server.handle_request(JSONRPCRequest(method="notifications/initialized").to_dict())
        self.server_info = result["serverInfo"]
        self._initialized = True
        return self.server_info

    def refresh_tools(self) -> List[ToolDefinition]:
        """向 MCP Server 请求最新的工具列表"""
        self.initialize()
        req = JSONRPCRequest(method="tools/list", id="client-init-1").to_dict()
        resp_data = self._server.handle_request(req)
        if "error" in resp_data:
            logger.warning("Failed to list tools from MCP server")
            return []

        tools_raw = resp_data.get("result", {}).get("tools", [])
        tools = []
        for t in tools_raw:
            tools.append(ToolDefinition(
                name=t["name"],
                description=t["description"],
                input_schema=t["inputSchema"],
            ))
        self._cached_tools = tools
        return tools

    def get_tools(self) -> List[ToolDefinition]:
        """获取工具定义列表（带内存缓存）"""
        if self._cached_tools is None:
            return self.refresh_tools()
        return self._cached_tools

    def get_llm_tools_schema(self) -> List[Dict[str, Any]]:
        """转换为通用大模型 function calling 的 tools 格式"""
        return [t.to_llm_tool() for t in self.get_tools()]

    def call_tool(self, name: str, arguments: Any) -> ToolCallResult:
        """通过 MCP 协议向服务端发起工具执行请求"""
        self.initialize()
        req = JSONRPCRequest(
            method="tools/call",
            params={"name": name, "arguments": arguments},
            id="client-call",
        ).to_dict()

        resp_data = self._server.handle_request(req)
        if "error" in resp_data:
            err = resp_data["error"]
            return ToolCallResult.text(f"MCP 协议调用错误 [{err.get('code')}]: {err.get('message')}", is_error=True)

        res = resp_data.get("result", {})
        return ToolCallResult(
            content=res.get("content", []),
            is_error=res.get("isError", False),
        )
