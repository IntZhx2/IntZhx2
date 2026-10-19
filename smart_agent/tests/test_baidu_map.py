"""
百度地图 WebService API 客户端单元测试 (Baidu Maps Client Tests)
"""

import unittest
from unittest.mock import patch, MagicMock
from smart_agent.tools.baidu_map import BaiduMapClient, get_baidu_ak


class TestBaiduMapClient(unittest.TestCase):
    def test_unconfigured_client(self):
        client = BaiduMapClient(ak="")
        self.assertFalse(client.is_configured)

        # 未配置 AK 时应明确失败
        self.assertIsNone(client.geocode("广州塔"))
        ok, res, err = client.route_plan("广州", "广州南站", "广州塔")
        self.assertFalse(ok)
        self.assertIn("未配置", err)

    @patch("smart_agent.tools.baidu_map.BaiduMapClient._request")
    def test_geocode_success(self, mock_request):
        mock_request.return_value = (
            True,
            {"status": 0, "result": {"location": {"lat": 23.10647, "lng": 113.32446}}},
            "",
        )
        client = BaiduMapClient(ak="mock_test_ak")
        coords = client.geocode("广州塔", "广州")
        self.assertIsNotNone(coords)
        self.assertAlmostEqual(coords[0], 23.10647)
        self.assertAlmostEqual(coords[1], 113.32446)

    @patch("smart_agent.tools.baidu_map.BaiduMapClient.geocode")
    @patch("smart_agent.tools.baidu_map.BaiduMapClient._request")
    def test_transit_route_plan(self, mock_request, mock_geocode):
        mock_geocode.side_effect = [(23.05, 113.39), (22.50, 113.94)]
        mock_request.return_value = (
            True,
            {
                "status": 0,
                "result": {
                    "routes": [
                        {
                            "duration": 5400,
                            "price": 35,
                            "steps": [
                                [{"vehicle_info": {"detail": {"name": "广深城际铁路"}}}],
                                [{"instruction": "从深圳北站换乘地铁5号线"}],
                            ],
                        }
                    ]
                },
            },
            "",
        )
        client = BaiduMapClient(ak="mock_test_ak")
        ok, details, err = client.route_plan("广州", "广州大学城", "深圳湾口岸", "metro_bus")
        self.assertTrue(ok)
        self.assertIsNotNone(details)
        self.assertIn("90 分钟", details["duration"])
        self.assertIn("35 元", details["cost"])
        self.assertIn("广深城际铁路", details["route"])

    @patch("smart_agent.tools.baidu_map.BaiduMapClient._request")
    def test_place_search_poi(self, mock_request):
        mock_request.return_value = (
            True,
            {
                "status": 0,
                "results": [
                    {
                        "name": "深圳湾公园",
                        "address": "深圳市南山区滨海大道(望海路)",
                        "telephone": "0755-86085890",
                        "detail_info": {
                            "tag": "旅游景点;公园",
                            "overall_rating": "4.8",
                            "shop_hours": "06:00-23:00",
                        },
                    }
                ],
            },
            "",
        )
        client = BaiduMapClient(ak="mock_test_ak")
        poi = client.search_place("深圳湾公园", "深圳")
        self.assertIsNotNone(poi)
        self.assertEqual(poi["name"], "深圳湾公园")
        self.assertEqual(poi["rating"], "4.8")
        self.assertIn("06:00-23:00", poi["shop_hours"])


if __name__ == "__main__":
    unittest.main()
