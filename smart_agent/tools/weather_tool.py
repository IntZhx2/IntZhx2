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

class WeatherQueryTool(BaseTool):
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
                    "description": "目标城市名称，例如 '广州', '北京', '成都'",
                }
            },
            "required": ["city"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "").strip()
        if not city:
            return ToolCallResult.text("错误: city 城市名称不能为空", is_error=True)

        # 尝试查询实时气象在线服务 (真实网络 API，绝不使用死模板或虚假预置数据)
        online_res = self._fetch_online(city)
        if online_res:
            return ToolCallResult.text(online_res)

        # 若在线气象接口失败或离线，绝不伪造虚假数据，如实返回错误反馈
        return ToolCallResult.text(
            f"【实时气象查询失败】无法通过实时气象接口获取城市 '{city}' 的天气数据（外部服务无响应或城市名称未命中）。"
            f"请大模型结合当地常识向用户提示大致季节气候与出行防护建议。",
            is_error=True,
        )

    def _fetch_online(self, city: str) -> str:
        try:
            encoded = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "TravelAgent/1.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
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
                        f"- 🍃 数据来源: 真实在线气象观测站 (wttr.in)"
                    )
        except Exception:
            pass
        return ""
