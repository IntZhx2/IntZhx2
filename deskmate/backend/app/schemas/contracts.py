"""严格校验共享契约及工具参数，拒绝多余字段和无效设备值。"""

from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.clock import parse_time


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LampArgs(StrictModel):
    on: bool | None = None
    brightness: int | None = Field(default=None, ge=1, le=100)
    color_temp: int | None = Field(default=None, ge=2500, le=4800)


class AcArgs(StrictModel):
    on: bool | None = None
    mode: Literal["cool", "heat", "fan", "dry"] | None = None
    temperature: int | None = Field(default=None, ge=16, le=30)


class PlugArgs(StrictModel):
    on: bool


class LampPreset(StrictModel):
    brightness: int = Field(ge=1, le=100)
    color_temp: int = Field(ge=2500, le=4800)


class AcPreset(StrictModel):
    auto_on: bool = True
    temperature: int = Field(default=26, ge=16, le=30)


def safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username:
        raise ValueError("仅支持 HTTP(S) 网址")
    return value


class WorkspaceItem(StrictModel):
    type: Literal["vscode", "folder", "url", "app"]
    path: str | None = Field(default=None, max_length=1024)
    url: str | None = Field(default=None, max_length=2048)
    name: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def check_item(self) -> "WorkspaceItem":
        field = {"vscode": "path", "folder": "path", "url": "url", "app": "name"}[self.type]
        if not getattr(self, field):
            raise ValueError(f"{self.type} 缺少 {field}")
        if self.type == "url":
            safe_url(self.url)
        return self


class WorkspaceIn(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    focus_minutes: int = Field(default=45, ge=1, le=240)
    lamp: LampPreset = Field(default_factory=lambda: LampPreset(brightness=80, color_temp=4000))
    ac: AcPreset = Field(default_factory=AcPreset)
    items: list[WorkspaceItem] = Field(default_factory=list, max_length=20)
    layout: Literal["code_left_browser_right", "maximize", "split_half", "custom"] = (
        "code_left_browser_right"
    )
    custom_layout: dict[str, Any] | None = None

    @model_validator(mode="after")
    def custom_required(self) -> "WorkspaceIn":
        if self.layout == "custom" and not self.custom_layout:
            raise ValueError("自定义布局需要 custom_layout")
        return self


class InputMinute(StrictModel):
    minute: str
    keys: int = Field(ge=0)
    clicks: int = Field(ge=0)
    scrolls: int = Field(ge=0)
    active_seconds: int = Field(ge=0, le=60)
    app_switches: int = Field(ge=0)
    front_process: str = Field(max_length=100)
    front_title_category: str = Field(max_length=40)
    activity_rate: float = Field(ge=0, allow_inf_nan=False)

    @field_validator("minute")
    @classmethod
    def timezone_required(cls, value: str) -> str:
        return parse_time(value).isoformat()


class AcSettings(StrictModel):
    auto_rule: Literal["auto", "ask", "off"]
    summer_temp: int = Field(ge=16, le=30)
    trigger_on_temp: float = Field(ge=16, le=45, allow_inf_nan=False)
    high_humidity_trigger: float = Field(ge=0, le=100, allow_inf_nan=False)


class WellbeingSettings(StrictModel):
    l1_score: int = Field(ge=0, le=100)
    l2_score: int = Field(ge=0, le=100)
    l3_score: int = Field(ge=0, le=100)
    max_continuous_focus_min: int = Field(ge=1, le=240)
    cooldown_min: int = Field(ge=1, le=120)
    flow_extension_min: int = Field(ge=1, le=60)
    max_flow_extensions: int = Field(ge=0, le=2)

    @model_validator(mode="after")
    def ordered(self) -> "WellbeingSettings":
        if not self.l1_score < self.l2_score < self.l3_score:
            raise ValueError("疲劳阈值需要 L1 < L2 < L3")
        return self


class Settings(StrictModel):
    focus_lamp: LampPreset
    relax_lamp: LampPreset
    sleep_lamp: LampPreset
    auto_lamp_after: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    motion_window_min: float = Field(gt=0, le=60, allow_inf_nan=False)
    absent_confirm_min: float = Field(gt=0, le=60, allow_inf_nan=False)
    absent_lamp_sleep_min: float = Field(ge=0, le=60, allow_inf_nan=False)
    absent_lamp_off_min: float = Field(gt=0, le=120, allow_inf_nan=False)
    absent_ac_off_min: float = Field(gt=0, le=240, allow_inf_nan=False)
    ac: AcSettings
    wellbeing: WellbeingSettings
    app_whitelist: list[str] = Field(max_length=100)
    study_categories: list[str] = Field(max_length=100)
    entertainment_categories: list[str] = Field(max_length=100)
    voice_takeover_prefixes: list[str] = Field(max_length=100)

    @model_validator(mode="after")
    def ordered(self) -> "Settings":
        if not self.absent_lamp_sleep_min <= self.absent_lamp_off_min <= self.absent_ac_off_min:
            raise ValueError("离座阈值需满足伴眠 ≤ 关灯 ≤ 关空调")
        return self


def merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    import copy

    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = value
    return result
