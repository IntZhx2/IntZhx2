"""
景点深度情报与美食打卡工具 (Attraction & Gourmet Tool)
结合百度地图 Place API POI 深度检索与精选文旅知识图谱，
提供全国旅游景点的真实地址、开放时间、评分、游玩时长建议、门票预约及周边地道美食。
"""

from typing import Any, Dict
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult
from smart_agent.tools.baidu_map import BaiduMapClient

# 核心景点与特色美食深度知识图谱（带详细预约规则与老字号美食指南）
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
    def __init__(self):
        super().__init__()
        self.baidu_client = BaiduMapClient()

    @property
    def name(self) -> str:
        return "attraction_info"

    @property
    def description(self) -> str:
        return (
            "查询旅游景点的深度详细信息与周边地道美食推荐。"
            "包含景点的真实地址、最佳游玩时间段、建议停留时长、门票与提前预约规则、核心打卡机位，"
            "以及周边步行可达的正宗老字号餐厅与招牌菜品推荐。"
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "所在城市，例如 '广州', '深圳', '杭州'",
                },
                "attraction_name": {
                    "type": "string",
                    "description": "景点名称，例如 '广州塔', '深圳湾公园', '永庆坊', '西湖'",
                },
            },
            "required": ["city", "attraction_name"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        city = kwargs.get("city", "广州").strip()
        name = kwargs.get("attraction_name", "").strip()

        if not name:
            return ToolCallResult.text("错误: attraction_name 景点名称不能为空", is_error=True)

        # 1. 优先命中本地深度文旅知识库
        matched_info = None
        for k, v in ATTRACTION_KNOWLEDGE.items():
            if k in name or name in k:
                matched_info = (k, v)
                break

        if matched_info:
            full_name, data = matched_info
            res = (
                f"🏛️ 【{city} · {full_name} 游览与美食深度攻略】\n"
                f"- 🏷️ 景点定位: {data['tag']}\n"
                f"- ⏱️ 建议时长: {data['duration']}\n"
                f"- ⏰ 黄金游览时段: {data['best_time']}\n"
                f"- 🎟️ 门票与预约要求: {data['booking']}\n"
                f"- 📸 核心机位与打卡亮点: {data['highlights']}\n"
                f"- 🍽️ 周边招牌美食推荐: {data['gourmet']}\n"
                f"- 📍 数据来源: 本地已核验精品文旅智库"
            )
            return ToolCallResult.text(res)

        # 2. 次选百度地图 POI 地点服务实时检索
        if self.baidu_client.is_configured:
            poi, err_msg = self.baidu_client.search_place(name, city)
            if poi:
                res = (
                    f"🏛️ 【{city} · {poi['name']} 官方实地文旅档案】\n"
                    f"- 🏷️ 地理分类: {poi['tag']}\n"
                    f"- 📍 详细地址: {poi['address']}\n"
                    f"- ⭐ 游客评分: {poi['rating']} / 5.0\n"
                    f"- ⏰ 营业开放时间: {poi['shop_hours']}\n"
                    f"- 📞 景区/商户电话: {poi['telephone']}\n"
                    f"- 🌐 数据来源: 百度地图实时地点检索 (Place POI API)\n"
                    f"- 💡 游玩与美食建议: 请大模型结合上述真实地址与开放时间，为游客合理规划游玩时长与就近地道风味。"
                )
                return ToolCallResult.text(res)
            elif err_msg and ("未授权" in err_msg or "被禁用" in err_msg or "AK" in err_msg or "配额" in err_msg):
                return ToolCallResult.text(
                    f"⚠️ 【百度地图接口调用反馈】\n"
                    f"景点 '{name}' 实时 POI 检索失败: {err_msg}。\n"
                    f"💡 建议排查: 请登录百度地图开放平台控制台检查 AK 应用类型（需为「服务端」并开启地点检索 API 权限）。\n"
                    f"请大模型结合公开知识库为用户规划该景点的建议游玩时长、门票预约及周边地道美食。",
                    is_error=True,
                )

        # 3. 未收录真实反馈，绝不捏造
        return ToolCallResult.text(
            f"【景点数据未收录】未能通过百度地图或文旅知识库检索到景点 '{name}'（城市：{city}）的备案游览与预约规则。"
            f"请大模型结合公开知识库为用户规划该景点的建议游玩时长、门票预约及周边地道美食。",
            is_error=True,
        )
