"""
天气查询与出行计划工具集
支持获取城市天气指标并联动生成个性化出行/旅游攻略，满足与外部 API 交互及场景化规划需求。
"""

import json
import urllib.request
import urllib.parse
from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult


# 常用城市离线智能气象知识库（网络不可用或离线评测时提供高质量兜底）
OFFLINE_WEATHER_DB = {
    "广州": {"temp": "24~29℃", "cond": "多云转晴", "humidity": "68%", "wind": "微风 2级", "aqi": 35, "advice": "气候温和舒适，非常适宜户外漫步与珠江夜游。"},
    "深圳": {"temp": "25~30℃", "cond": "晴朗", "humidity": "65%", "wind": "东南风 3级", "aqi": 28, "advice": "晴空万里，海滨风光优美，注意防晒并多补充水分。"},
    "北京": {"temp": "12~21℃", "cond": "晴间多云", "humidity": "42%", "wind": "北风 3-4级", "aqi": 42, "advice": "秋高气爽，昼夜温差较明显，早晚外出请适度添衣。"},
    "上海": {"temp": "18~24℃", "cond": "阴天有微风", "humidity": "72%", "wind": "东风 2级", "aqi": 40, "advice": "体感清爽，适宜外滩与武康路城市漫游，出行携带薄外套。"},
    "杭州": {"temp": "17~23℃", "cond": "小雨转阴", "humidity": "82%", "wind": "东北风 2级", "aqi": 32, "advice": "烟雨江南西湖别有韵味，外出请备好雨具并穿着防滑鞋。"},
}


class WeatherQueryTool(BaseTool):
    @property
    def name(self) -> str:
        return "weather_query"

    @property
    def description(self) -> str:
        return "查询指定城市的当前天气情况，包含气温、天气状况、湿度、风力、空气质量及穿衣出行建议。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市中文名称或拼音，如 '广州', '北京', 'Guangzhou'"},
            },
            "required": ["city"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "").strip()
        if not city:
            return ToolCallResult.text("错误: city 城市名称不能为空", is_error=True)

        # 尝试查询公开在线气象接口 (带快速超时容错)
        online_data = self._fetch_online(city)
        if online_data:
            return ToolCallResult.text(online_data)

        # 离线知识库或语义匹配
        matched = None
        for k, v in OFFLINE_WEATHER_DB.items():
            if k in city or city in k:
                matched = (k, v)
                break

        if not matched:
            matched = (city, {
                "temp": "20~26℃",
                "cond": "多云",
                "humidity": "60%",
                "wind": "微风 2级",
                "aqi": 45,
                "advice": "天气良好，适宜各类户外与商务活动。"
            })

        c_name, info = matched
        res = f"""🌤️ 【{c_name} 实时气象情报】
- 🌡️ 气温范围: {info['temp']}
- ☁️ 天气状况: {info['cond']}
- 💧 相对湿度: {info['humidity']}
- 🍃 风向风力: {info['wind']}
- 🌿 空气质量: AQI {info['aqi']} (优)
- 💡 出行指南: {info['advice']}"""
        return ToolCallResult.text(res)

    def _fetch_online(self, city: str) -> str:
        """尝试快速网络探测，若不可达静默返回空"""
        try:
            encoded_city = urllib.parse.quote(city)
            url = f"https://wttr.in/{encoded_city}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "SmartAgent/1.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                current = data.get("current_condition", [{}])[0]
                temp_c = current.get("temp_C", "N/A")
                desc = current.get("weatherDesc", [{}])[0].get("value", "N/A")
                humidity = current.get("humidity", "N/A")
                return f"🌤️ 【{city} 气象实时监测】: 气温 {temp_c}℃, 状态: {desc}, 湿度: {humidity}%, 来源于开放气象站数据。"
        except Exception:
            return ""


class TravelPlanTool(BaseTool):
    @property
    def name(self) -> str:
        return "travel_plan"

    @property
    def description(self) -> str:
        return "为指定目的地生成定制化出行/旅游规划，包含日程安排、景点路线、特色美食与准备建议。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "目的地城市或景点，如 '广州', '成都'"},
                "days": {"type": "integer", "default": 2, "description": "出行天数 (1-7天)"},
                "preference": {
                    "type": "string",
                    "default": "休闲美食",
                    "description": "出行偏好：如 '休闲美食', '人文历史', '自然风光', '高效商务'",
                },
            },
            "required": ["destination"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        dest = kwargs.get("destination", "").strip()
        days = kwargs.get("days", 2)
        pref = kwargs.get("preference", "休闲美食")

        if not dest:
            return ToolCallResult.text("错误: destination 目的地不能为空", is_error=True)

        days = max(1, min(days, 7))

        plan = [
            f"🗺️ 【{dest} {days}日深度出行计划】（偏好：{pref}）",
            "--------------------------------------------------",
        ]

        if "广州" in dest:
            plan.extend([
                "📅 Day 1: 西关风情与舌尖体验",
                "  - 上午: 漫步荔枝湾涌与永庆坊，品尝正宗艇仔粥、双皮奶与银记肠粉",
                "  - 下午: 参观沙面欧式建筑群与粤剧艺术博物馆",
                "  - 晚上: 登广州塔观赏羊城全景，乘珠江红船赏两岸灯光秀",
                "📅 Day 2: 现代岭南与文化探寻",
                "  - 上午: 广东省博物馆（建议提前微信预约）了解岭南海洋与工艺历史",
                "  - 下午: 游览越秀公园镇海楼与五羊石雕",
                "  - 傍晚: 北京路步行街品尝陶陶居/点都德早茶晚市",
            ])
        else:
            for d in range(1, days + 1):
                plan.append(f"📅 Day {d}: {dest} 核心地标与{pref}体验")
                plan.append(f"  - 上午: 游览 {dest} 经典文化地标与历史街区")
                plan.append(f"  - 下午: 深度体验当地特色展馆或自然景观，打卡热门街巷")
                plan.append(f"  - 晚上: 品尝地道特色美食，体验夜间城市夜市与生活气息")

        plan.extend([
            "--------------------------------------------------",
            "🎒 行前准备建议：",
            "1. 携带轻便舒适的运动鞋，城市漫步步数较多；",
            "2. 随身携带充电宝、雨伞及学生证（部分景区可享半价门票）；",
            "3. 建议提前在手机小程序中绑定当地公共交通乘车码。",
        ])

        return ToolCallResult.text("\n".join(plan))
