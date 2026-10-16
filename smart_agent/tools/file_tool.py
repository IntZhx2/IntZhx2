"""
文件与工作区操作工具集
提供在安全沙箱工作空间内读写、检索与管理文件的功能，满足 AI 办公助理场景。
"""

import os
from pathlib import Path
from typing import Any, Dict, List
from smart_agent.config import WORKSPACE_DIR
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult


def _resolve_safe_path(filepath: str) -> Path:
    """解析安全沙箱路径，防止路径遍历攻击"""
    p = Path(filepath)
    if not p.is_absolute():
        p = WORKSPACE_DIR / p
    resolved = p.resolve()
    # 允许访问当前 workspace
    try:
        resolved.relative_to(WORKSPACE_DIR.resolve())
    except ValueError:
        # 如果超出 workspace，重定向回 workspace 根目录下
        resolved = (WORKSPACE_DIR / Path(filepath).name).resolve()
    return resolved


class FileReadTool(BaseTool):
    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return "读取工作区中指定文件的文本内容。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "文件相对路径或文件名"},
            },
            "required": ["filepath"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        filepath = kwargs.get("filepath", "")
        if not filepath:
            return ToolCallResult.text("错误: 缺少 filepath 参数", is_error=True)

        target = _resolve_safe_path(filepath)
        if not target.exists():
            return ToolCallResult.text(f"文件不存在: {filepath}", is_error=True)
        if not target.is_file():
            return ToolCallResult.text(f"目标不是一个普通文件: {filepath}", is_error=True)

        try:
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            return ToolCallResult.text(f"📄 文件内容 [{target.name}] ({len(content)} 字符):\n\n{content}")
        except Exception as e:
            return ToolCallResult.text(f"读取文件失败: {str(e)}", is_error=True)


class FileWriteTool(BaseTool):
    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "在工作区创建或覆写文件，支持保存待办清单、行程方案、备忘录等文本。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "保存的文件名或相对路径"},
                "content": {"type": "string", "description": "写入的文本内容"},
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "default": "write",
                    "description": "写入模式：write (覆盖) 或 append (追加)",
                },
            },
            "required": ["filepath", "content"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        filepath = kwargs.get("filepath", "")
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "write")

        if not filepath:
            return ToolCallResult.text("错误: 缺少 filepath 参数", is_error=True)

        target = _resolve_safe_path(filepath)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_mode = "a" if mode == "append" else "w"
            with open(target, write_mode, encoding="utf-8") as f:
                f.write(content)

            return ToolCallResult.text(
                f"✅ 文件已成功写入沙箱工作区: {target.name} ({len(content)} 字符, 模式: {mode})"
            )
        except Exception as e:
            return ToolCallResult.text(f"写入文件失败: {str(e)}", is_error=True)


class FileListTool(BaseTool):
    @property
    def name(self) -> str:
        return "file_list"

    @property
    def description(self) -> str:
        return "列出当前工作区中存在的所有文件和子目录清单。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    def execute(self, **kwargs) -> ToolCallResult:
        try:
            items = list(WORKSPACE_DIR.glob("*"))
            if not items:
                return ToolCallResult.text("📂 当前工作空间为空，暂无文件。")

            lines = [f"📂 工作空间文件列表 ({len(items)} 项):"]
            for item in sorted(items, key=lambda x: (not x.is_dir(), x.name)):
                if item.is_dir():
                    lines.append(f"📁 {item.name}/")
                else:
                    size_kb = item.stat().st_size / 1024
                    lines.append(f"📄 {item.name} ({size_kb:.1f} KB)")
            return ToolCallResult.text("\n".join(lines))
        except Exception as e:
            return ToolCallResult.text(f"列出目录失败: {str(e)}", is_error=True)
