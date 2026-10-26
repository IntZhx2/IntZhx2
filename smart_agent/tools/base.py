"""
MCP 工具抽象基类与注册机制
支持以 Python 原生函数或面向对象类形式快速封装符合 MCP 标准规范的工具。
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
import inspect
from smart_agent.mcp.protocol import ToolDefinition, ToolCallResult


class BaseTool(ABC):
    """MCP 工具基础抽象类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具唯一标识符"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述，用于大模型判断何时调用"""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema 格式的参数规格"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> ToolCallResult:
        """执行工具逻辑并返回统一结构"""
        pass

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
        )

    def validate_arguments(self, arguments: Any) -> None:
        """Validate our JSON Schema subset; raise ValueError before any tool executes.

        Supports type (including nullable unions), required, enum, properties,
        additionalProperties and array items, recursively. This is not a full
        JSON Schema implementation (e.g. $ref and combinators are unsupported).
        """
        if not isinstance(arguments, dict) or any(not isinstance(k, str) for k in arguments):
            raise ValueError("arguments must be an object with string keys")
        self._validate_value(arguments, self.input_schema, "arguments")

    @staticmethod
    def _validate_value(value: Any, schema: Any, path: str) -> None:
        if schema is True:
            return
        if schema is False:
            raise ValueError(f"{path} is not allowed")
        checks = {
            "object": lambda v: isinstance(v, dict),
            "array": lambda v: isinstance(v, list),
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: (type(v) is int or
                                  (type(v) is float and v.is_integer())),
            "number": lambda v: type(v) in (int, float),
            "boolean": lambda v: type(v) is bool,
            "null": lambda v: v is None,
        }
        declared = schema.get("type")
        types = declared if isinstance(declared, list) else [declared]
        if declared is not None and not any(checks[t](value) for t in types):
            raise ValueError(f"{path} must have type {declared}")
        if "enum" in schema and not any(
            BaseTool._json_equal(value, choice) for choice in schema["enum"]
        ):
            raise ValueError(f"{path} must be one of {schema['enum']!r}")
        if isinstance(value, dict):
            if any(not isinstance(k, str) for k in value):
                raise ValueError(f"{path} must have string keys")
            for key in schema.get("required", []):
                if key not in value:
                    raise ValueError(f"{path}.{key} is required")
            properties = schema.get("properties", {})
            additional = schema.get("additionalProperties", True)
            for key, item in value.items():
                child = properties.get(key, additional)
                BaseTool._validate_value(item, child, f"{path}.{key}")
        elif isinstance(value, list) and "items" in schema:
            for index, item in enumerate(value):
                BaseTool._validate_value(item, schema["items"], f"{path}[{index}]")

    @staticmethod
    def _json_equal(left: Any, right: Any) -> bool:
        """JSON booleans are distinct from numbers, unlike Python's True == 1."""
        if type(left) in (int, float) and type(right) in (int, float):
            return left == right
        if type(left) is not type(right):
            return False
        if isinstance(left, dict):
            return left.keys() == right.keys() and all(
                BaseTool._json_equal(left[key], right[key]) for key in left
            )
        if isinstance(left, list):
            return len(left) == len(right) and all(
                BaseTool._json_equal(a, b) for a, b in zip(left, right)
            )
        return left == right


class FunctionTool(BaseTool):
    """基于函数与 Docstring/Type Hint 自动封装的工具"""

    def __init__(
        self,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
    ):
        self._func = func
        self._name = name or func.__name__
        self._description = description or (func.__doc__ or "").strip()
        self._schema = schema or self._generate_schema(func)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def input_schema(self) -> Dict[str, Any]:
        return self._schema

    def execute(self, **kwargs) -> ToolCallResult:
        try:
            result = self._func(**kwargs)
            if isinstance(result, ToolCallResult):
                return result
            if isinstance(result, (dict, list)):
                import json
                return ToolCallResult.text(json.dumps(result, ensure_ascii=False, indent=2))
            return ToolCallResult.text(str(result))
        except Exception as e:
            return ToolCallResult.text(f"工具执行异常: {type(e).__name__}: {str(e)}", is_error=True)

    @staticmethod
    def _generate_schema(func: Callable[..., Any]) -> Dict[str, Any]:
        """基于 inspect 解析函数签名生成 JSON Schema"""
        sig = inspect.signature(func)
        properties = {}
        required = []
        accepts_extra = False

        type_mapping = {
            int: "integer",
            float: "number",
            str: "string",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                accepts_extra = True
                continue
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                param_type = type_mapping.get(param.annotation, "string")

            prop_def = {"type": param_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)
            else:
                prop_def["default"] = param.default

            properties[param_name] = prop_def

        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": accepts_extra,
        }
