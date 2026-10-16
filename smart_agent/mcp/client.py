"""
Model Context Protocol (MCP) 客户端实现
由智能体核心调用，负责连接 MCP 服务端、拉取工具目录及发起安全工具执行。
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

    def refresh_tools(self) -> List[ToolDefinition]:
        """向 MCP Server 请求最新的工具列表"""
        req = JSONRPCRequest(method="tools/list", id="client-init-1").to_dict()
        resp_data = self._server.handle_request(req)
        if "error" in resp_data:
            logger.error(f"Failed to list tools from MCP server: {resp_data['error']}")
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

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolCallResult:
        """通过 MCP 协议向服务端发起工具执行请求"""
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
