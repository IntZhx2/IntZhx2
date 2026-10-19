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
        on_step: Optional[Callable[[AgentStepTrace], None]] = None,
        on_step_callback: Optional[Callable[[AgentStepTrace], None]] = None,
    ) -> AgentRunResult:
        """接收用户自然语言输入，启动 ReAct 认知规划并执行工具调用"""
        traces: List[AgentStepTrace] = []
        step_callback = on_step or on_step_callback

        def _emit(trace: AgentStepTrace):
            traces.append(trace)
            if step_callback:
                try:
                    step_callback(trace)
                except Exception:
                    pass

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
            assistant_content = (response.get("content") or "").strip()

            # 情况 A: 模型未发起工具调用
            if not tool_calls:
                if assistant_content:
                    final_answer = assistant_content
                    self.memory.add_assistant_message(final_answer)
                    _emit(AgentStepTrace(step_type="answer", content=final_answer))
                    break
                else:
                    # 模型返回空文本且无工具调用，退出循环以进入无 tools 强行正文汇总阶段
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

        # 3. 终结汇总保障：若 final_answer 仍为空，剥离 tools 参数强制要求大模型汇总生成完整长文
        if not final_answer:
            synth_messages = list(self.memory.get_messages())
            synth_messages.append({
                "role": "user",
                "content": (
                    "现在所有相关气象、景点门票预约和交通路线工具已调用完毕。"
                    "请根据上面所有工具获得的真实数据，严格满足我的出行偏好与时间约束，"
                    "为我撰写包含【早中晚完整时间线、景点核心亮点与门票预约、具体地铁/打车换乘耗时、周边地道老字号美食必吃菜品】"
                    "的一条龙深度定制旅游攻略。请使用优雅的 Markdown 格式输出（包含表格与各级标题）。"
                ),
            })
            try:
                synth_resp = self.llm_client.chat_completion(synth_messages, tools=None)
                final_answer = (synth_resp.get("content") or "").strip()
                if final_answer:
                    self.memory.add_assistant_message(final_answer)
                    _emit(AgentStepTrace(step_type="answer", content=final_answer))
            except Exception as e:
                logger.error(f"强制生成攻略长文失败: {e}")
                raise

        # 4. 彻底杜绝敷衍模板
        if not final_answer:
            final_answer = "⚠️ 大模型未返回最终攻略正文，请检查网络或重新点击生成。"
            self.memory.add_assistant_message(final_answer)
            _emit(AgentStepTrace(step_type="answer", content=final_answer))

        return AgentRunResult(
            answer=final_answer,
            traces=traces,
            memory_length=len(self.memory.get_messages()),
        )
