"""
Model Context Protocol (MCP) 服务端实现。
In-process partial MCP 2024-11-05 subset: initialize/initialized, tools and ping
over JSON-RPC dictionaries. No transport, batch requests, resources or prompts;
this adapter does not require the official SDK or claim full MCP compliance.
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
    INVALID_REQUEST,
)
from smart_agent.tools.base import BaseTool

logger = logging.getLogger("mcp.server")
_MISSING_ARGUMENTS = object()


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

    def call_tool(self, name: str, arguments: Any = _MISSING_ARGUMENTS) -> ToolCallResult:
        """Validate and contain failures for every caller and every BaseTool subclass."""
        if not isinstance(name, str) or not name:
            return ToolCallResult.text("错误: 工具 name 必须为非空字符串", is_error=True)
        tool = self._tools.get(name)
        if not tool:
            return ToolCallResult.text(f"错误: 未找到名为 '{name}' 的工具", is_error=True)

        args = {} if arguments is _MISSING_ARGUMENTS else arguments
        try:
            tool.validate_arguments(args)
        except (TypeError, ValueError) as exc:
            return ToolCallResult.text(f"工具参数无效: {exc}", is_error=True)
        except Exception as exc:
            logger.warning("Tool schema validation failed (%s)", type(exc).__name__)
            return ToolCallResult.text(f"工具校验异常: {type(exc).__name__}: {exc}", is_error=True)
        try:
            result = tool.execute(**args)
            if not isinstance(result, ToolCallResult):
                raise TypeError("tool must return ToolCallResult")
            return result
        except Exception as exc:
            logger.warning("Tool execution failed (%s)", type(exc).__name__)
            return ToolCallResult.text(f"工具执行异常: {type(exc).__name__}: {exc}", is_error=True)

    def handle_request(self, request_payload: Any) -> Optional[Dict[str, Any]]:
        """Handle one request; valid notifications always return None, even on errors."""
        if not isinstance(request_payload, dict):
            return JSONRPCResponse.fail(None, INVALID_REQUEST, "请求必须是 JSON-RPC 对象").to_dict()
        req_id = request_payload.get("id")
        if req_id is not None and type(req_id) not in (str, int, float):
            return JSONRPCResponse.fail(None, INVALID_REQUEST, "无效的请求 id").to_dict()
        try:
            req = JSONRPCRequest.from_dict(request_payload)
        except Exception as e:
            return JSONRPCResponse.fail(req_id, INVALID_REQUEST, f"无效的 JSON-RPC 请求: {str(e)}").to_dict()

        notification = "id" not in request_payload
        params = request_payload.get("params", {})
        try:
            if not isinstance(params, dict):
                response = JSONRPCResponse.fail(req.id, INVALID_PARAMS, "params 必须是对象").to_dict()
            else:
                response = self._dispatch(req, params)
        except Exception as exc:
            logger.warning("MCP request failed (%s)", type(exc).__name__)
            response = JSONRPCResponse.fail(req.id, INTERNAL_ERROR, "内部服务错误").to_dict()
        return None if notification else response

    def _dispatch(self, req: JSONRPCRequest, params: Dict[str, Any]) -> Dict[str, Any]:
        method = req.method

        if method == "tools/list":
            tools_data = [t.to_dict() for t in self.list_tools()]
            return JSONRPCResponse.success(req.id, {"tools": tools_data}).to_dict()

        elif method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", _MISSING_ARGUMENTS)
            if not name or not isinstance(name, str):
                return JSONRPCResponse.fail(req.id, INVALID_PARAMS, "缺少或无效的 'name' 参数").to_dict()

            res = self.call_tool(name, arguments)
            return JSONRPCResponse.success(req.id, res.to_dict()).to_dict()

        elif method == "initialize":
            return JSONRPCResponse.success(req.id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }).to_dict()

        elif method == "notifications/initialized":
            return JSONRPCResponse.success(req.id, {}).to_dict()

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
