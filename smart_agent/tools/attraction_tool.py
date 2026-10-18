"""
景点深度情报与美食打卡工具 (Attraction & Gourmet Tool)
提供目的地景点的游玩时长建议、门票预约规则、打卡机位以及周边必吃特色地道美食。
"""

from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult

# 核心景点与特色美食知识图谱
ATTRACTION_KNOWLEDGE = {
    "广州塔": {
        "city": "广州",
        "tag": "地标建筑 / 现代夜景",
        "duration": "建议游玩 2~3 小时",
        "best_time": "17:30~20:30 (可同时欣赏落日余晖与城市流光夜景)",
        "booking": "需提前在“广州塔”官方公众号购票实名预约分时段入塔；433米白云星空观光票约 150元。",
        "highlights": "433米星空观光厅俯瞰全城、450米户外平台、极速云霄与摩天轮。",
        "gourmet": "塔内有璇玑地中海自助旋转餐厅；塔下及海心沙周边推荐【炳胜品味】(招牌脆皮叉烧、黑椒和牛)与琶醍江畔音乐餐吧。",
    },
    "永庆坊": {
        "city": "广州",
        "tag": "历史街区 / 岭南文脉 / 骑楼风情",
        "duration": "建议游玩 2~2.5 小时",
        "best_time": "10:00~13:00 或 16:00~19:00",
        "booking": "全天开放，无需门票；内部【粤剧艺术博物馆】周一闭馆，需在公众号提前预约免费入场。",
        "highlights": "李小龙祖居、月亮桥夜景倒影、钟书阁特色骑楼书店、非遗街区广彩广绣。",
        "gourmet": "周边遍布西关老字号：【银记肠粉】(牛肉肠配艇仔粥)、【恩宁刘福记】(传统竹升面)、【顺记冰室】(手工芒果椰子冰酪)。",
    },
    "沙面": {
        "city": "广州",
        "tag": "近代欧式建筑群 / 珠江林荫漫步",
        "duration": "建议游玩 1.5~2 小时",
        "best_time": "上午 9:30~11:30 (光线柔和，适宜人像摄影)",
        "booking": "全天免费对外开放，属于历史文化保护街区，无需门票。",
        "highlights": "露德天主教圣母堂、沙面大街古樟树群、海关红楼、星巴克欧式独栋小洋楼。",
        "gourmet": "推荐前往全国最早中外合资五星级酒店【白天鹅宾馆·玉堂春暖】品尝顶级黑珍珠粤式早茶（榄仁萨其马、虾饺皇）。",
    },
    "广东省博物馆": {
        "city": "广州",
        "tag": "国家一级博物馆 / 岭南历史与海洋自然",
        "duration": "建议游玩 2.5~3 小时",
        "best_time": "周二至周日 9:00~17:00 (16:00停止入馆，周一闭馆)",
        "booking": "免费开放，但极为火爆！必须提前在“广东省博物馆”公众号实名抢约门票（通常提前数天放票）。",
        "highlights": "“月光宝盒”特色建筑外观、三楼潮州木雕艺术展（金碧辉煌）、自然资源与古生物恐龙化石展。",
        "gourmet": "出馆后步行至花城汇地下美食广场，推荐【陶陶居】或【大头虾越式风味】(麻油捞鸡、咖喱牛腩)。",
    },
    "越秀公园": {
        "city": "广州",
        "tag": "羊城八景 / 古迹园林",
        "duration": "建议游玩 1.5~2 小时",
        "best_time": "早晨 8:00~10:30 (空气清新，感受市民晨练氛围)",
        "booking": "免费对外开放，镇海楼（广州博物馆）登楼需现场购票约 10元。",
        "highlights": "五羊石雕（广州市标象征）、明代古城墙、镇海楼（五层楼登高俯瞰）。",
        "gourmet": "公园南门出即到盘福路与东风西路美食圈，推荐【惠食佳】(老字号啫啫煲、生肠煲、黄鳝饭)。",
    },
    "北京路步行街": {
        "city": "广州",
        "tag": "千年商都遗址 / 繁华商业步行街",
        "duration": "建议游玩 2 小时",
        "best_time": "下午至晚上 16:00~21:30",
        "booking": "全天开放，无需门票；大佛寺亮灯时间通常为 19:00~21:00。",
        "highlights": "千年古道玻璃地面遗址、南越国木构水闸遗址、大佛古寺夜间金碧辉煌亮灯盛景（宛如现实版千与千寻）。",
        "gourmet": "惠福东路小吃一条街：【陈添记鱼皮】(传统祖传爽脆鱼皮)、【富导传统小吃】(萝卜牛杂)、【达杨原味炖品】(原只椰子炖竹丝鸡)。",
    },
}


class AttractionInfoTool(BaseTool):
    @property
    def name(self) -> str:
        return "attraction_info"

    @property
    def description(self) -> str:
        return (
            "查询旅游景点的深度详细信息与周边地道美食推荐。"
            "包含景点的最佳游玩时间段、建议停留时长、门票与提前预约规则、核心打卡机位，"
            "以及周边步行可达的正宗老字号餐厅与招牌菜品推荐。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "所在城市，例如 '广州'",
                },
                "attraction_name": {
                    "type": "string",
                    "description": "景点名称，例如 '广州塔', '永庆坊', '沙面', '广东省博物馆', '越秀公园', '北京路'",
                },
            },
            "required": ["city", "attraction_name"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "广州").strip()
        name = kwargs.get("attraction_name", "").strip()

        if not name:
            return ToolCallResult.text("错误: attraction_name 景点名称不能为空", is_error=True)

        matched_info = None
        for k, v in ATTRACTION_KNOWLEDGE.items():
            if k in name or name in k:
                matched_info = (k, v)
                break

        if not matched_info:
            res = (
                f"🏛️ 【{city} · {name} 景点速览】\n"
                f"- ⏱️ 建议游览时长: 约 1.5~2.5 小时\n"
                f"- 📅 预约与门票: 建议提前关注景区官方公众号确认最新开放时段与实名预约要求。\n"
                f"- 📸 游玩建议: 建议避开周末正午人流高峰，携带身份证件有序入场。\n"
                f"- 🍜 周边美食: 建议就近探寻老城区巷弄内的大众点评高分本土特色餐馆。"
            )
            return ToolCallResult.text(res)

        full_name, data = matched_info
        res = (
            f"🏛️ 【{city} · {full_name} 游览与美食攻略】\n"
            f"- 🏷️ 景点定位: {data['tag']}\n"
            f"- ⏱️ 建议时长: {data['duration']}\n"
            f"- ⏰ 黄金游览时段: {data['best_time']}\n"
            f"- 🎟️ 门票与预约要求: {data['booking']}\n"
            f"- 📸 核心机位与打卡亮点: {data['highlights']}\n"
            f"- 🍽️ 周边招牌美食推荐: {data['gourmet']}"
        )
        return ToolCallResult.text(res)
