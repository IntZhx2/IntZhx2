"""
旅游气象与穿衣出行决策工具 (Weather Tool)
结合百度地图官方气象服务 (Weather API) 与国际气象站，
为智能体旅游规划提供目的地的气象实时动态、气温区间、穿衣指数与出行防护建议。
"""

import urllib.request
import urllib.parse
import json
import math
from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult
from smart_agent.tools.baidu_map import BaiduMapClient


def _aqi_label(value: Any) -> str:
    """按 AQI 数值分级，缺失或无效数据不能视为优良。"""
    if isinstance(value, bool):
        return "未知"
    try:
        aqi = float(value)
    except (TypeError, ValueError):
        return "未知"
    if not math.isfinite(aqi) or not 0 <= aqi <= 500:
        return "未知"
    for upper, label in ((50, "优"), (100, "良"), (150, "轻度污染"),
                         (200, "中度污染"), (300, "重度污染"), (500, "严重污染")):
        if aqi <= upper:
            return label


class WeatherQueryTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.baidu_client = BaiduMapClient()

    @property
    def name(self) -> str:
        return "weather_query"

    @property
    def description(self) -> str:
        return "查询指定旅游目的地的当前天气动态、气温区间、湿度与穿衣建议，用于智能体定制适宜当季天气的行程。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "目标城市名称，例如 '广州', '深圳', '北京', '成都'",
                }
            },
            "required": ["city"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "")
        if not isinstance(city, str) or not city.strip():
            return ToolCallResult.text("错误: city 城市名称不能为空", is_error=True)
        city = city.strip()

        # 1. 优先调用百度地图官方气象服务 (毫秒级响应，包含原生穿衣/紫外线/感冒指数)
        if self.baidu_client.is_configured:
            w_data, b_err = self.baidu_client.get_weather(city)
            if w_data:
                tips_block = f"\n{w_data['tips']}" if w_data.get("tips") else ""
                res = (
                    f"🌤️ 【{city} 气象实时监测】\n"
                    f"- 🌡️ 实时气温: {w_data['temp']}℃ (体感温度: {w_data['feels_like']}℃)\n"
                    f"- ☁️ 天气状态: {w_data['text']}\n"
                    f"- 💧 相对湿度: {w_data['rh']}%\n"
                    f"- 🍃 风向风力: {w_data['wind_dir']} {w_data['wind_class']}\n"
                    f"- 🌿 空气质量: AQI {w_data.get('aqi', '--')} ({_aqi_label(w_data.get('aqi'))})\n"
                    f"- 🌐 数据来源: 百度地图实时气象监测服务 (Weather API)"
                    f"{tips_block}"
                )
                return ToolCallResult.text(res)

        # 2. 次选 wttr.in 国际气象站在线兜底
        online_res = self._fetch_online(city)
        if online_res:
            return ToolCallResult.text(online_res)

        # 3. 若均无法获取，诚实返回错误反馈，绝不使用死模板或虚假预置数据
        return ToolCallResult.text(
            f"【实时气象查询失败】无法通过气象接口获取城市 '{city}' 的实时数据。"
            f"请大模型结合当地常识向用户提示大致季节气候与出行防护建议。",
            is_error=True,
        )

    def _fetch_online(self, city: str) -> str:
        try:
            encoded = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded}?format=j1"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "curl/7.68.0 TravelAgent/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                current = data.get("current_condition", [{}])[0]
                temp = current.get("temp_C", "")
                desc = current.get("weatherDesc", [{}])[0].get("value", "")
                humidity = current.get("humidity", "")
                feels_like = current.get("FeelsLikeC", "")
                if temp:
                    return (
                        f"🌤️ 【{city} 气象实时监测】\n"
                        f"- 🌡️ 实时气温: {temp}℃ (体感温度: {feels_like}℃)\n"
                        f"- ☁️ 天气状态: {desc}\n"
                        f"- 💧 相对湿度: {humidity}%\n"
                        f"- 🍃 数据来源: 国际气象观测站 (wttr.in)"
                    )
        except Exception:
            pass
        return ""
