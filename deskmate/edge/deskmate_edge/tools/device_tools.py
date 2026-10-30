"""DeskMate Edge 智能家居与外设控制工具集 (device_tools.py)
实现 CONTRACTS §3.3 中环境 Agent 与音箱控制工具规范
通过 Home Assistant REST API 与 MiService 驱动实体硬件
"""

import asyncio
import json
import logging
from typing import Any, Literal
import httpx
from pydantic import BaseModel, Field
from ..config import devices_config, settings
from ..protocol import AcState, LampState, PlugState
from ..tool_registry import registry

logger = logging.getLogger("deskmate_edge.device_tools")

# 设备实体配置
lamp_conf = devices_config.get("lamp", {})
plug_conf = devices_config.get("plug", {})
speaker_conf = devices_config.get("speaker", {})

lamp_entity = lamp_conf.get("entity_id", "light.desk_lamp")
plug_entity = plug_conf.get("entity_id", "switch.desk_plug")
speaker_media_player = speaker_conf.get("entity_id", "media_player.xiaomi_speaker")
notify_tts = speaker_conf.get("tts_notify_entity", "notify.xiaomi_play_text")
notify_directive = speaker_conf.get("directive_notify_entity", "notify.xiaomi_execute_text_directive")

# 内部模拟缓存（若未连接 HA 时的降级状态）
_mock_lamp = LampState(online=True, on=False, brightness=80, color_temp=4000)
_mock_plug = PlugState(online=True, on=False, power_w=0.0)
_mock_ac = AcState(online=True, on=False, mode="cool", temperature=26, inferred=True)


async def call_ha_service(domain: str, service: str, payload: dict[str, Any]) -> dict[str, Any]:
    """统一调用 Home Assistant REST API 服务"""
    if not settings.HA_TOKEN or settings.MOCK_MODE:
        logger.info(f"[Mock HA] 调用服务 {domain}/{service}: {payload}")
        return {}

    url = f"{settings.HA_URL.rstrip('/')}/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {settings.HA_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except Exception as e:
            logger.error(f"调用 HA 服务 {domain}/{service} 异常: {e}")
            raise ConnectionError(f"HA_SERVICE_ERROR: {e}")


# 入参 Schema 定义

class LampSetArgs(BaseModel):
    on: bool | None = Field(default=None, description="台灯开关状态")
    brightness: int | None = Field(default=None, ge=1, le=100, description="亮度百分比 (1-100)")
    color_temp: int | None = Field(default=None, ge=2600, le=5000, description="色温开尔文 (2600-5000K)")


class LampEffectArgs(BaseModel):
    effect: Literal["breathe", "blink"] = Field(description="效果类型：breathe (呼吸律动) | blink (闪烁)")
    duration_s: int = Field(default=10, description="持续秒数")


class PlugSetArgs(BaseModel):
    on: bool = Field(description="插座通断电状态")


class AcSetArgs(BaseModel):
    on: bool | None = Field(default=None, description="空调开关")
    mode: Literal["cool", "heat", "fan", "dry"] | None = Field(default="cool", description="空调模式")
    temperature: int | None = Field(default=None, ge=16, le=30, description="目标温度 (16-30℃)")


class SpeakerTtsArgs(BaseModel):
    text: str = Field(description="播报文本，口语化，严禁超过 60 字")
    interrupt: bool = Field(default=True, description="是否打断当前正在播放的音频")


class SpeakerExecDirectiveArgs(BaseModel):
    directive: str = Field(description="下发给小爱的自然语言指令，如'把空调调到26度'")


# 注册工具

@registry.register(
    name="lamp_set",
    description="控制台灯开关、亮度百分比与色温",
    args_schema=LampSetArgs,
    timeout_s=5
)
async def tool_lamp_set(on: bool | None = None, brightness: int | None = None, color_temp: int | None = None) -> dict[str, Any]:
    if on is False:
        await call_ha_service("light", "turn_off", {"entity_id": lamp_entity})
        _mock_lamp.on = False
    else:
        payload: dict[str, Any] = {"entity_id": lamp_entity}
        if brightness is not None:
            # 转换为 1-255
            payload["brightness"] = int(brightness * 2.55)
            _mock_lamp.brightness = brightness
        if color_temp is not None:
            # 硬件范围保护
            safe_temp = max(2600, min(5000, color_temp))
            payload["color_temp_kelvin"] = safe_temp
            _mock_lamp.color_temp = safe_temp
        await call_ha_service("light", "turn_on", payload)
        _mock_lamp.on = True

    return _mock_lamp.model_dump()


@registry.register(
    name="lamp_effect",
    description="触发台灯 10 秒柔和呼吸光律动（L1 疲劳干预或专注顺延提示）",
    args_schema=LampEffectArgs,
    timeout_s=15
)
async def tool_lamp_effect(effect: str = "breathe", duration_s: int = 10) -> dict[str, Any]:
    logger.info(f"触发台灯动效: {effect}，持续 {duration_s} 秒")
    if effect == "breathe":
        # 呼吸律动：先暗后亮
        await call_ha_service("light", "turn_on", {"entity_id": lamp_entity, "brightness": 60})
        await asyncio.sleep(2)
        await call_ha_service("light", "turn_on", {"entity_id": lamp_entity, "brightness": 204})
    return {}


@registry.register(
    name="plug_set",
    description="控制米家智能插座通电/断电（联动桌面外设风扇/挂灯）",
    args_schema=PlugSetArgs,
    timeout_s=5
)
async def tool_plug_set(on: bool) -> dict[str, Any]:
    service = "turn_on" if on else "turn_off"
    await call_ha_service("switch", service, {"entity_id": plug_entity})
    _mock_plug.on = on
    return _mock_plug.model_dump()


@registry.register(
    name="ac_set",
    description="通过小爱音箱红外遥控控制空调开关、模式与设定温度",
    args_schema=AcSetArgs,
    timeout_s=8
)
async def tool_ac_set(on: bool | None = None, mode: str | None = "cool", temperature: int | None = None) -> dict[str, Any]:
    cmd_text = ""
    if on is False:
        cmd_text = "把空调关了"
        _mock_ac.on = False
    elif on is True and temperature is not None:
        cmd_text = f"把空调调到{temperature}度"
        _mock_ac.on = True
        _mock_ac.temperature = temperature
    elif temperature is not None:
        cmd_text = f"把空调调到{temperature}度"
        _mock_ac.temperature = temperature
    else:
        cmd_text = "把空调打开"
        _mock_ac.on = True

    if cmd_text:
        # 通过 HA notify 发送 execute_text_directive
        await call_ha_service("notify", "send_message", {
            "entity_id": notify_directive,
            "message": json.dumps([cmd_text, False])
        })

    return _mock_ac.model_dump()


@registry.register(
    name="speaker_tts",
    description="让小爱音箱进行自定义文本语音播报（严格 ≤ 60字，无 Markdown）",
    args_schema=SpeakerTtsArgs,
    timeout_s=6
)
async def tool_speaker_tts(text: str, interrupt: bool = True) -> dict[str, Any]:
    clean_text = text.strip()[:60]
    if interrupt:
        # 先打断音箱当前可能在播放的声音
        await call_ha_service("media_player", "media_stop", {"entity_id": speaker_media_player})

    await call_ha_service("notify", "send_message", {
        "entity_id": notify_tts,
        "message": clean_text
    })
    return {}


@registry.register(
    name="speaker_stop",
    description="打断小爱音箱当前的音频播放或语音输出",
    timeout_s=3
)
async def tool_speaker_stop() -> dict[str, Any]:
    await call_ha_service("media_player", "media_stop", {"entity_id": speaker_media_player})
    return {}


@registry.register(
    name="speaker_exec_directive",
    description="下发语音文本指令由小爱音箱原生执行（如红外遥控）",
    args_schema=SpeakerExecDirectiveArgs,
    timeout_s=8
)
async def tool_speaker_exec_directive(directive: str) -> dict[str, Any]:
    await call_ha_service("notify", "send_message", {
        "entity_id": notify_directive,
        "message": json.dumps([directive, False])
    })
    return {}
