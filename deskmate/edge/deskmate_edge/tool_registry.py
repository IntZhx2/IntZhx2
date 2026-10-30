"""DeskMate Edge 工具注册中心 (tool_registry.py)
负责工具的注册、ToolSpec 自动生成、参数 Pydantic 校验、超时熔断与统一异常码封装
遵循 CONTRACTS.md §3.2 与 §3.3 规范
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Coroutine
from pydantic import BaseModel, ValidationError
from .protocol import ToolSpec

logger = logging.getLogger("deskmate_edge.tool_registry")


class RegisteredTool:
    """内部注册的工具实体封装"""
    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Coroutine[Any, Any, dict[str, Any]]],
        args_schema: type[BaseModel] | None = None,
        timeout_s: int = 10,
    ):
        self.name = name
        self.description = description
        self.func = func
        self.args_schema = args_schema
        self.timeout_s = timeout_s

    def to_spec(self) -> dict[str, Any]:
        """生成符合 OpenAI / CONTRACTS 规范的 ToolSpec"""
        params_schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": []
        }
        if self.args_schema:
            schema = self.args_schema.model_json_schema()
            params_schema["properties"] = schema.get("properties", {})
            params_schema["required"] = schema.get("required", [])

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params_schema,
            },
            "timeout_s": self.timeout_s
        }

    async def execute(self, raw_args: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
        """执行工具调用，含入参校验与超时防护
        返回: (ok: bool, data: dict, error_code: str | None)
        """
        # 1. 参数校验
        call_kwargs = raw_args
        if self.args_schema:
            try:
                validated_model = self.args_schema.model_validate(raw_args)
                call_kwargs = validated_model.model_dump()
            except ValidationError as ve:
                logger.warning(f"工具 {self.name} 入参校验失败: {ve}")
                return False, {}, f"BAD_ARGS: {ve.errors()}"

        # 2. 超时执行
        try:
            res = await asyncio.wait_for(self.func(**call_kwargs), timeout=self.timeout_s)
            return True, res or {}, None
        except asyncio.TimeoutError:
            logger.error(f"工具 {self.name} 执行超时 (>{self.timeout_s}s)")
            return False, {}, "TIMEOUT"
        except PermissionError as pe:
            logger.warning(f"工具 {self.name} 权限受限: {pe}")
            return False, {}, "PERMISSION_DENIED"
        except ConnectionError as ce:
            logger.warning(f"工具 {self.name} 设备离线: {ce}")
            return False, {}, "DEVICE_OFFLINE"
        except Exception as e:
            logger.exception(f"工具 {self.name} 内部执行异常: {e}")
            return False, {}, f"INTERNAL: {str(e)}"


class ToolRegistry:
    """全局工具注册中心"""
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        description: str,
        args_schema: type[BaseModel] | None = None,
        timeout_s: int = 10,
    ):
        """工具注册装饰器"""
        def decorator(func: Callable[..., Coroutine[Any, Any, dict[str, Any]]]):
            self._tools[name] = RegisteredTool(
                name=name,
                description=description,
                func=func,
                args_schema=args_schema,
                timeout_s=timeout_s,
            )
            return func
        return decorator

    def get_tool(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def get_all_specs(self) -> list[dict[str, Any]]:
        """获取所有已注册工具的 ToolSpec 清单，供 edge.hello 握手使用"""
        return [tool.to_spec() for tool in self._tools.values()]

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
        """统一指令分发"""
        tool = self.get_tool(tool_name)
        if not tool:
            logger.warning(f"未找到已注册的工具: {tool_name}")
            return False, {}, f"BAD_ARGS: tool '{tool_name}' not found"
        return await tool.execute(args)


# 全局单例
registry = ToolRegistry()
