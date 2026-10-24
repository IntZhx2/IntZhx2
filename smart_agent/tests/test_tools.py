"""
旅游专属 MCP 工具集单元测试 (Weather, Traffic, Attraction, Itinerary)
"""

import unittest
import tempfile
from unittest import mock
from pathlib import Path
from smart_agent.tools.weather_tool import WeatherQueryTool
from smart_agent.tools.traffic_tool import TrafficTransitTool
from smart_agent.tools.attraction_tool import AttractionInfoTool
from smart_agent.tools.itinerary_tool import ItinerarySaveTool, ItineraryListTool


class TestTravelToolsSuite(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        for patcher in (
            mock.patch("smart_agent.tools.itinerary_tool.WORKSPACE_DIR", self.workspace),
            mock.patch("smart_agent.tools.baidu_map.get_baidu_ak", return_value=""),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("外部请求必须使用 mock")),
            mock.patch("smart_agent.tools.baidu_map.BaiduMapClient._request",
                       side_effect=AssertionError("地图请求必须使用 mock")),
        ):
            patched = patcher.start()
            self.addCleanup(patcher.stop)
            # 即使被工具的错误处理捕获，也必须让未隔离的外部调用导致测试失败。
            if patcher.attribute in ("urlopen", "_request"):
                self.addCleanup(patched.assert_not_called)

    def test_weather_query_tool(self):
        tool = WeatherQueryTool()
        # 1. 模拟国际天气服务结果，不访问真实服务
        with unittest.mock.patch.object(tool, "_fetch_online", return_value="🌤️ 【广州 气象实时监测】: 实时气温 28℃, 状态: Sunny, 湿度: 50%"):
            res = tool.execute(city="广州")
            self.assertFalse(res.is_error)
            text = res.get_text()
            self.assertIn("广州", text)
            self.assertIn("28℃", text)

        # 2. 接口失败场景：真实反馈错误，绝不伪造假模板
        with unittest.mock.patch.object(tool, "_fetch_online", return_value=""):
            fail_res = tool.execute(city="广州")
            self.assertTrue(fail_res.is_error)
            self.assertIn("实时气象查询失败", fail_res.get_text())

        # 3. 缺少参数
        err_res = tool.execute(city="")
        self.assertTrue(err_res.is_error)

    def test_traffic_transit_tool(self):
        tool = TrafficTransitTool()
        # 测试带起终点与地铁方式
        details = {"duration": "约 40 分钟", "cost": "6 元", "route": "测试地铁换乘路线", "tip": "预留候车时间"}
        with mock.patch.object(tool.baidu_client, "ak", "test-ak"), mock.patch.object(
            tool.baidu_client, "route_plan", return_value=(True, details, "")
        ) as route:
            res = tool.execute(city="广州", origin="广州南站", destination="广州塔", transit_mode="metro_bus")
            route.assert_called_once_with("广州", "广州南站", "广州塔", "metro_bus")
        self.assertFalse(res.is_error)
        text = res.get_text()
        self.assertIn("广州南站", text)
        self.assertIn("广州塔", text)
        self.assertIn("地铁", text)
        self.assertIn("预估耗时", text)

        # 没有配置服务时返回错误，不返回硬编码路线。
        unrecorded = tool.execute(city="广州", origin="火星基地", destination="未知地点", transit_mode="metro_bus")
        self.assertTrue(unrecorded.is_error)
        self.assertIn("未配置", unrecorded.get_text())

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

        # 未收录景点真实反馈 is_error=True
        unrecorded = tool.execute(city="广州", attraction_name="虚拟无名景点XYZ")
        self.assertTrue(unrecorded.is_error)
        self.assertIn("未收录", unrecorded.get_text())

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
        target = self.workspace / filename
        self.assertTrue(target.exists())
        with open(target, "r", encoding="utf-8") as f:
            data = f.read()
        self.assertIn("测试广州2日游一条龙攻略", data)
        self.assertIn("15:00 必须到广州塔", data)

        # 2. 列出清单
        list_res = list_tool.execute()
        self.assertFalse(list_res.is_error)
        self.assertIn(filename, list_res.get_text())

    def test_tools_boundary_inputs(self):
        weather_tool = WeatherQueryTool()
        traffic_tool = TrafficTransitTool()

        # 城市为空
        r_w = weather_tool.execute(city="")
        self.assertTrue(r_w.is_error)
        self.assertIn("城市名称不能为空", r_w.get_text())

        # 起点或终点为空
        r_t1 = traffic_tool.execute(city="广州", origin="", destination="广州塔")
        self.assertTrue(r_t1.is_error)
        self.assertIn("不能为空", r_t1.get_text())

        r_t2 = traffic_tool.execute(city="广州", origin="沙面", destination="")
        self.assertTrue(r_t2.is_error)
        self.assertIn("不能为空", r_t2.get_text())


if __name__ == "__main__":
    unittest.main()
