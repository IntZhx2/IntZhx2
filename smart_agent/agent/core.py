"""
智能体核心控制引擎 (SmartAgent Core)
实现 ReAct (Reasoning + Acting) 认知执行循环，统筹多轮记忆、MCP 工具调用与跨端事件分发。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import json
import time
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

    @property
    def final_response(self) -> str:
        return self.answer

    @property
    def steps(self) -> List[AgentStepTrace]:
        return self.traces

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "traces": [t.to_dict() for t in self.traces],
            "memory_length": self.memory_length,
        }


class SmartAgent:
    """负责多轮对话与工具调用的旅游规划智能体"""

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

    @staticmethod
    def _validate_response(response: Any, allow_tool_calls: bool = True) -> Dict[str, Any]:
        """Reject malformed model frames before recording or executing any tool calls."""
        if not isinstance(response, dict):
            raise ValueError("Model response must be an object")
        content = response.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError("Model response content must be a string or null")
        calls = response.get("tool_calls")
        if calls is not None and not isinstance(calls, list):
            raise ValueError("Model tool_calls must be an array or null")
        if calls and not allow_tool_calls:
            raise ValueError("Model synthesis must return an answer without tool calls")
        seen_ids = set()
        for call in calls or []:
            if not isinstance(call, dict):
                raise ValueError("Each model tool call must be an object")
            call_id = call.get("id")
            function = call.get("function")
            if not isinstance(call_id, str) or not call_id or call_id in seen_ids:
                raise ValueError("Model tool call IDs must be nonempty, unique strings")
            seen_ids.add(call_id)
            if (call.get("type", "function") != "function"
                    or not isinstance(function, dict)
                    or not isinstance(function.get("name"), str) or not function["name"]):
                raise ValueError("Model tool call must specify a function name")
        return response

    def run(
        self,
        user_input: str,
        on_step: Optional[Callable[[AgentStepTrace], None]] = None,
        on_step_callback: Optional[Callable[[AgentStepTrace], None]] = None,
    ) -> AgentRunResult:
        """接收用户自然语言输入，启动 ReAct 认知规划并执行工具调用"""
        self.memory.begin_turn(user_input)
        try:
            return self._run_turn(user_input, on_step or on_step_callback)
        except BaseException:
            self.memory.rollback_turn()
            raise

    def _run_turn(
        self,
        user_input: str,
        step_callback: Optional[Callable[[AgentStepTrace], None]],
    ) -> AgentRunResult:
        traces: List[AgentStepTrace] = []

        def _emit(trace: AgentStepTrace):
            traces.append(trace)
            if step_callback:
                try:
                    step_callback(trace)
                except Exception:
                    pass

        # 1. 用户输入已由 run 写入，开始记录本轮执行耗时
        start_time = time.time()

        final_answer = ""
        current_turn = 0

        # 获取可调用的 MCP 工具 schema 列表
        tools_schema = self.mcp_client.get_llm_tools_schema()

        # 2. 启动 ReAct 认知规划循环 (Thought -> Action -> Observation -> Final Answer)
        while current_turn < self.max_turns:
            current_turn += 1
            messages = self.memory.get_messages()

            # 调用大模型/本地语义引擎做出行动决策
            response = self._validate_response(
                self.llm_client.chat_completion(messages, tools=tools_schema)
            )
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
                    except (ValueError, TypeError):
                        # Let the central MCP boundary reject malformed arguments.
                        args = raw_args
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

        # 3. 尚无最终答案时，不传 tools 参数，尝试汇总已有观察
        if not final_answer:
            synth_messages = list(self.memory.get_messages())
            failed_calls = [
                {"tool": trace.details["tool"], "call_id": trace.details["call_id"]}
                for trace in traces
                if trace.step_type == "tool_result" and trace.details.get("is_error")
            ]
            synth_messages.append({
                "role": "user",
                "content": (
                    "请依据原始出行要求和上面的实际工具观察结果汇总行程。"
                    "不能假定所有查询均已完成或成功；is_error=True 的结果不可作为已核实数据，"
                    "失败或尚未查询的信息必须标注为不可用或待核实，不得编造补齐。"
                    "本地静态资料必须注明来源性质，不得表述为实时天气、票价、预约余量或实时路况。"
                    "将到达时间和交通耗时明确写为估算，说明仍需核实的行程约束，不得保证准时到达。"
                    "在证据支持的范围内，提供早中晚时间线、景点与门票预约、交通换乘和当地美食建议，"
                    "使用清晰的 Markdown 格式；缺失的信息明确留待核实。"
                    "本轮工具失败记录（is_error=True）："
                    + json.dumps(failed_calls, ensure_ascii=False)
                ),
            })
            try:
                synth_resp = self._validate_response(
                    self.llm_client.chat_completion(synth_messages, tools=None),
                    allow_tool_calls=False,
                )
                final_answer = (synth_resp.get("content") or "").strip()
                if final_answer:
                    self.memory.add_assistant_message(final_answer)
                    _emit(AgentStepTrace(step_type="answer", content=final_answer))
            except Exception as e:
                logger.warning("强制生成攻略长文失败 (%s)", type(e).__name__)
                raise

        # 4. 模型仍未返回正文时，提供明确的失败提示
        if not final_answer:
            final_answer = "⚠️ 大模型未返回最终攻略正文，请检查网络或重新点击生成。"
            self.memory.add_assistant_message(final_answer)
            _emit(AgentStepTrace(step_type="answer", content=final_answer))

        # 5. 将本轮工具中间报文压缩为 user -> assistant 文本对，
        # 减少历史工具报文对后续模型调用的格式影响。
        self.memory.compact_last_turn(user_input, final_answer)

        elapsed_sec = time.time() - start_time
        logger.info(f"ReAct 规划循环完成，耗时 {elapsed_sec:.2f}s，产生 {len(traces)} 个轨迹步骤")

        return AgentRunResult(
            answer=final_answer,
            traces=traces,
            memory_length=len(self.memory.get_messages()),
        )
