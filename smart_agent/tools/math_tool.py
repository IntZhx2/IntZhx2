"""
精确数学计算与安全沙箱执行工具
提供无精度损失的算术运算与受控环境下的数据分析能力。
"""

import ast
import math
import operator
from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult


class SafeEvaluator(ast.NodeVisitor):
    """基于 AST 语法树的安全数学表达式计算器，彻底规避任意代码注入危险"""

    ALLOWED_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    ALLOWED_FUNCTIONS = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "log": math.log,
        "pi": math.pi,
        "e": math.e,
    }

    def evaluate(self, expr: str) -> Any:
        try:
            tree = ast.parse(expr, mode="eval")
            return self.visit(tree.body)
        except Exception as e:
            raise ValueError(f"无法解析表达式 '{expr}': {str(e)}")

    def visit_Constant(self, node: ast.Constant) -> Any:
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"不允许的常量类型: {type(node.value)}")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op = type(node.op)
        if op in self.ALLOWED_OPERATORS:
            val = self.visit(node.operand)
            return self.ALLOWED_OPERATORS[op](val)
        raise ValueError(f"不支持的一元运算符: {op}")

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op = type(node.op)
        if op in self.ALLOWED_OPERATORS:
            left = self.visit(node.left)
            right = self.visit(node.right)
            if op == ast.Div and right == 0:
                raise ZeroDivisionError("除数不能为 0")
            return self.ALLOWED_OPERATORS[op](left, right)
        raise ValueError(f"不支持的二元运算符: {op}")

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.ALLOWED_FUNCTIONS:
                func = self.ALLOWED_FUNCTIONS[func_name]
                args = [self.visit(arg) for arg in node.args]
                return func(*args)
        raise ValueError(f"不允许调用未受信任的函数")

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in self.ALLOWED_FUNCTIONS:
            return self.ALLOWED_FUNCTIONS[node.id]
        raise ValueError(f"未定义的数学常量: {node.id}")

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"不安全或不支持的语法节点: {type(node).__name__}")


class CalculateTool(BaseTool):
    def __init__(self):
        self._evaluator = SafeEvaluator()

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return "执行精确的数学运算或表达式求值，支持加减乘除、乘方、取模以及常用数学函数（sqrt, abs, round, sin, cos）。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式字符串，如 '25 * (120 - 45) / 5' 或 'sqrt(144) + 18'",
                },
            },
            "required": ["expression"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        expr = kwargs.get("expression", "").strip()
        if not expr:
            return ToolCallResult.text("错误: expression 不能为空", is_error=True)

        try:
            val = self._evaluator.evaluate(expr)
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            return ToolCallResult.text(f"🔢 计算结果: {expr} = {val}")
        except Exception as e:
            return ToolCallResult.text(f"计算失败: {str(e)}", is_error=True)
