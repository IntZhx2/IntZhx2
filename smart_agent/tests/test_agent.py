"""
智能体 ReAct 认知规划与多轮会话记忆测试
"""

import unittest
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.agent.core import SmartAgent
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.tools import create_default_tools
from smart_agent.tools.todo_tool import _db_manager


class TestAgentCoreAndMemory(unittest.TestCase):
    def setUp(self):
        # 清理数据库
        with _db_manager.get_connection() as conn:
            conn.execute("DELETE FROM todos")
            conn.commit()

        self.server = MCPServer(name="TestAgentServer")
        for tool in create_default_tools():
            self.server.register_tool(tool)

        self.client = MCPClient(self.server)
        self.llm = LLMClient()
        self.memory = ConversationMemory(session_id="unit_test_session", window_size=4)
        self.agent = SmartAgent(
            memory=self.memory,
            mcp_client=self.client,
            llm_client=self.llm,
        )

    def test_memory_sliding_window(self):
        # 初始应包含系统提示词
        msgs = self.memory.get_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["role"], "system")

        # 连续添加 6 条消息（超过 window_size=4）
        for i in range(6):
            self.memory.add_user_message(f"message_{i}")

        msgs_after = self.memory.get_messages()
        # 系统提示词保留 (1) + 最近 window_size 条 (4) = 5
        self.assertEqual(len(msgs_after), 5)
        self.assertEqual(msgs_after[0]["role"], "system")
        self.assertEqual(msgs_after[-1]["content"], "message_5")

    def test_react_tool_execution_flow(self):
        # 测试智能体接收自然语言指令并自主驱动 MCP 工具完成待办添加
        result = self.agent.run("帮我添加一条重要待办：复习软件工程，优先级高")

        # 验证产生了完整的思考轨迹、工具调用和观察
        trace_types = [t.step_type for t in result.traces]
        self.assertIn("tool_call", trace_types)
        self.assertIn("tool_result", trace_types)
        self.assertIn("answer", trace_types)

        # 验证数据库中确实写入了该条记录
        with _db_manager.get_connection() as conn:
            rows = conn.execute("SELECT * FROM todos WHERE title LIKE '%复习软件工程%'").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["priority"], "high")

    def test_multi_turn_continuity(self):
        # 第一轮对话：自我介绍
        res1 = self.agent.run("你好，请介绍一下你自己")
        self.assertIn("SmartAgent", res1.answer)

        # 第二轮对话：问及上下文
        res2 = self.agent.run("你还记得我们刚才聊了什么吗？")
        self.assertIn("对话上下文", res2.answer)


if __name__ == "__main__":
    unittest.main()
