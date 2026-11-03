"""从环境变量读取服务配置，集中维护可调阈值。"""

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "qwen-plus"
    llm_fast_model: str = "qwen-turbo"
    llm_vl_model: str = "qwen-vl-plus"
    search_provider: str = "llm_builtin"
    bocha_api_key: SecretStr = SecretStr("")
    edge_token: SecretStr
    jwt_secret: SecretStr
    admin_password: SecretStr
    demo_password: SecretStr
    demo_mode: bool = False
    database_url: str = "sqlite:///./data/deskmate.db"
    tz: str = "Asia/Shanghai"
    jwt_expire_minutes: int = Field(default=480, ge=1)
    llm_timeout_s: float = Field(default=20, gt=0)
    agent_timeout_s: float = Field(default=90, gt=0)
    acknowledgement_s: float = Field(default=2, gt=0)
    max_agent_steps: int = Field(default=6, ge=1, le=6)
    web_patch_interval_s: float = Field(default=0.2, gt=0)
    heartbeat_s: float = Field(default=20, gt=0)
    edge_stale_s: float = Field(default=60, gt=0)
    scheduler_interval_s: float = Field(default=1, gt=0)
    keyboard_recent_s: int = Field(default=120, ge=1)
    fast_path_timeout_s: float = Field(default=3, gt=0, le=3)
    default_focus_minutes: int = Field(default=45, ge=1)
    break_minutes: int = Field(default=5, ge=1)
    conversation_limit: int = Field(default=50, ge=1)
    conversation_turns: int = Field(default=12, ge=1)
    session_retention_days: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def secure_seeds(self) -> "Config":
        for field in ("edge_token", "jwt_secret"):
            if len(getattr(self, field).get_secret_value()) < 32:
                raise ValueError(f"{field} 至少需要 32 字符随机值")
        for field in ("admin_password", "demo_password"):
            if len(getattr(self, field).get_secret_value()) < 10:
                raise ValueError(f"{field} 至少需要 10 字符")
        return self


DEFAULT_SETTINGS = {
    "focus_lamp": {"brightness": 80, "color_temp": 4000},
    "relax_lamp": {"brightness": 40, "color_temp": 2700},
    "sleep_lamp": {"brightness": 10, "color_temp": 2500},
    "auto_lamp_after": "18:00",
    "motion_window_min": 5,
    "absent_confirm_min": 3,
    "absent_lamp_sleep_min": 3,
    "absent_lamp_off_min": 15,
    "absent_ac_off_min": 30,
    "ac": {
        "auto_rule": "auto",
        "summer_temp": 26,
        "trigger_on_temp": 27.5,
        "high_humidity_trigger": 75.0,
    },
    "wellbeing": {
        "l1_score": 40,
        "l2_score": 55,
        "l3_score": 75,
        "max_continuous_focus_min": 60,
        "cooldown_min": 15,
        "flow_extension_min": 10,
        "max_flow_extensions": 2,
    },
    "app_whitelist": [
        "Code.exe",
        "devenv.exe",
        "idea64.exe",
        "pycharm64.exe",
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
        "notepad.exe",
        "explorer.exe",
        "Typora.exe",
        "Obsidian.exe",
        "WeChat.exe",
    ],
    "study_categories": ["Code.exe", "idea64.exe", "pycharm64.exe", "Typora.exe", "Obsidian.exe"],
    "entertainment_categories": [
        "bilibili.com",
        "douyin.com",
        "weibo.com",
        "Steam.exe",
        "CloudMusic.exe",
    ],
    "voice_takeover_prefixes": ["帮我", "请", "桌伴", "准备一下", "查一下", "分析一下"],
}
