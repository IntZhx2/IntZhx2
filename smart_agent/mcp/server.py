"""
Model Context Protocol (MCP) 服务端实现
管理工具注册表，对外提供标准 JSON-RPC 2.0 请求响应分发。
"""

from typing import Any, Dict, List, Optional
import json
import logging
from smart_agent.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    ToolDefinition,
    ToolCallResult,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from smart_agent.tools.base import BaseTool

logger = logging.getLogger("mcp.server")


class MCPServer:
    """MCP 服务端核心实现"""

    def __init__(self, name: str = "SmartAgent-MCP-Server", version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """注册工具到 MCP 服务"""
        self._tools[tool.name] = tool
        logger.info(f"Registered MCP tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        """获取所有可用工具清单"""
        return [tool.get_definition() for tool in self._tools.values()]

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> ToolCallResult:
        """执行指定工具"""
        tool = self._tools.get(name)
        if not tool:
            return ToolCallResult.text(f"错误: 未找到名为 '{name}' 的工具", is_error=True)

        args = arguments or {}
        return tool.execute(**args)

    def handle_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """处理符合 JSON-RPC 2.0 规范的请求字典"""
        req_id = request_payload.get("id")
        try:
            req = JSONRPCRequest.from_dict(request_payload)
        except Exception as e:
            return JSONRPCResponse.fail(req_id, -32600, f"无效的 JSON-RPC 请求: {str(e)}").to_dict()

        # 分发方法路由
        method = req.method
        params = req.params or {}

        if method == "tools/list":
            tools_data = [t.to_dict() for t in self.list_tools()]
            return JSONRPCResponse.success(req.id, {"tools": tools_data}).to_dict()

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not name or not isinstance(name, str):
                return JSONRPCResponse.fail(req.id, INVALID_PARAMS, "缺少或无效的 'name' 参数").to_dict()

            res = self.call_tool(name, arguments)
            return JSONRPCResponse.success(req.id, res.to_dict()).to_dict()

        elif method == "ping":
            return JSONRPCResponse.success(req.id, {"status": "pong", "server": self.name}).to_dict()

        elif method == "server/info":
            return JSONRPCResponse.success(req.id, {
                "name": self.name,
                "version": self.version,
                "tools_count": len(self._tools),
            }).to_dict()

        else:
            return JSONRPCResponse.fail(req.id, METHOD_NOT_FOUND, f"不支持的方法: {method}").to_dict()
