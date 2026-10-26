"""
交通接驳与通勤换乘规划工具。
通过百度地图 DirectionLite 查询路线，无法获取时明确报告失败。
"""

from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult
from smart_agent.tools.baidu_map import BaiduMapClient


class TrafficTransitTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.baidu_client = BaiduMapClient()

    @property
    def name(self) -> str:
        return "traffic_transit"

    @property
    def description(self) -> str:
        return (
            "按指定城市、起终点和交通方式查询百度地图路线、预估耗时与费用。"
            "支持地铁公交、打车、自驾和步行；未配置服务或查询失败时返回错误。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "所在城市，如广州、深圳、北京"},
                "origin": {"type": "string", "description": "出发地点"},
                "destination": {"type": "string", "description": "目的地点"},
                "transit_mode": {
                    "type": "string",
                    "enum": ["metro_bus", "taxi", "self_drive", "walk"],
                    "description": "metro_bus(地铁公交), taxi(打车), self_drive(自驾), walk(步行)",
                },
            },
            "required": ["city", "origin", "destination", "transit_mode"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        values = {}
        for field, label in (("city", "城市名称"), ("origin", "起点"), ("destination", "终点")):
            value = kwargs.get(field)
            if not isinstance(value, str) or not value.strip():
                return ToolCallResult.text(f"错误: {field} {label}不能为空且必须为字符串", is_error=True)
            values[field] = value.strip()
        city, origin, dest = values["city"], values["origin"], values["destination"]
        mode = kwargs.get("transit_mode")
        mode_names = {
            "metro_bus": "🚇 地铁 / 公共交通",
            "taxi": "🚖 打车 / 网约车",
            "self_drive": "🚗 自驾 / 租车",
            "walk": "🚶 城市漫步 (步行)",
        }
        if not isinstance(mode, str) or mode not in mode_names:
            return ToolCallResult.text(
                "错误: transit_mode 必须明确指定为 metro_bus、taxi、self_drive 或 walk",
                is_error=True,
            )
        if not self.baidu_client.is_configured:
            return ToolCallResult.text(
                "【交通路线查询失败】未配置百度地图 AK，无法核验路线、耗时与费用。",
                is_error=True,
            )
        ok, details, err_msg = self.baidu_client.route_plan(city, origin, dest, mode)
        if not ok or not details:
            return ToolCallResult.text(
                f"【交通路线查询失败】从 '{origin}' 到 '{dest}' 的路线测算未能完成: "
                f"{err_msg or '接口未返回可用路线'}。请稍后重试或使用地图应用核验。",
                is_error=True,
            )
        return ToolCallResult.text(
            f"🗺️ 【{city} 交通接驳与通勤指引】\n"
            f"- 🚩 起点: {origin} ➔ 🏁 终点: {dest}\n"
            f"- 🚗 推荐交通方式: {mode_names[mode]}\n"
            f"- ⏱️ 预估耗时: {details['duration']}\n"
            f"- 💰 预估花费: {details['cost']}\n"
            f"- 🧭 换乘推荐路线:\n  {details['route']}\n"
            f"- ⚠️ 交通避坑贴士: {details['tip']}\n"
            f"- 🌐 数据来源: 百度地图路线规划 (DirectionLite API)，结果仅供参考"
        )
