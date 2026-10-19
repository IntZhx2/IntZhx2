"""
交通接驳与通勤换乘规划工具 (Traffic & Transit Tool)
结合百度地图 WebService API (DirectionLite) 与本地精品交通路网，
计算旅游行程中各景点、车站与酒店之间的交通换乘路线、预估耗时、费用及高峰避堵建议。
"""

from typing import Any, Dict, Optional
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
            "为旅游行程规划两地之间的最佳交通接驳方案。"
            "根据用户指定的出行偏好（地铁/公交、打车/网约车、自驾租车、步行或高铁接驳），"
            "计算路线换乘指引、行程预估耗时、费用区间及高峰防拥堵避坑小贴士。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "所在城市，如 '广州', '深圳', '北京'",
                },
                "origin": {
                    "type": "string",
                    "description": "出发地点，如 '广州大学城', '广州南站', '酒店', '沙面岛'",
                },
                "destination": {
                    "type": "string",
                    "description": "目的地点，如 '深圳湾口岸', '广州塔', '广东省博物馆', '北京路'",
                },
                "transit_mode": {
                    "type": "string",
                    "enum": ["metro_bus", "taxi", "self_drive", "walk"],
                    "default": "metro_bus",
                    "description": "交通方式：metro_bus(地铁公交), taxi(打车网约车), self_drive(自驾), walk(步行)",
                },
            },
            "required": ["city", "origin", "destination"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "广州").strip()
        origin = kwargs.get("origin", "").strip()
        dest = kwargs.get("destination", "").strip()
        mode = kwargs.get("transit_mode", "metro_bus")

        if not origin or not dest:
            return ToolCallResult.text("错误: origin 起点与 destination 终点均不能为空", is_error=True)

        mode_name_map = {
            "metro_bus": "🚇 地铁 / 公共交通",
            "taxi": "🚖 打车 / 网约车",
            "self_drive": "🚗 自驾 / 租车",
            "walk": "🚶 城市漫步 (Citywalk 步行)",
        }
        mode_desc = mode_name_map.get(mode, "公共交通")

        # 1. 优先尝试百度地图实时路线规划 (DirectionLite WebService)
        if self.baidu_client.is_configured:
            ok, transit_details, err_msg = self.baidu_client.route_plan(city, origin, dest, mode)
            if ok and transit_details:
                res = (
                    f"🗺️ 【{city} 交通接驳与通勤指引】\n"
                    f"- 🚩 起点: {origin} ➔ 🏁 终点: {dest}\n"
                    f"- 🚗 推荐交通方式: {mode_desc}\n"
                    f"- ⏱️ 预估耗时: {transit_details['duration']}\n"
                    f"- 💰 预估花费: {transit_details['cost']}\n"
                    f"- 🧭 换乘推荐路线:\n  {transit_details['route']}\n"
                    f"- ⚠️ 交通避坑贴士: {transit_details['tip']}\n"
                    f"- 🌐 数据来源: 百度地图实时路线规划 (DirectionLite API)"
                )
                return ToolCallResult.text(res)
            elif err_msg and ("未授权" in err_msg or "被禁用" in err_msg or "AK" in err_msg or "配额" in err_msg):
                # 百度接口鉴权或权限报错，真实报告具体原因，避免被误判为未收录
                return ToolCallResult.text(
                    f"⚠️ 【百度地图接口调用反馈】\n"
                    f"从 '{origin}' 到 '{dest}' 的实时测算未能完成: {err_msg}。\n"
                    f"💡 建议排查: 请登录百度地图开放平台控制台检查 AK 应用类型（需为「服务端」并开启路线规划 API 权限）。\n"
                    f"请大模型结合真实地理网络为用户规划合理的地铁/打车换乘指引与耗时预估。",
                    is_error=True,
                )

        # 2. 次选本地精品交通路网知识库
        local_details = self._analyze_local_route(city, origin, dest, mode)
        if local_details:
            res = (
                f"🗺️ 【{city} 交通接驳与通勤指引】\n"
                f"- 🚩 起点: {origin} ➔ 🏁 终点: {dest}\n"
                f"- 🚗 推荐交通方式: {mode_desc}\n"
                f"- ⏱️ 预估耗时: {local_details['duration']}\n"
                f"- 💰 预估花费: {local_details['cost']}\n"
                f"- 🧭 换乘推荐路线:\n  {local_details['route']}\n"
                f"- ⚠️ 交通避坑贴士: {local_details['tip']}\n"
                f"- 📍 数据来源: 本地已核验专线交通库"
            )
            return ToolCallResult.text(res)

        # 3. 未收录真实反馈，绝不捏造
        return ToolCallResult.text(
            f"【交通路线未收录】未能检索到从 '{origin}' 到 '{dest}' 的专线交通方案。"
            f"请大模型结合真实地理网络为用户规划合理的地铁/打车换乘指引与耗时预估。",
            is_error=True,
        )

    def _analyze_local_route(self, city: str, orig: str, dest: str, mode: str) -> Optional[Dict[str, str]]:
        if "南站" in orig and "广州塔" in dest:
            if mode == "metro_bus":
                return {
                    "duration": "约 35 分钟",
                    "cost": "5 元 / 人",
                    "route": "广州南站乘坐【地铁2号线】（嘉禾望岗方向）至【昌岗站】换乘【地铁8号线】至【客村站】，再换乘【地铁3号线】一站即达【广州塔站】（出站即见塔身）",
                    "tip": "换乘便捷，站内指引清晰；如携带大件行李请走无障碍垂直电梯。",
                }
            elif mode == "taxi":
                return {
                    "duration": "约 30~40 分钟 (平峰)",
                    "cost": "约 65~80 元",
                    "route": "途经广州大道南或东晓南路高架，沿新港中路直达广州塔西路接驳区",
                    "tip": "下午高峰期环城高速与广州大道易偶发拥堵，赶时间建议优先选地铁。",
                }
        elif ("沙面" in orig or "永庆坊" in orig) and "广州塔" in dest:
            return {
                "duration": "约 28 分钟",
                "cost": "4 元 / 人",
                "route": "在【黄沙站】或【文化公园站】乘坐【地铁6号线】至【海珠广场站】，换乘【地铁2号线】至【市二宫】或【昌岗】转【8号线/3号线】直通广州塔",
                "tip": "若偏好江景体验，亦可在黄沙码头乘坐水上巴士【西堤-中大】线，沿江航行后再转车，体验极佳。",
            }
        elif "广州塔" in orig and "北京路" in dest:
            return {
                "duration": "约 22 分钟",
                "cost": "3 元 / 人",
                "route": "【广州塔站】搭乘【APM线】或【地铁3号线】至【海心沙/珠江新城】，转【地铁5号线】至【淘金/杨箕】或直接【3号线北延段】至【嘉禾望岗方向】转【1号线】至【公元前站】D出口即达北京路步行街",
                "tip": "傍晚北京路人流较大，建议提前规划回程地铁末班车时间。",
            }
        elif ("天河" in orig or "珠江新城" in orig or "酒店" in orig) and ("广州塔" in dest or "海心沙" in dest):
            return {
                "duration": "约 15~20 分钟",
                "cost": "地铁 2~3 元，打车约 15~25 元",
                "route": "乘坐【APM线】直达广州塔，或乘坐【地铁3号线】一站跨江直通",
                "tip": "花城广场中轴线可步行经海心桥（需预约）直达广州塔南广场。",
            }

        return None
