"""
智能体多轮对话记忆管理模块 (Conversation Memory)
负责管理上下文生命周期、滑动窗口衰减预算、角色消息封装以及跨会话持久化。
"""

from dataclasses import dataclass, field, asdict
from copy import deepcopy
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
        self._turn_snapshot: Optional[List[Message]] = None
        self._init_system_prompt()

    def begin_turn(self, user_input: str):
        """Pin the active turn, retaining an exact snapshot for failed-run rollback."""
        if self._turn_snapshot is not None:
            raise RuntimeError("A conversation turn is already active")
        self._turn_snapshot = deepcopy(self._messages)
        self.add_user_message(user_input)

    def rollback_turn(self):
        """Undo memory changes only; tools may already have had external effects."""
        if self._turn_snapshot is not None:
            self._messages = self._turn_snapshot
            self._turn_snapshot = None

    def _init_system_prompt(self):
        if not self._messages:
            self._messages.append(Message(role="system", content=self.system_prompt))

    def add_user_message(self, content: str) -> Message:
        msg = Message(role="user", content=content)
        self._messages.append(msg)
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
        """Trim whole historical turns only after an answer; the newest turn may exceed budget."""
        if self._turn_snapshot is not None or not self._messages:
            return
        last = self._messages[-1]
        if last.role != "assistant" or last.tool_calls:
            return
        starts = [i for i, msg in enumerate(self._messages) if msg.role == "user"]
        # Each boundary includes every assistant tool call and all its results.
        while len(starts) > 1 and len(self._messages) - 1 > self.window_size:
            next_start = starts[1]
            self._messages = self._messages[:1] + self._messages[next_start:]
            starts = [i for i, msg in enumerate(self._messages) if msg.role == "user"]

    def compact_last_turn(self, user_input: str, assistant_response: str):
        """Compact only the completed active turn, then evict whole older turns."""
        last_user = next((i for i in range(len(self._messages) - 1, 0, -1)
                          if self._messages[i].role == "user"), None)
        if last_user is None:
            self._messages.append(Message(role="user", content=user_input))
        else:
            self._messages = self._messages[:last_user + 1]
        self._messages.append(Message(role="assistant", content=assistant_response))
        self._turn_snapshot = None
        self._trim_window()

    def clear(self):
        """清空当前会话历史"""
        self._messages = []
        self._turn_snapshot = None
        self._init_system_prompt()

    def load_from_turns(self, turns: List[Dict[str, Any]]):
        """从历史轮次恢复 user/assistant 文本上下文，不包含工具调用报文。"""
        self.clear()
        if not turns:
            return
        for turn in turns:
            u_prompt = (turn.get("user_prompt") or "").strip()
            a_resp = (turn.get("assistant_response") or "").strip()
            if u_prompt:
                self._messages.append(Message(role="user", content=u_prompt))
            if a_resp:
                self._messages.append(Message(role="assistant", content=a_resp))
        self._trim_window()

    def load_from_messages(self, messages_data: List[Dict[str, Any]]):
        """直接从字典列表恢复内存消息"""
        if not messages_data:
            self.clear()
            return
        self._messages = []
        for item in messages_data:
            self._messages.append(Message(
                role=item.get("role", "user"),
                content=item.get("content", ""),
                tool_calls=item.get("tool_calls"),
                tool_call_id=item.get("tool_call_id"),
                name=item.get("name"),
                timestamp=item.get("timestamp", time.time()),
            ))
        if not any(m.role == "system" for m in self._messages):
            self._messages.insert(0, Message(role="system", content=self.system_prompt))
        self._trim_window()

    def export_messages(self) -> List[Dict[str, Any]]:
        """导出当前内存消息列表字典"""
        return [asdict(m) for m in self._messages]

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
