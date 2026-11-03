"""单一运行环境的内存状态中心，每次增量包含完整顶层对象。"""

from copy import deepcopy
from typing import Any

from app.clock import Clock, iso
from app.ws.web_hub import WebHub


class StateStore:
    def __init__(self, clock: Clock, web: WebHub, demo: bool) -> None:
        self.clock, self.web = clock, web
        self.data: dict[str, Any] = {
            "edge_online": False,
            "demo_mode": demo,
            "devices": {},
            "presence": {
                "present": True,
                "since": iso(clock),
                "sources": {"motion": True, "keyboard_mouse": True, "screen_locked": False},
            },
            "focus": {
                "state": "idle",
                "session_id": None,
                "workspace_name": "",
                "goal": "",
                "phase_started_at": None,
                "phase_ends_at": None,
                "remaining_seconds": 0,
                "pomodoro_index": 1,
                "flow_extensions": 0,
                "focus_seconds_today": 0,
            },
            "fatigue": {
                "level": 0,
                "score": 0.0,
                "in_flow": False,
                "reasons": [],
                "updated_at": iso(clock),
            },
            "current_input_stats": None,
        }

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self.data)

    def update(self, **changed: Any) -> None:
        self.data.update(deepcopy(changed))
        self.web.patch(deepcopy(changed))

    def device(self, name: str, value: dict[str, Any]) -> None:
        devices = deepcopy(self.data["devices"])
        devices[name] = deepcopy(value)
        self.update(devices=devices)
