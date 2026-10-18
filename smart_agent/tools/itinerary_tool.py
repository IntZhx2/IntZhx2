"""
行程方案归档与导出工具 (Itinerary Export Tool)
将智能体规划生成的高质量完整旅游攻略（包含时间线、交通接驳、美食推荐）持久化保存至工作区文档。
"""

import time
import re
from pathlib import Path
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
                    "description": "保存的文件名，如 'guangzhou_travel.md'（可选，留空将自动根据标题生成）",
                },
            },
            "required": ["title", "content"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        title = kwargs.get("title", "定制旅游出行攻略").strip()
        content = kwargs.get("content", "").strip()
        filename = kwargs.get("filename", "").strip()

        if not content:
            return ToolCallResult.text("错误: 攻略正文内容 content 不能为空", is_error=True)

        if not filename:
            # 清理标题非法字符生成文件名
            clean_title = re.sub(r'[^\w\-\u4e00-\u9fa5]', '_', title)
            timestamp = time.strftime("%Y%m%d_%H%M")
            filename = f"{clean_title}_{timestamp}.md"

        if not filename.endswith((".md", ".txt")):
            filename += ".md"

        target_path = WORKSPACE_DIR / filename

        try:
            WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
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
            files = list(WORKSPACE_DIR.glob("*.md")) + list(WORKSPACE_DIR.glob("*.txt"))
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
