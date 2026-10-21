"""
旅游规划智能体 ReAct 认知规划与强制 API Key 验证测试
"""

import unittest
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.agent.core import SmartAgent
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.tools import create_default_tools


class MockOnlineLLMClient(LLMClient):
    """用于测试 ReAct 循环调度的模拟在线 LLM 客户端"""
    def __init__(self):
        super().__init__(api_key="sk-mock-valid-test-key-123456")
        self.call_count = 0

    def chat_completion(self, messages, tools=None):
        self.call_count += 1
        last_msg = messages[-1]

        # 第一次交互：大模型决定调用 weather_query 工具
        if self.call_count == 1:
            return {
                "role": "assistant",
                "content": "正在为您查询目的地的气象与交通指数...",
                "tool_calls": [
                    {
                        "id": "call_mock_1",
                        "type": "function",
                        "function": {
                            "name": "weather_query",
                            "arguments": '{"city": "广州"}',
                        },
                    }
                ],
            }

        # 第二次交互（观察到工具结果后）：给出结合约束的一条龙旅游攻略
        return {
            "role": "assistant",
            "content": "已结合广州最新气象与您下午3点登广州塔的要求，为您生成包含景点、地铁换乘和早茶美食的完整一条龙攻略！",
            "tool_calls": None,
        }


class TestTravelAgentCore(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer(name="TestTravelServer")
        for tool in create_default_tools():
            self.server.register_tool(tool)
        self.client = MCPClient(self.server)

    def test_mandatory_api_key_enforcement(self):
        # 未配置 API Key 时必须抛出友好异常拒绝伪离线
        no_key_client = LLMClient(api_key="")
        memory = ConversationMemory(session_id="test_no_key")
        agent = SmartAgent(memory=memory, mcp_client=self.client, llm_client=no_key_client)

        with self.assertRaises(RuntimeError) as cm:
            agent.run("帮我规划广州2日游")
        self.assertIn("未配置大模型 API Key", str(cm.exception))

    def test_memory_sliding_window(self):
        memory = ConversationMemory(session_id="test_window", window_size=4)
        # 初始系统提示词 (1)
        self.assertEqual(len(memory.get_messages()), 1)
        self.assertEqual(memory.get_messages()[0]["role"], "system")

        for i in range(6):
            memory.add_user_message(f"user_msg_{i}")

        # 系统词(1) + 最近4条 = 5
        msgs = memory.get_messages()
        self.assertEqual(len(msgs), 5)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[-1]["content"], "user_msg_5")

    def test_react_travel_tool_loop(self):
        mock_llm = MockOnlineLLMClient()
        memory = ConversationMemory(session_id="test_react_loop")
        agent = SmartAgent(memory=memory, mcp_client=self.client, llm_client=mock_llm)

        # 触发带特定时间约束的旅游需求
        result = agent.run("广州2日游，周六下午3点必须到广州塔，坐地铁")

        # 验证产生了完整的思考、工具调度与最终回答
        trace_types = [t.step_type for t in result.traces]
        self.assertIn("tool_call", trace_types)
        self.assertIn("tool_result", trace_types)
        self.assertIn("answer", trace_types)
        self.assertIn("广州塔", result.answer)


    def test_memory_load_from_turns(self):
        memory = ConversationMemory(session_id="test_load_turns")
        turns = [
            {"user_prompt": "你好，想去北京玩", "assistant_response": "北京欢迎你，推荐故宫和颐和园。"},
            {"user_prompt": "第二天怎么去长城？", "assistant_response": "可从北京北站乘坐S2线直达八达岭。"}
        ]
        memory.load_from_turns(turns)
        msgs = memory.get_messages()
        # 系统提示词(1) + 2轮*(user+assistant) = 5
        self.assertEqual(len(msgs), 5)
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")
        self.assertEqual(msgs[1]["content"], "你好，想去北京玩")
        self.assertEqual(msgs[2]["role"], "assistant")
        self.assertEqual(msgs[3]["role"], "user")
        self.assertEqual(msgs[4]["role"], "assistant")

    def test_memory_compact_last_turn(self):
        memory = ConversationMemory(session_id="test_compact")
        memory.add_user_message("广州天气如何？")
        memory.add_assistant_message("正在查询...", tool_calls=[{"id": "call_1", "type": "function"}])
        memory.add_tool_message("call_1", "weather_query", "晴朗 28℃")
        memory.compact_last_turn("广州天气如何？", "今日广州天气晴朗，气温28℃，适合户外出行。")

        msgs = memory.get_messages()
        # 验证中间的 tool / tool_calls 被彻底压缩，只保留最终的 assistant 答案
        self.assertEqual(len(msgs), 3) # system + user + assistant
        self.assertEqual(msgs[1]["role"], "user")
        self.assertEqual(msgs[2]["role"], "assistant")
        self.assertEqual(msgs[2]["content"], "今日广州天气晴朗，气温28℃，适合户外出行。")
        self.assertNotIn("tool_calls", msgs[2])

    def test_memory_first_message_after_system_is_user(self):
        memory = ConversationMemory(session_id="test_leading_user", window_size=3)
        # 添加多条消息
        memory.add_user_message("1")
        memory.add_assistant_message("2")
        memory.add_user_message("3")
        memory.add_assistant_message("4")
        memory.add_user_message("5")

        msgs = memory.get_messages()
        # 首条必须为 system，紧随其后的首条上下文消息必须是 user
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
