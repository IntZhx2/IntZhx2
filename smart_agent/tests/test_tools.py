"""
旅游专属 MCP 工具集单元测试 (Weather, Traffic, Attraction, Itinerary)
"""

import unittest
from pathlib import Path
from smart_agent.tools.weather_tool import WeatherQueryTool
from smart_agent.tools.traffic_tool import TrafficTransitTool
from smart_agent.tools.attraction_tool import AttractionInfoTool
from smart_agent.tools.itinerary_tool import ItinerarySaveTool, ItineraryListTool
from smart_agent.config import WORKSPACE_DIR


class TestTravelToolsSuite(unittest.TestCase):
    def setUp(self):
        # 清空测试保存文件
        for f in WORKSPACE_DIR.glob("test_travel_*.md"):
            try:
                f.unlink()
            except Exception:
                pass

    def test_weather_query_tool(self):
        tool = WeatherQueryTool()
        res = tool.execute(city="广州")
        self.assertFalse(res.is_error)
        text = res.get_text()
        self.assertIn("广州", text)
        self.assertIn("气温", text)
        self.assertIn("穿搭", text)

    def test_traffic_transit_tool(self):
        tool = TrafficTransitTool()
        # 测试带起终点与地铁方式
        res = tool.execute(city="广州", origin="广州南站", destination="广州塔", transit_mode="metro_bus")
        self.assertFalse(res.is_error)
        text = res.get_text()
        self.assertIn("广州南站", text)
        self.assertIn("广州塔", text)
        self.assertIn("地铁", text)
        self.assertIn("预估耗时", text)

        # 缺少参数异常
        err_res = tool.execute(city="广州", origin="")
        self.assertTrue(err_res.is_error)

    def test_attraction_info_tool(self):
        tool = AttractionInfoTool()
        # 广州塔
        r1 = tool.execute(city="广州", attraction_name="广州塔")
        self.assertFalse(r1.is_error)
        t1 = r1.get_text()
        self.assertIn("广州塔", t1)
        self.assertIn("门票与预约", t1)
        self.assertIn("周边招牌美食", t1)

        # 永庆坊
        r2 = tool.execute(city="广州", attraction_name="永庆坊")
        self.assertFalse(r2.is_error)
        self.assertIn("西关老字号", r2.get_text())

    def test_itinerary_save_and_list_tool(self):
        save_tool = ItinerarySaveTool()
        list_tool = ItineraryListTool()

        title = "测试广州2日游一条龙攻略"
        content = "## Day 1: 西关老街与广州塔登塔\n- 15:00 必须到广州塔\n- 晚上品尝炳胜粤菜"
        filename = "test_travel_gz.md"

        # 1. 保存
        save_res = save_tool.execute(title=title, content=content, filename=filename)
        self.assertFalse(save_res.is_error)
        self.assertIn("成功保存并导出", save_res.get_text())

        # 验证文件已存在
        target = WORKSPACE_DIR / filename
        self.assertTrue(target.exists())
        with open(target, "r", encoding="utf-8") as f:
            data = f.read()
        self.assertIn("测试广州2日游一条龙攻略", data)
        self.assertIn("15:00 必须到广州塔", data)

        # 2. 列出清单
        list_res = list_tool.execute()
        self.assertFalse(list_res.is_error)
        self.assertIn(filename, list_res.get_text())


if __name__ == "__main__":
    unittest.main()
