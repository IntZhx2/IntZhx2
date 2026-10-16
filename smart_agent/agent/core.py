"""
智能体核心控制引擎 (SmartAgent Core)
实现 ReAct (Reasoning + Acting) 认知执行循环，统筹多轮记忆、MCP 工具调用与跨端事件分发。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import json
import logging
from smart_agent.config import MAX_REACT_TURNS
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.mcp.client import MCPClient

logger = logging.getLogger("agent.core")


@dataclass
class AgentStepTrace:
    """ReAct 规划轨迹单步记录"""
    step_type: str  # thought, tool_call, tool_result, answer
    content: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"type": self.step_type, "content": self.content}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class AgentRunResult:
    """智能体执行完整结果"""
    answer: str
    traces: List[AgentStepTrace]
    memory_length: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "traces": [t.to_dict() for t in self.traces],
            "memory_length": self.memory_length,
        }


class SmartAgent:
    """具备能说会做特性的全功能智能体"""

    def __init__(
        self,
        memory: ConversationMemory,
        mcp_client: MCPClient,
        llm_client: LLMClient,
        max_turns: int = MAX_REACT_TURNS,
    ):
        self.memory = memory
        self.mcp_client = mcp_client
        self.llm_client = llm_client
        self.max_turns = max_turns

    def run(
        self,
        user_input: str,
        on_step_callback: Optional[Callable[[AgentStepTrace], None]] = None,
    ) -> AgentRunResult:
        """接收用户自然语言输入，启动 ReAct 认知规划并执行工具调用"""
        traces: List[AgentStepTrace] = []

        def _emit(trace: AgentStepTrace):
            traces.append(trace)
            if on_step_callback:
                on_step_callback(trace)

        # 1. 记录用户输入至记忆
        self.memory.add_user_message(user_input)

        final_answer = ""
        current_turn = 0

        # 获取可调用的 MCP 工具 schema 列表
        tools_schema = self.mcp_client.get_llm_tools_schema()

        # 2. 启动 ReAct 认知规划循环 (Thought -> Action -> Observation -> Final Answer)
        while current_turn < self.max_turns:
            current_turn += 1
            messages = self.memory.get_messages()

            # 调用大模型/本地语义引擎做出行动决策
            response = self.llm_client.chat_completion(messages, tools=tools_schema)
            tool_calls = response.get("tool_calls")
            assistant_content = response.get("content") or ""

            # 情况 A: 模型未发起工具调用，直接输出最终语言答复
            if not tool_calls:
                final_answer = assistant_content
                self.memory.add_assistant_message(final_answer)
                _emit(AgentStepTrace(step_type="answer", content=final_answer))
                break

            # 情况 B: 模型产生思考并规划调用 MCP 工具
            if assistant_content:
                _emit(AgentStepTrace(step_type="thought", content=assistant_content))

            # 将 assistant 包含 tool_calls 的消息加入记忆上下文
            self.memory.add_assistant_message(assistant_content, tool_calls=tool_calls)

            # 遍历并执行每个工具调用 (Action -> Observation)
            for tc in tool_calls:
                func_info = tc.get("function", {})
                tool_name = func_info.get("name", "")
                tool_id = tc.get("id", f"call_{current_turn}")

                raw_args = func_info.get("arguments", "{}")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {}
                else:
                    args = raw_args

                # 记录 Action 轨迹
                _emit(AgentStepTrace(
                    step_type="tool_call",
                    content=f"调用工具: {tool_name}",
                    details={"tool": tool_name, "arguments": args, "call_id": tool_id},
                ))

                # 真实调用 MCP 服务端执行操作
                result = self.mcp_client.call_tool(tool_name, args)
                res_text = result.get_text()

                # 记录 Observation 结果轨迹
                _emit(AgentStepTrace(
                    step_type="tool_result",
                    content=res_text,
                    details={"tool": tool_name, "is_error": result.is_error, "call_id": tool_id},
                ))

                # 将工具执行结果作为 tool 角色消息写入对话记忆
                self.memory.add_tool_message(tool_call_id=tool_id, name=tool_name, content=res_text)

        # 兜底：如果到达最大轮次仍未完成，给用户一个友好说明
        if not final_answer:
            final_answer = "我已经为您执行了相关操作，以上是工具处理的最新结果。"
            self.memory.add_assistant_message(final_answer)
            _emit(AgentStepTrace(step_type="answer", content=final_answer))

        return AgentRunResult(
            answer=final_answer,
            traces=traces,
            memory_length=len(self.memory.get_messages()),
        )
