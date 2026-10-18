"""
Model Context Protocol (MCP) 核心模块
"""

from smart_agent.mcp.protocol import (
    ToolDefinition,
    ToolCallResult,
    JSONRPCRequest,
    JSONRPCResponse,
)

__all__ = [
    "ToolDefinition",
    "ToolCallResult",
    "JSONRPCRequest",
    "JSONRPCResponse",
]
