"""
智能体会话历史与多轮接续管理模块 (Session Manager)
提供会话自动持久化、多轮记忆恢复接续、历史会话归档管理及 Markdown 导出下载功能。
"""

import json
import time
import uuid
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from smart_agent.config import SESSIONS_DIR


class SessionManager:
    """会话生命周期管理"""

    @staticmethod
    def _get_session_path(session_id: str) -> Path:
        # 移除非法文件名字符
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "", session_id)
        return SESSIONS_DIR / f"{safe_id}.json"

    @classmethod
    def list_sessions(cls) -> List[Dict[str, Any]]:
        """列出所有历史会话，按最近更新时间倒序排序"""
        sessions = []
        for file in SESSIONS_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                turns = data.get("turns", [])
                if not turns:
                    continue  # 忽略尚未包含任何交互轮次的空会话
                sessions.append({
                    "session_id": data.get("session_id", file.stem),
                    "title": data.get("title", "未命名对话"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "turn_count": len(turns),
                    "preview": data.get("preview", ""),
                })
            except Exception:
                continue

        # 按 updated_at 倒序排列
        sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
        return sessions

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """获取单个会话的全部历史与消息"""
        path = cls._get_session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def create_new_session(cls, title: str = "新旅游行程规划") -> Dict[str, Any]:
        """初始化一个全新的会话"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        sess_id = f"sess_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"
        session_data = {
            "session_id": sess_id,
            "title": title,
            "created_at": now_str,
            "updated_at": now_str,
            "preview": "",
            "turns": [],
            "llm_messages": [],
        }
        cls.save_session(session_data)
        return session_data

    @classmethod
    def save_session(cls, session_data: Dict[str, Any]):
        """持久化会话数据到文件"""
        sess_id = session_data.get("session_id")
        if not sess_id:
            return
        path = cls._get_session_path(sess_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

    @classmethod
    def append_turn(
        cls,
        session_id: str,
        user_prompt: str,
        assistant_response: str,
        step_traces: List[Dict[str, Any]],
        llm_messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """将一轮完整的多轮交互（用户提问、工具调用链路、大模型响应）写入会话"""
        session = cls.get_session(session_id)
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        if not session:
            # 自动生成有意义的简明标题
            title = cls._generate_smart_title(user_prompt)
            session = {
                "session_id": session_id,
                "title": title,
                "created_at": now_str,
                "updated_at": now_str,
                "preview": user_prompt[:60],
                "turns": [],
                "llm_messages": [],
            }
        else:
            # 如果当前还是默认未命名标题，更新为根据首轮需求智能提炼的标题
            if session.get("title") in ("", "新旅游行程规划", "未命名对话"):
                session["title"] = cls._generate_smart_title(user_prompt)

        session["updated_at"] = now_str
        session["preview"] = user_prompt[:60]
        session["llm_messages"] = llm_messages

        session["turns"].append({
            "turn_id": len(session.get("turns", [])) + 1,
            "timestamp": now_str,
            "user_prompt": user_prompt,
            "step_traces": step_traces,
            "assistant_response": assistant_response,
        })

        cls.save_session(session)
        return session

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        """删除会话文件"""
        path = cls._get_session_path(session_id)
        if path.exists():
            try:
                path.unlink()
                return True
            except Exception:
                return False
        return False

    @classmethod
    def export_markdown(cls, session_id: str) -> str:
        """将会话完整记录渲染为漂亮的 Markdown 文档，供用户一键下载保存"""
        session = cls.get_session(session_id)
        if not session:
            return "# 对话记录未找到\n"

        title = session.get("title", "旅游规划会话记录")
        created_at = session.get("created_at", "")
        updated_at = session.get("updated_at", "")
        turns = session.get("turns", [])

        md = [
            f"# 🎒 {title}",
            f"> 📅 会话创建: `{created_at}` | 最近更新: `{updated_at}` | 交互轮次: `{len(turns)}` 轮",
            f"> 🤖 旅行规划助手: **TravelAgent**",
            "\n---\n",
        ]

        for turn in turns:
            tid = turn.get("turn_id", 1)
            t_time = turn.get("timestamp", "")
            user_text = turn.get("user_prompt", "")
            traces = turn.get("step_traces", [])
            reply = turn.get("assistant_response", "")

            md.append(f"## 💬 第 {tid} 轮对话 ({t_time})")
            md.append(f"**用户需求:**\n\n> {user_text}\n")

            if traces:
                md.append("#### 🛠️ MCP 真实工具调用链记录:")
                step_idx = 1
                for step in traces:
                    stype = step.get("type") or step.get("step_type", "")
                    content = step.get("content", "")
                    details = step.get("details", {}) or {}
                    action = step.get("action", "")

                    if stype == "thought":
                        md.append(f"- **🧠 规划思考**: {content}")
                    elif stype == "tool_call" or (action and not stype):
                        tool_name = details.get("tool") or action or content
                        args_str = json.dumps(details.get("arguments", {}), ensure_ascii=False) if details.get("arguments") else ""
                        md.append(f"- **🔧 执行工具 #{step_idx}** (`{tool_name}`){': ' + args_str if args_str else ''}")
                        step_idx += 1
                    elif stype == "tool_result" or step.get("observation"):
                        tool_name = details.get("tool", "")
                        obs = content or step.get("observation", "")
                        is_err = details.get("is_error", False) or step.get("is_error", False)
                        status_str = "❌ 异常" if is_err else "✅ 成功"
                        md.append(f"  - **数据反馈 [{tool_name or 'MCP'} {status_str}]**:")
                        obs_indented = "\n    ".join(obs.strip().split("\n"))
                        md.append(f"    ```text\n    {obs_indented}\n    ```")
                md.append("")

            md.append("#### 🤖 TravelAgent 深度规划攻略与回复:")
            md.append(f"\n{reply}\n")
            md.append("\n---\n")

        return "\n".join(md)

    @classmethod
    def _generate_smart_title(cls, prompt: str) -> str:
        """从用户初始输入中提取精简标题"""
        p = prompt.strip()
        # 寻找诸如“从X到Y”或者“城市X天游”等特征
        match = re.search(r"从\s*([^\s,，。至到]+)\s*(?:至|到)\s*([^\s,，。]+)", p)
        if match:
            return f"{match.group(1)} ➔ {match.group(2)} 旅游规划"

        match_city = re.search(r"([^\s,，。]{2,6}市|[^\s,，。]{2,4})\s*(\d+天[^\s,，。]*|一日游|两条路线|旅游|攻略)", p)
        if match_city:
            return f"{match_city.group(1)} {match_city.group(2)}"

        # 默认前 18 个字符
        clean = re.sub(r"[\r\n]+", " ", p)
        return clean[:18] + ("..." if len(clean) > 18 else "")
