"""DeskMate Edge 核心架构单元测试 (A-10)
支持标准库 unittest 与 pytest，保证任何纯净 Python 3.11/3.12 环境下均可直接运行
"""

import asyncio
import sys
import unittest
from pathlib import Path
from pydantic import BaseModel, Field

# 将 edge 目录加入 sys.path
edge_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(edge_root))

from deskmate_edge.platform_mock.platform_impl import MockPlatform
from deskmate_edge.protocol import WsEnvelope
from deskmate_edge.tool_registry import ToolRegistry


class DemoArgs(BaseModel):
    name: str = Field(description="名称")
    count: int = Field(default=1, ge=1, le=10, description="数量")


class TestEdgeCore(unittest.TestCase):
    """A-10 核心规范测试集"""

    def setUp(self):
        self.registry = ToolRegistry()

    def test_tool_registry_spec_generation(self):
        """测试 ToolSpec 是否合规自动生成"""
        @self.registry.register(
            name="test_tool",
            description="测试工具说明",
            args_schema=DemoArgs,
            timeout_s=5
        )
        async def sample_fn(name: str, count: int = 1):
            return {"greeting": f"Hello {name} * {count}"}

        specs = self.registry.get_all_specs()
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec["function"]["name"], "test_tool")
        self.assertIn("name", spec["function"]["parameters"]["properties"])
        self.assertIn("count", spec["function"]["parameters"]["properties"])
        self.assertIn("name", spec["function"]["parameters"]["required"])

    def test_tool_registry_execution_and_validation(self):
        """测试工具执行、入参校验与错误捕获"""
        @self.registry.register(
            name="calculate",
            description="计算工具",
            args_schema=DemoArgs,
            timeout_s=2
        )
        async def calc_fn(name: str, count: int = 1):
            return {"val": f"{name}_{count}"}

        # 1. 正常入参
        ok, data, err = asyncio.run(self.registry.dispatch("calculate", {"name": "test", "count": 3}))
        self.assertTrue(ok)
        self.assertEqual(data["val"], "test_3")
        self.assertIsNone(err)

        # 2. 越界非法入参 (count > 10)
        ok_bad, _, err_bad = asyncio.run(self.registry.dispatch("calculate", {"name": "test", "count": 99}))
        self.assertFalse(ok_bad)
        self.assertIn("BAD_ARGS", err_bad)

        # 3. 缺少必填参数
        ok_missing, _, err_missing = asyncio.run(self.registry.dispatch("calculate", {}))
        self.assertFalse(ok_missing)
        self.assertIn("BAD_ARGS", err_missing)

    def test_tool_registry_timeout_protection(self):
        """测试超时自动熔断保护"""
        @self.registry.register(
            name="slow_tool",
            description="模拟耗时工具",
            timeout_s=1
        )
        async def slow_fn():
            await asyncio.sleep(2)
            return {"done": True}

        ok, _, err = asyncio.run(self.registry.dispatch("slow_tool", {}))
        self.assertFalse(ok)
        self.assertEqual(err, "TIMEOUT")

    def test_mock_platform(self):
        """测试 Mock 平台能力完整性"""
        mock_p = MockPlatform()
        mock_p.set_dpi_awareness()
        wins = mock_p.get_open_windows()
        self.assertGreaterEqual(len(wins), 2)
        self.assertEqual(mock_p.arrange_windows("code_left_browser_right"), 2)

        # 剪贴板测试
        mock_p.write_clipboard("def test(): pass")
        self.assertEqual(mock_p.read_clipboard(), "def test(): pass")

        # 截图测试
        shot = mock_p.take_screenshot("screen")
        self.assertIn("image_b64", shot)
        self.assertEqual(shot["mime"], "image/jpeg")

    def test_ws_envelope(self):
        """测试 CONTRACTS §1 信封协议序列化与反序列化"""
        env = WsEnvelope(type="event", name="pc.session", payload={"locked": True})
        json_str = env.model_dump_json()
        self.assertIn('"v":2', json_str)
        self.assertIn('"type":"event"', json_str)
        self.assertIn('"name":"pc.session"', json_str)

        deserialized = WsEnvelope.model_validate_json(json_str)
        self.assertTrue(deserialized.payload["locked"])


if __name__ == "__main__":
    unittest.main()
