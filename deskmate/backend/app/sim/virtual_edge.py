"""仅在内存执行全部工具，模拟状态与通知，绝不操作宿主电脑。"""

from copy import deepcopy
from typing import Any

from app.agent.tools import TOOL_SCHEMAS, ToolError, spec
from app.clock import Clock, iso
from app.engine.state_store import StateStore


class VirtualEdge:
    def __init__(self, store: StateStore, clock: Clock) -> None:
        self.store, self.clock = store, clock
        self.clipboard = ""
        self.windows: list[dict[str, Any]] = []
        self.notes: dict[str, str] = {}
        self.expect_until = 0.0
        self.config: dict[str, Any] = {}
        self.fail_tools: set[str] = set()
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.reset_devices()

    def reset_devices(self) -> None:
        self.store.update(
            devices={
                "lamp": {"online": True, "on": False, "brightness": 80, "color_temp": 4000},
                "plug": {"online": True, "on": True, "power_w": 12.5},
                "ac": {
                    "online": True,
                    "on": False,
                    "mode": "cool",
                    "temperature": 26,
                    "inferred": True,
                },
                "motion": {
                    "online": True,
                    "last_motion_at": iso(self.clock),
                    "illuminance": "weak",
                },
                "climate": {
                    "online": True,
                    "temperature": 26.5,
                    "humidity": 55.0,
                    "updated_at": iso(self.clock),
                },
                "speaker": {"online": True, "voice_bridge_ok": True, "ir_supported": True},
            }
        )

    @property
    def tools(self) -> dict[str, dict[str, Any]]:
        return {name: spec(name, schema) for name, (schema, _) in TOOL_SCHEMAS.items()}

    async def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name in self.fail_tools:
            raise ToolError("DEVICE_OFFLINE")
        self.calls.append((name, deepcopy(args)))
        self.calls = self.calls[-200:]
        if name in {"lamp_set", "ac_set", "plug_set"}:
            device = name.removesuffix("_set")
            state = deepcopy(self.store.data["devices"][device])
            if not state["online"]:
                raise ToolError("DEVICE_OFFLINE")
            state.update(args)
            self.store.device(device, state)
            return state
        if name in {"speaker_tts", "show_win_toast"}:
            await self.store.web.publish(
                "notify",
                {
                    "level": "info",
                    "title": args.get("title", "虚拟小爱播报"),
                    "text": args.get("text", args.get("message", "")),
                    "action": "none",
                },
            )
        elif name == "voice_expect_reply":
            self.expect_until = self.clock.monotonic() + args.get("seconds", 30)
        elif name == "edge_config_update":
            self.config.update(args)
        elif name == "speaker_exec_directive":
            await self.store.web.publish(
                "notify",
                {
                    "level": "info",
                    "title": "虚拟红外指令",
                    "text": args["directive"],
                    "action": "none",
                },
            )
        elif name in {"open_app", "open_folder", "open_url"}:
            target = args.get("path", args.get("name", args.get("url", "")))
            self.windows.append(
                {
                    "title": target,
                    "process": "Code.exe" if args.get("in_vscode") else "explorer.exe",
                    "rect": [0, 0, 1280, 720],
                }
            )
            return {"opened": target} if name != "open_url" else {}
        elif name == "arrange_windows":
            for index, window in enumerate(self.windows):
                window["rect"] = [
                    0 if index % 2 == 0 else 768,
                    0,
                    768 if index % 2 == 0 else 512,
                    720,
                ]
            return {"arranged_count": len(self.windows)}
        elif name == "get_open_windows":
            return {"windows": deepcopy(self.windows)}
        elif name == "find_files":
            return (
                {
                    "files": [
                        {
                            "path": "D:\\Projects\\软件工程大作业",
                            "name": "软件工程大作业",
                            "is_dir": True,
                        }
                    ]
                }
                if "软工" in args["keyword"] or ("软件" in args["keyword"])
                else {"files": []}
            )
        elif name in {"read_clipboard", "get_selected_text"}:
            return {"text": self.clipboard[:8000]}
        elif name == "write_clipboard":
            self.clipboard = args["text"]
        elif name == "take_screenshot":
            # 固定 1x1 PNG 是协议测试占位图，不冒充报错截图或真实桌面。
            return {
                "image_b64": (
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwC"
                    "AAAAC0lEQVR42mP8/x8AAwMCAO+a8foAAAAASUVORK5CYII="
                ),
                "mime": "image/png",
            }
        elif name == "create_note":
            self.notes[args["title"]] = args["content"]
            return {"path": f"D:\\DeskMateNotes\\{args['title']}.md"}
        elif name not in {"lamp_effect", "speaker_stop"}:
            if name not in TOOL_SCHEMAS:
                raise ToolError("NOT_ALLOWED")
        return {}
