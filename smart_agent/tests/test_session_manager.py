"""
智能体会话历史与多轮接续管理单元测试 (Session Manager Tests)
"""

import unittest
from pathlib import Path
from smart_agent.agent.session_manager import SessionManager
from smart_agent.config import SESSIONS_DIR


class TestSessionManager(unittest.TestCase):
    def setUp(self):
        self.created_sessions = []
        # 清理测试会话文件
        for f in SESSIONS_DIR.glob("sess_test_*.json"):
            try:
                f.unlink()
            except Exception:
                pass

    def tearDown(self):
        for sid in self.created_sessions:
            SessionManager.delete_session(sid)
        for f in SESSIONS_DIR.glob("sess_test_*.json"):
            try:
                f.unlink()
            except Exception:
                pass

    def test_session_lifecycle(self):
        # 1. 创建新会话
        sess = SessionManager.create_new_session("测试广州2日游规划")
        sess_id = sess["session_id"]
        self.created_sessions.append(sess_id)
        self.assertTrue(sess_id.startswith("sess_"))
        self.assertEqual(sess["title"], "测试广州2日游规划")

        # 2. 追加第一轮交互
        user_p = "我想周六去广州塔，下午3点必须到"
        agent_r = "## 广州塔登塔行程\n建议14:30到达广州塔西门"
        step_traces = [{"step": 1, "action": "weather_query", "observation": "晴朗 25℃"}]
        llm_msgs = [{"role": "user", "content": user_p}, {"role": "assistant", "content": agent_r}]

        updated = SessionManager.append_turn(
            session_id=sess_id,
            user_prompt=user_p,
            assistant_response=agent_r,
            step_traces=step_traces,
            llm_messages=llm_msgs,
        )
        self.assertEqual(len(updated["turns"]), 1)
        self.assertEqual(updated["turns"][0]["user_prompt"], user_p)

        # 3. 读取会话
        fetched = SessionManager.get_session(sess_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(len(fetched["turns"]), 1)

        # 4. 导出 Markdown
        md = SessionManager.export_markdown(sess_id)
        self.assertIn("广州塔", md)
        self.assertIn("weather_query", md)
        self.assertIn("第 1 轮对话", md)

        # 5. 列表包含该会话
        s_list = SessionManager.list_sessions()
        ids = [s["session_id"] for s in s_list]
        self.assertIn(sess_id, ids)

        # 6. 删除会话
        self.assertTrue(SessionManager.delete_session(sess_id))
        self.assertIsNone(SessionManager.get_session(sess_id))

    def test_session_not_found_safety(self):
        # 验证读取与删除不存在的会话时能够安全容错，不抛出崩溃异常
        self.assertIsNone(SessionManager.get_session("sess_non_existent_12345"))
        self.assertFalse(SessionManager.delete_session("sess_non_existent_12345"))
        self.assertIn("未找到", SessionManager.export_markdown("sess_non_existent_12345"))

    def test_session_multiple_turns_accumulation(self):
        sess = SessionManager.create_new_session("深圳三天双人游")
        sess_id = sess["session_id"]
        self.created_sessions.append(sess_id)

        # 追加第 1 轮
        SessionManager.append_turn(
            session_id=sess_id,
            user_prompt="第一天想去大梅沙看海",
            assistant_response="建议早晨从市区搭乘地铁8号线直达大梅沙站...",
            step_traces=[],
            llm_messages=[],
        )

        # 追加第 2 轮
        SessionManager.append_turn(
            session_id=sess_id,
            user_prompt="第二天下午改去华侨城创意园",
            assistant_response="已为您更新第二天行程：下午前往OCT-LOFT创意文化园...",
            step_traces=[],
            llm_messages=[],
        )

        fetched = SessionManager.get_session(sess_id)
        self.assertEqual(len(fetched["turns"]), 2)
        self.assertEqual(fetched["title"], "深圳三天双人游")
        self.assertEqual(fetched["turns"][0]["turn_id"], 1)
        self.assertEqual(fetched["turns"][1]["turn_id"], 2)

        md = SessionManager.export_markdown(sess_id)
        self.assertIn("第 1 轮对话", md)
        self.assertIn("第 2 轮对话", md)
        self.assertIn("大梅沙", md)
        self.assertIn("华侨城创意园", md)

        SessionManager.delete_session(sess_id)


if __name__ == "__main__":
    unittest.main()
