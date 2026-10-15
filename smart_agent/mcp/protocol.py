"""
Model Context Protocol (MCP) 核心协议规范
基于 JSON-RPC 2.0 标准规范实现 MCP 协议的数据结构、序列化与错误码定义。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import json


# 标准 JSON-RPC 2.0 错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class ToolDefinition:
    """MCP 工具元数据描述"""
    name: str
    description: str
    input_schema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    def to_llm_tool(self) -> Dict[str, Any]:
        """转换为 OpenAI/通用大模型标准的 tool schema 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            }
        }


@dataclass
class ToolCallResult:
    """MCP 工具调用执行结果"""
    content: List[Dict[str, Any]]
    is_error: bool = False

    @classmethod
    def text(cls, text: str, is_error: bool = False) -> "ToolCallResult":
        return cls(content=[{"type": "text", "text": text}], is_error=is_error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "isError": self.is_error,
        }

    def get_text(self) -> str:
        texts = [c.get("text", "") for c in self.content if c.get("type") == "text"]
        return "\n".join(texts)


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 请求对象"""
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None
    jsonrpc: str = "2.0"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JSONRPCRequest":
        if not isinstance(data, dict):
            raise ValueError("Invalid JSON-RPC format: not a dict")
        if data.get("jsonrpc") != "2.0":
            raise ValueError(f"Unsupported jsonrpc version: {data.get('jsonrpc')}")
        if "method" not in data or not isinstance(data["method"], str):
            raise ValueError("Missing or invalid 'method'")
        return cls(
            method=data["method"],
            params=data.get("params"),
            id=data.get("id"),
            jsonrpc="2.0",
        )

    def to_dict(self) -> Dict[str, Any]:
        res = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            res["params"] = self.params
        if self.id is not None:
            res["id"] = self.id
        return res


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 响应对象"""
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            res["error"] = self.error
        else:
            res["result"] = self.result
        return res

    @classmethod
    def success(cls, req_id: Optional[Union[str, int]], result: Any) -> "JSONRPCResponse":
        return cls(id=req_id, result=result)

    @classmethod
    def fail(cls, req_id: Optional[Union[str, int]], code: int, message: str, data: Any = None) -> "JSONRPCResponse":
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return cls(id=req_id, error=err)
