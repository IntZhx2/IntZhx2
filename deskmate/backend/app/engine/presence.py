"""融合移动、键鼠空闲和锁屏信号，执行可重试的离座阶梯动作。"""

import logging
from copy import deepcopy
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from app.clock import iso, parse_time

if TYPE_CHECKING:
    from app.runtime import Runtime

logger = logging.getLogger(__name__)


class PresenceEngine:
    def __init__(self, runtime: "Runtime") -> None:
        self.runtime = runtime
        self.last_motion = runtime.clock.now()
        self.last_input = runtime.clock.now()
        self.locked = False
        self.away_since = None
        self.completed: set[str] = set()
        self.saved: dict[str, Any] = {}
        self.pending_return = False
        self.return_minutes = 0

    def pc_session(self, payload: dict[str, Any]) -> None:
        if type(payload.get("locked")) is not bool or type(payload.get("idle_seconds")) is not int:
            raise ValueError("无效 pc.session")
        if payload["idle_seconds"] < 0:
            raise ValueError("空闲秒数不可为负数")
        self.locked = payload["locked"]
        self.last_input = self.runtime.clock.now() - timedelta(seconds=payload["idle_seconds"])

    async def tick(self) -> None:
        rt, now = self.runtime, self.runtime.clock.now()
        settings = rt.settings
        idle = (now - self.last_input).total_seconds()
        motion_age = (now - self.last_motion).total_seconds()
        confirmed_absent = self.locked or (
            idle >= settings["absent_confirm_min"] * 60
            and motion_age >= settings["absent_confirm_min"] * 60
        )
        positive = not self.locked and (
            idle < rt.config.keyboard_recent_s or motion_age < settings["motion_window_min"] * 60
        )
        was_present = rt.store.data["presence"]["present"]
        present = False if confirmed_absent else (True if positive else was_present)
        sources = {
            "motion": motion_age < settings["motion_window_min"] * 60,
            "keyboard_mouse": idle < rt.config.keyboard_recent_s,
            "screen_locked": self.locked,
        }
        if present == was_present and sources != rt.store.data["presence"]["sources"]:
            rt.store.update(presence={**rt.store.data["presence"], "sources": sources})
        if present != was_present:
            rt.store.update(
                presence={
                    "present": present,
                    "since": iso(rt.clock),
                    "sources": {
                        "motion": motion_age < settings["motion_window_min"] * 60,
                        "keyboard_mouse": idle < rt.config.keyboard_recent_s,
                        "screen_locked": self.locked,
                    },
                }
            )
            if not present:
                self.away_since = now
                self.completed.clear()
                self.saved = deepcopy(rt.store.data["devices"])
                rt.focus.pause()
                if rt.wellbeing:
                    rt.wellbeing.on_user_left(self.locked)
            else:
                rt.focus.resume()
                self.return_minutes = (rt.focus.state["remaining_seconds"] + 59) // 60
                self.pending_return = True
                self.away_since = None
                self.completed.clear()
        # 返回动作失败时继续重试，避免一次设备错误永久丢失恢复。
        if present and self.pending_return:
            if "return_lamp" not in self.completed:
                lamp = self.saved.get("lamp", {})
                args = {k: lamp[k] for k in ("on", "brightness", "color_temp") if k in lamp}
                if rt.focus.state["state"] == "focusing":
                    args.update(on=True)
                if await self.action("lamp_set", args):
                    self.completed.add("return_lamp")
            if "return_plug" not in self.completed:
                if await self.action(
                    "plug_set", {"on": self.saved.get("plug", {}).get("on", False)}
                ):
                    self.completed.add("return_plug")
            if {"return_lamp", "return_plug"} <= self.completed:
                await self.action(
                    "speaker_tts", {"text": f"欢迎回来，番茄钟继续，还剩{self.return_minutes}分钟"}
                )
                self.pending_return = False
        if present:
            if present != was_present and rt.focus.state["state"] == "idle":
                lamp = rt.store.data["devices"].get("lamp", {})
                motion = rt.store.data["devices"].get("motion", {})
                local = now.astimezone(ZoneInfo(rt.config.tz)).strftime("%H:%M")
                if not lamp.get("on") and (
                    motion.get("illuminance") == "weak" or local >= settings["auto_lamp_after"]
                ):
                    await self.action("lamp_set", {"on": True, **settings["relax_lamp"]})
            return
        if self.away_since is None:
            self.away_since = parse_time(rt.store.data["presence"]["since"])
        minutes = (now - self.away_since).total_seconds() / 60
        # 锁屏立即伴眠；其余离座在确认时立即暂停，灯光遵循配置延迟。
        sleep_due = self.locked or minutes >= max(
            0, settings["absent_lamp_sleep_min"] - settings["absent_confirm_min"]
        )
        actions: list[tuple[str, str, dict[str, Any]]] = []
        if minutes >= settings["absent_lamp_off_min"]:
            actions.extend(
                [("lamp_off", "lamp_set", {"on": False}), ("plug_off", "plug_set", {"on": False})]
            )
        elif sleep_due:
            actions.append(("sleep", "lamp_set", {"on": True, **settings["sleep_lamp"]}))
        if minutes >= settings["absent_ac_off_min"]:
            actions.append(("ac_off", "ac_set", {"on": False}))
        for key, tool, args in actions:
            if key not in self.completed and await self.action(tool, args):
                self.completed.add(key)

    async def action(self, tool: str, args: dict[str, Any]) -> bool:
        try:
            await self.runtime.edge.call(tool, args)
            return True
        except Exception:
            logger.warning("在座动作失败，下一轮重试: %s", tool)
            return False
