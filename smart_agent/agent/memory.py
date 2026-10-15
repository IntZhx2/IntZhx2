"""
智能体多轮对话记忆管理模块 (Conversation Memory)
负责管理上下文生命周期、滑动窗口衰减预算、角色消息封装以及跨会话持久化。
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import json
import time
from pathlib import Path
from smart_agent.config import DATA_DIR, MEMORY_WINDOW_SIZE, SYSTEM_PROMPT


@dataclass
class Message:
    """标准聊天消息对象"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


class ConversationMemory:
    """多轮对话记忆管理器"""

    def __init__(
        self,
        session_id: str = "default",
        system_prompt: str = SYSTEM_PROMPT,
        window_size: int = MEMORY_WINDOW_SIZE,
    ):
        self.session_id = session_id
        self.system_prompt = system_prompt
        self.window_size = window_size
        self._messages: List[Message] = []
        self._init_system_prompt()

    def _init_system_prompt(self):
        if not self._messages:
            self._messages.append(Message(role="system", content=self.system_prompt))

    def add_user_message(self, content: str) -> Message:
        msg = Message(role="user", content=content)
        self._messages.append(msg)
        self._trim_window()
        return msg

    def add_assistant_message(
        self, content: str, tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> Message:
        msg = Message(role="assistant", content=content, tool_calls=tool_calls)
        self._messages.append(msg)
        self._trim_window()
        return msg

    def add_tool_message(self, tool_call_id: str, name: str, content: str) -> Message:
        msg = Message(role="tool", content=content, tool_call_id=tool_call_id, name=name)
        self._messages.append(msg)
        self._trim_window()
        return msg

    def get_messages(self) -> List[Dict[str, Any]]:
        """获取用于大模型 API 调用的消息字典列表"""
        return [m.to_dict() for m in self._messages]

    def get_history_summary(self) -> List[Dict[str, Any]]:
        """获取对前端友好的展示型历史"""
        display_history = []
        for m in self._messages:
            if m.role == "system":
                continue
            display_history.append({
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "name": m.name,
                "time": time.strftime("%H:%M:%S", time.localtime(m.timestamp)),
            })
        return display_history

    def _trim_window(self):
        """保持滑动窗口预算，保留系统提示词，修剪最旧的历史记录"""
        if len(self._messages) <= self.window_size + 1:
            return

        sys_msg = self._messages[0]
        # 保留最近 window_size 条记录
        recent = self._messages[-self.window_size:]
        self._messages = [sys_msg] + recent

    def clear(self):
        """清空当前会话历史"""
        self._messages = []
        self._init_system_prompt()

    def save_to_file(self, filepath: Optional[Path] = None):
        """将会话持久化到磁盘"""
        target = filepath or (DATA_DIR / f"session_{self.session_id}.json")
        data = [asdict(m) for m in self._messages]
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self, filepath: Optional[Path] = None):
        """从磁盘恢复会话"""
        target = filepath or (DATA_DIR / f"session_{self.session_id}.json")
        if not target.exists():
            return
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._messages = [Message(**item) for item in data]
        except Exception:
            self.clear()
