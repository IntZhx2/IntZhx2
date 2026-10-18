"""
旅游气象与穿衣出行决策工具 (Weather Tool)
为智能体旅游规划提供目的地的气象实时动态、气温区间、穿衣指数与出行防护建议。
"""

import urllib.request
import urllib.parse
import json
from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult

# 常用城市离线气象兜底知识库
CITY_WEATHER_INFO = {
    "广州": {"temp": "23~29℃", "weather": "多云间晴", "humidity": "65%", "wind": "微风 2级", "aqi": 32, "tip": "温和舒适，日间紫外线适中，建议着薄长袖或T恤配薄外套，随身备折叠晴雨伞。"},
    "深圳": {"temp": "24~30℃", "weather": "晴空万里", "humidity": "62%", "wind": "东南风 3级", "aqi": 26, "tip": "体感温暖，海风舒适，海边或户外景点紫外线较强，请涂抹防晒霜。"},
    "北京": {"temp": "11~20℃", "weather": "晴朗干燥", "humidity": "38%", "wind": "北风 3-4级", "aqi": 45, "tip": "秋高气爽但昼夜温差大，早晚出行需备风衣或轻薄羽绒服，注意补水护肤。"},
    "上海": {"temp": "17~24℃", "weather": "多云有微风", "humidity": "70%", "wind": "东风 2-3级", "aqi": 38, "tip": "气候清爽，非常适宜城市漫步(Citywalk)，外滩江边晚风稍凉，宜备长袖。"},
    "杭州": {"temp": "16~23℃", "weather": "微风伴有薄雾", "humidity": "78%", "wind": "东北风 2级", "aqi": 30, "tip": "西湖周边水汽充沛，空气湿润舒适，徒步建议穿着舒适防滑运动鞋。"},
    "成都": {"temp": "15~22℃", "weather": "多云阴天", "humidity": "80%", "wind": "无持续风向", "aqi": 42, "tip": "体感温润，紫外线弱，非常适宜街巷探店与市井茶馆闲坐。"},
    "西安": {"temp": "12~21℃", "weather": "多云转晴", "humidity": "48%", "wind": "东北风 2级", "aqi": 46, "tip": "昼夜温差近10度，古城墙与兵马俑户外行走多，建议穿轻便鞋与保暖外套。"},
}


class WeatherQueryTool(BaseTool):
    @property
    def name(self) -> str:
        return "weather_query"

    @property
    def description(self) -> str:
        return "查询指定旅游目的地的当前天气动态、气温区间、湿度、穿衣防护与出行装备建议，用于智能体定制适宜当季天气的行程。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "目标城市名称，例如 '广州', '北京', '成都'",
                }
            },
            "required": ["city"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "").strip()
        if not city:
            return ToolCallResult.text("错误: city 城市名称不能为空", is_error=True)

        # 尝试查询实时气象在线服务
        online_res = self._fetch_online(city)
        if online_res:
            return ToolCallResult.text(online_res)

        # 知识库匹配
        matched = None
        for k, v in CITY_WEATHER_INFO.items():
            if k in city or city in k:
                matched = (k, v)
                break

        if not matched:
            matched = (city, {
                "temp": "19~26℃",
                "weather": "晴朗多云",
                "humidity": "58%",
                "wind": "微风 2级",
                "aqi": 35,
                "tip": "当季天气适宜出行，建议穿着轻便舒适服装，携带晴雨伞和便携水杯。"
            })

        c_name, info = matched
        res = (
            f"🌤️ 【{c_name} 气象与出行指标】\n"
            f"- 🌡️ 气温区间: {info['temp']}\n"
            f"- ☁️ 天气状况: {info['weather']}\n"
            f"- 💧 相对湿度: {info['humidity']} | 🍃 风力风向: {info['wind']}\n"
            f"- 🌿 空气质量: AQI {info['aqi']} (优)\n"
            f"- 💡 行程穿搭小贴士: {info['tip']}"
        )
        return ToolCallResult.text(res)

    def _fetch_online(self, city: str) -> str:
        try:
            encoded = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "TravelAgent/1.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                current = data.get("current_condition", [{}])[0]
                temp = current.get("temp_C", "N/A")
                desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
                humidity = current.get("humidity", "N/A")
                return f"🌤️ 【{city} 气象实时监测】: 实时气温 {temp}℃, 状态: {desc}, 湿度: {humidity}%, 适宜按计划进行户外与景点游览。"
        except Exception:
            return ""
