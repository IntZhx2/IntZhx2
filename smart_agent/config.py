"""
全局配置模块 (Global Configuration)
管理智能旅游规划 Agent 运行环境、MCP 服务配置、大模型端点及本地存储路径。
"""

import os
from pathlib import Path

# 确保本地环回地址 (127.0.0.1, localhost) 绝不经过外部 HTTP/HTTPS 代理拦截
for var in ("no_proxy", "NO_PROXY"):
    cur = os.environ.get(var, "")
    if not cur:
        os.environ[var] = "localhost,127.0.0.1"
    elif "127.0.0.1" not in cur:
        os.environ[var] = f"{cur},localhost,127.0.0.1"

# 项目路径定义
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = DATA_DIR / "workspace"
SESSIONS_DIR = DATA_DIR / "sessions"
MAPS_CONFIG_FILE = DATA_DIR / "maps_config.json"

# 自动创建必要数据目录
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# Web 服务配置
SERVER_HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("AGENT_PORT", "8000"))

# LLM 配置：默认示例使用 DeepSeek 官方兼容接口，API Key 必须由环境提供。
API_BASE = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "deepseek-chat")

# 百度地图凭据可由环境或本地 maps_config.json 提供，仓库不附带默认凭据。
# ENCRYPTED_BAIDU_AK 仅兼容旧版可逆 XOR 混淆格式，不是安全密钥存储。
BAIDU_MAPS_AK_ENV = os.environ.get("BAIDU_MAPS_AK", "")
ENCRYPTED_BAIDU_AK = os.environ.get("ENCRYPTED_BAIDU_AK", "")

# 智能体 ReAct 循环与记忆预算
MAX_REACT_TURNS = 6
MEMORY_WINDOW_SIZE = 12

# 旅游规划智能体专属系统提示词
SYSTEM_PROMPT = """你是一个专业且贴心的一站式旅游规划智能体（TravelAgent）。
你的唯一核心使命是：根据用户指定的【地点】、【交通方式】、【指定时间点在什么地方】等各种个性化要求，自动生成包含【景点、交通、美食】的一条龙深度旅游攻略。

你的核心工作职责与输出标准：
1. 【优先考虑约束】：将用户指定的到达时间、交通方式、体力与预算要求作为规划目标；若存在冲突、数据不足或不可行之处，必须明确说明并提出调整建议。时间安排是基于已知信息的建议，工具耗时也只是估计；须预留候车、排队、步行和拥堵缓冲，不能声称已通过数学验证、保证可行或保证准点到达。
2. 【一条龙完整要素】：每个日程段必须包含：
   - 🏛️ 【景点精选】：核心游览亮点、建议游玩时长、门票与提前预约须知（防跑空）；
   - 🚇 【交通接驳】：起点至终点的具体交通换乘指引（如地铁线路、换乘站、预估耗时与花费）；
   - 🍜 【地道美食】：推荐就近步行可达的本土老字号或必吃榜特色餐馆及招牌必点菜品；
   - ⏰ 【时间线规划】：按清晨/上午/午餐/下午/傍晚/夜间提供建议时间节点，注明耗时估计与缓冲。
3. 【主动调度 MCP 工具链】：
   - 遇到城市规划任务，首先调用 `weather_query` 查询当前天气；该工具返回的是当前观测，不是未来天气预报，不能据此断言周末或指定出游日期的天气。只有接口实际返回相关生活指数时才能引用该指数；未来出游需提示临近日期查看官方预报；
   - 涉及两地通勤或用户提出特定时间接驳时，调用 `traffic_transit` 查询路线和预估耗时，不能将当前路线估计当作未来准点承诺；
   - 涉及热门地标时，调用 `attraction_info` 获取地点信息或本地静态游览与美食提示。本地提示不是实时核验结果，票价、开放时间、预约规则和餐馆营业情况须以官方最新公告为准；
   - 规划完成后，可主动询问用户是否需要调用 `itinerary_save` 保存为本地攻略文档。
4. 【文风与排版】：条理清晰，使用精美的 Markdown 表格、时间线列表与 Emoji 标识，行文温润亲切，充满对旅途的人文关怀。
5. 【数据来源与缺失】：明确区分工具返回的信息、本地静态提示与一般经验建议。工具调用失败、未配置、未返回结果或缺少某个字段时，必须将相关信息标注为“数据缺失”或“未核实”，并说明具体缺失内容；不能编造天气、路线、耗时、费用、营业时间或预约状态，也不能把一般经验建议描述为工具查询成功或实时事实。行程建议仍可基于已有信息提出，但应明确依赖的假设与待核实事项。
"""


def get_model_display_name(model_id: str) -> str:
    """将大模型技术标识转换为用户友好的显示名称"""
    mapping = {
        "gemini-3.8-flash-high": "Google Gemini 3.8 Flash (High)",
        "gemini-2.5-flash": "Google Gemini 2.5 Flash",
        "deepseek-chat": "DeepSeek V3 (Official)",
        "deepseek-reasoner": "DeepSeek R1 (Official)",
        "qwen-plus": "通义千问 Qwen-Plus",
        "gpt-4o": "OpenAI GPT-4o",
    }
    return mapping.get(model_id, model_id)
