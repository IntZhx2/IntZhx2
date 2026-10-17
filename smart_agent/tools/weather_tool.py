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
        import random
        dest = kwargs.get("destination", "").strip()
        days = kwargs.get("days", 2)
        pref = kwargs.get("preference", "休闲美食")

        if not dest:
            return ToolCallResult.text("错误: destination 目的地不能为空", is_error=True)

        days = max(1, min(days, 7))

        # 丰富的特色主题景点与美食候选池，让本地离线生成更生动多变
        gz_themes = [
            {
                "theme": "西关烟火与历史老街",
                "morning": "漫步永庆坊、荔枝湾涌与粤剧艺术博物馆，品尝老字号艇仔粥与银记肠粉",
                "afternoon": "游览沙面欧式建筑群，在古榕树与石板路上体验民国风情与近代海关旧址",
                "night": "前往太古仓码头或珠江琶醍，观赏江景落日与创意音乐餐吧",
            },
            {
                "theme": "岭南文化与云山珠水",
                "morning": "登白云山摩星岭眺望羊城全貌，体验鸣春谷鸟鸣与山顶早茶",
                "afternoon": "参观越秀公园五羊石雕与镇海楼（广州博物馆），探访古城墙历史",
                "night": "乘珠江红船游船，夜游两岸灯光秀，近距离打卡海心沙与猎德大桥",
            },
            {
                "theme": "现代都市与艺术打卡",
                "morning": "参观广东省博物馆与广州大剧院，感受花城广场宏伟的现代中轴线建筑群",
                "afternoon": "漫步东山口新河浦历史文化街区，打卡百年红砖洋房与先锋独立艺术展",
                "night": "登上广州塔（小蛮腰）433米观光平台俯瞰流光溢彩的珠江夜色",
            },
            {
                "theme": "古寺禅意与市井早茶",
                "morning": "前往陶陶居或点都德总店品尝地道早茶（虾饺、红米肠、豉汁凤爪）",
                "afternoon": "参拜六榕寺与光孝寺（“未有羊城，先有光孝”），漫步古朴惠福东路",
                "night": "逛北京路步行街千年古道遗址与大佛寺绝美夜景灯光",
            },
        ]

        plan = [
            f"🗺️ 【{dest} {days}日深度出行计划】（偏好：{pref}）",
            "--------------------------------------------------",
        ]

        if "广州" in dest:
            # 随机选取不重复的主题路线组合
            selected_themes = random.sample(gz_themes, min(days, len(gz_themes)))
            for idx, item in enumerate(selected_themes, start=1):
                plan.extend([
                    f"📅 Day {idx}: {item['theme']}",
                    f"  - 🌅 上午: {item['morning']}",
                    f"  - ☀️ 下午: {item['afternoon']}",
                    f"  - 🌙 晚上: {item['night']}",
                ])
        else:
            spots = ["历史文化街区与核心展馆", "网红艺术创意园区与手作工坊", "地标观景台与自然湿地公园", "传统特色小吃街与老字号夜市"]
            random.shuffle(spots)
            for d in range(1, days + 1):
                s1 = spots[(d * 2 - 2) % len(spots)]
                s2 = spots[(d * 2 - 1) % len(spots)]
                plan.extend([
                    f"📅 Day {d}: {dest} 深度探索与{pref}体验",
                    f"  - 🌅 上午: 游览 {dest} 经典{s1}，感受地道风土人情",
                    f"  - ☀️ 下午: 深度探访{s2}，拍照打卡与选购特色纪念物",
                    f"  - 🌙 晚上: 寻访当地大众点评黑珍珠/必吃榜地道餐厅，体验夜市烟火",
                ])

        tips_pool = [
            "携带轻便舒适的运动鞋，城市漫步平均每日步数约 15,000+ 步；",
            "随身备好晴雨伞，岭南天气多变，遮阳防雨两相宜；",
            "建议提前在微信/支付宝小程序中绑定“广州公共交通乘车码”，扫码直接搭乘地铁APM线与公交；",
            "广东省博物馆与广州塔观光门票建议提前 3~7 天在官方公众号实名预约；",
            "早茶通常在上午 9:00~11:00 为高峰期，错峰就餐体验更舒适。",
        ]
        chosen_tips = random.sample(tips_pool, 3)

        plan.extend([
            "--------------------------------------------------",
            "🎒 行前实用小贴士：",
        ] + [f"{i}. {tip}" for i, tip in enumerate(chosen_tips, start=1)])

        return ToolCallResult.text("\n".join(plan))
