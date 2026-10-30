"""DeskMate Edge 契约协议定义 (protocol.py)
严格遵循 docs/CONTRACTS.md §1 ~ §3 定义的数据结构与 WebSocket 消息信封
"""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field


def get_current_iso_time() -> str:
    """获取带时区的 ISO 8601 时间戳字符串"""
    return datetime.now(timezone.utc).astimezone().isoformat()


# §1 WebSocket 通用信封
class WsEnvelope(BaseModel):
    """CONTRACTS §1 通用消息信封 (v=2)"""
    v: int = 2
    type: Literal["event", "cmd", "result", "ping", "pong"]
    id: str = Field(default_factory=lambda: str(uuid4()))
    ts: str = Field(default_factory=get_current_iso_time)
    name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


# §2 共享数据结构与设备状态模型
class LampState(BaseModel):
    """米家台灯 1S"""
    online: bool = True
    on: bool = False
    brightness: int = 80
    color_temp: int = 4000


class PlugState(BaseModel):
    """米家智能插座 3"""
    online: bool = True
    on: bool = False
    power_w: float | None = 0.0


class AcState(BaseModel):
    """空调（小爱红外遥控）"""
    online: bool = True
    on: bool = False
    mode: Literal["cool", "heat", "fan", "dry"] = "cool"
    temperature: int = 26
    inferred: bool = True


class MotionState(BaseModel):
    """小米人体传感器 2"""
    online: bool = True
    last_motion_at: str = Field(default_factory=get_current_iso_time)
    illuminance: Literal["strong", "weak"] | None = "weak"


class ClimateState(BaseModel):
    """米家智能温湿度计 3"""
    online: bool = True
    temperature: float = 26.0
    humidity: float = 50.0
    updated_at: str = Field(default_factory=get_current_iso_time)


class SpeakerState(BaseModel):
    """小爱音箱 Play 增强版"""
    online: bool = True
    voice_bridge_ok: bool = True
    ir_supported: bool = True


# §2.2 InputMinute 键鼠与前台活动结构
class InputMinute(BaseModel):
    """每分钟键鼠及系统活动统计（严禁包含按键内容字符）"""
    minute: str = Field(default_factory=get_current_iso_time)
    keys: int = 0
    clicks: int = 0
    scrolls: int = 0
    active_seconds: int = 0
    app_switches: int = 0
    front_process: str = "explorer.exe"
    front_title_category: str = "study"
    activity_rate: float = 0.0


# §3.3 工具元数据定义 (ToolSpec)
class ToolParameter(BaseModel):
    type: str = "string"
    description: str = ""
    required: bool = False
    enum: list[str] | None = None
    default: Any = None


class ToolSpec(BaseModel):
    """工具规范，向云端注册"""
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    timeout_s: int = 10


# §3.1 edge.hello 握手载荷
class EdgeHelloPayload(BaseModel):
    edge_version: str = "0.2.0"
    platform: str = "windows"
    dpi_scale: float = 1.0
    devices: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)


# §3.2 指令与返回载荷
class ToolCallPayload(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResultPayload(BaseModel):
    call_id: str
    ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
