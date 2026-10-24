"""
行程方案归档与导出工具 (Itinerary Export Tool)
将智能体规划生成的高质量完整旅游攻略（包含时间线、交通接驳、美食推荐）持久化保存至工作区文档。
"""

import time
import re
import os
from pathlib import PureWindowsPath
from typing import Any, Dict
from smart_agent.config import WORKSPACE_DIR
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult


class ItinerarySaveTool(BaseTool):
    @property
    def name(self) -> str:
        return "itinerary_save"

    @property
    def description(self) -> str:
        return (
            "将确认生成的一条龙旅游攻略方案导出并保存为本地 Markdown 文档。"
            "便于用户离线保存、打印或在手机端随身查阅景程安排、交通路线与美食清单。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "攻略文档标题，如 '广州周末2日深度游攻略'",
                },
                "content": {
                    "type": "string",
                    "description": "完整的攻略正文内容（包含每日时间线、交通方式、景点门票与美食推荐）",
                },
                "filename": {
                    "type": "string",
                    "description": "纯文件名，如 'guangzhou_travel.md'（可选，留空按标题生成；拒绝路径、符号链接及覆盖已有文件）",
                },
            },
            "required": ["title", "content"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        title = kwargs.get("title", "定制旅游出行攻略")
        content = kwargs.get("content", "")
        filename = kwargs.get("filename", "")
        if not all(isinstance(value, str) for value in (title, content, filename)):
            return ToolCallResult.text("错误: title、content 与 filename 必须为字符串", is_error=True)
        title, content = title.strip(), content.strip()

        if not content:
            return ToolCallResult.text("错误: 攻略正文内容 content 不能为空", is_error=True)

        if not filename:
            # 清理标题非法字符生成文件名
            clean_title = re.sub(r'[^\w\-\u4e00-\u9fa5]', '_', title)
            timestamp = time.strftime("%Y%m%d_%H%M")
            filename = f"{clean_title}_{timestamp}.md"

        # 同时拒绝 POSIX 和 Windows 路径，不能通过后缀补全修正非法路径。
        if (filename in (".", "..") or not filename.strip()
                or any(char in filename for char in ("/", "\\", ":", "\x00"))
                or PureWindowsPath(filename).drive):
            return ToolCallResult.text("错误: filename 必须是纯文件名，不允许绝对路径或目录穿越", is_error=True)

        if not filename.endswith((".md", ".txt")):
            filename += ".md"

        target_path = WORKSPACE_DIR / filename

        try:
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            # 固定目录描述符防止目录在检查后被替换；独占创建拒绝已有文件及符号链接。
            directory_fd = os.open(WORKSPACE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                file_fd = os.open(
                    filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600, dir_fd=directory_fd,
                )
            finally:
                os.close(directory_fd)
            with os.fdopen(file_fd, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')} | 生成工具: SmartAgent 旅游规划专家\n\n")
                f.write("---\n\n")
                f.write(content)
                f.write("\n\n---\n*祝您旅途愉快，一路顺风！*\n")

            return ToolCallResult.text(
                f"✅ 行程方案已成功保存并导出为文档！\n"
                f"- 📄 文件名: `{filename}`\n"
                f"- 📂 存储路径: `{target_path}`\n"
                f"- 📊 内容体量: 约 {len(content)} 字符\n"
                f"您可随时通过网页端或工作空间直接查看完整行程。"
            )
        except FileExistsError:
            return ToolCallResult.text("错误: 文件已存在（含符号链接），请使用其他文件名；不会覆盖", is_error=True)
        except Exception as e:
            return ToolCallResult.text(f"保存攻略文件失败: {str(e)}", is_error=True)


class ItineraryListTool(BaseTool):
    @property
    def name(self) -> str:
        return "itinerary_list"

    @property
    def description(self) -> str:
        return "列出当前工作空间中已保存归档的全部历史旅游攻略与行程文档。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    def execute(self, **kwargs) -> ToolCallResult:
        try:
            files = [f for pattern in ("*.md", "*.txt") for f in WORKSPACE_DIR.glob(pattern)
                     if not f.is_symlink() and f.is_file()]
            if not files:
                return ToolCallResult.text("📂 当前工作区暂未归档任何旅游攻略文档。")

            lines = [f"📂 已归档的旅游行程方案清单 (共 {len(files)} 份):"]
            for f in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
                size_kb = f.stat().st_size / 1024
                lines.append(f"- 📄 `{f.name}` ({size_kb:.1f} KB, 更新于 {mtime})")

            return ToolCallResult.text("\n".join(lines))
        except Exception as e:
            return ToolCallResult.text(f"查询行程清单失败: {str(e)}", is_error=True)
