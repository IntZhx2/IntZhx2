"""
Model Context Protocol (MCP) 核心模块
"""

from smart_agent.mcp.protocol import (
    ToolDefinition,
    ToolCallResult,
    JSONRPCRequest,
    JSONRPCResponse,
)
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient

__all__ = [
    "ToolDefinition",
    "ToolCallResult",
    "JSONRPCRequest",
    "JSONRPCResponse",
    "MCPServer",
    "MCPClient",
]
