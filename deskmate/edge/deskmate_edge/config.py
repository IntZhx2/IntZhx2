"""DeskMate Edge 配置加载模块 (config.py)
基于 Pydantic 加载 .env 与 config/devices.yaml
具备自动回退机制，确保在极简环境下也能稳定加载
"""

import os
from pathlib import Path
from typing import Any
import yaml

# 定位 edge 根目录
EDGE_ROOT = Path(__file__).resolve().parent.parent


def _parse_env_file(filepath: Path) -> dict[str, str]:
    """简单解析 .env 键值对"""
    env_vars = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars


try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class EdgeSettings(BaseSettings):
        """边缘端环境配置（来自 .env）"""
        BACKEND_WS_URL: str = "ws://127.0.0.1:8000/ws/edge"
        EDGE_TOKEN: str = "change-me"
        HA_URL: str = "http://127.0.0.1:8123"
        HA_TOKEN: str = ""
        MI_USER: str = ""
        MI_PASS: str = ""
        MI_PASS_TOKEN: str = ""
        SPEAKER_HARDWARE: str = "L05C"
        SPEAKER_DEVICE_ID: str = ""
        MOCK_MODE: bool = False

        model_config = SettingsConfigDict(
            env_file=str(EDGE_ROOT / ".env"),
            env_file_encoding="utf-8",
            extra="ignore"
        )

except ImportError:
    from pydantic import BaseModel

    class EdgeSettings(BaseModel):
        BACKEND_WS_URL: str = "ws://127.0.0.1:8000/ws/edge"
        EDGE_TOKEN: str = "change-me"
        HA_URL: str = "http://127.0.0.1:8123"
        HA_TOKEN: str = ""
        MI_USER: str = ""
        MI_PASS: str = ""
        MI_PASS_TOKEN: str = ""
        SPEAKER_HARDWARE: str = "L05C"
        SPEAKER_DEVICE_ID: str = ""
        MOCK_MODE: bool = False

        def __init__(self, **data):
            env_data = _parse_env_file(EDGE_ROOT / ".env")
            env_data.update(os.environ)
            combined = {}
            for k, field_info in self.model_fields.items():
                if k in data:
                    combined[k] = data[k]
                elif k in env_data:
                    raw_val = env_data[k]
                    if field_info.annotation is bool or field_info.annotation == bool:
                        combined[k] = str(raw_val).lower() in ("true", "1", "yes")
                    else:
                        combined[k] = raw_val
                else:
                    combined[k] = field_info.default
            super().__init__(**combined)


def load_devices_config() -> dict[str, Any]:
    """加载 devices.yaml 设备映射表"""
    devices_yaml = EDGE_ROOT / "config" / "devices.yaml"
    if not devices_yaml.exists():
        return {}
    with open(devices_yaml, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# 全局单例
settings = EdgeSettings()
devices_config = load_devices_config()
