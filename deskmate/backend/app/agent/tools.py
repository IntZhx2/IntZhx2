"""固定权限边界内接受 Edge 动态工具规格，校验所有调用。"""

import re
from typing import Any

from jsonschema import Draft202012Validator

from app.schemas.contracts import safe_url


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def string(**kwargs: Any) -> dict[str, Any]:
    return {"type": "string", "maxLength": 8000, **kwargs}


def integer(low: int, high: int) -> dict[str, Any]:
    return {"type": "integer", "minimum": low, "maximum": high}


BOOL = {"type": "boolean"}
S = string()
TOOL_SCHEMAS: dict[str, tuple[dict[str, Any], int]] = {
    "lamp_set": (
        obj({"on": BOOL, "brightness": integer(1, 100), "color_temp": integer(2500, 4800)}),
        5,
    ),
    "lamp_effect": (
        obj(
            {"effect": string(enum=["breathe", "blink"]), "duration_s": integer(1, 15)}, ["effect"]
        ),
        15,
    ),
    "ac_set": (
        obj(
            {
                "on": BOOL,
                "mode": string(enum=["cool", "heat", "fan", "dry"]),
                "temperature": integer(16, 30),
            }
        ),
        8,
    ),
    "plug_set": (obj({"on": BOOL}, ["on"]), 5),
    "speaker_tts": (obj({"text": S, "interrupt": BOOL}, ["text"]), 6),
    "speaker_stop": (obj({}), 3),
    "speaker_exec_directive": (obj({"directive": S}, ["directive"]), 8),
    "voice_expect_reply": (obj({"seconds": integer(1, 30)}), 3),
    "open_app": (obj({"name": string(maxLength=100)}, ["name"]), 8),
    "open_folder": (obj({"path": string(maxLength=1024), "in_vscode": BOOL}, ["path"]), 8),
    "open_url": (obj({"url": string(maxLength=2048)}, ["url"]), 5),
    "find_files": (
        obj(
            {"keyword": string(maxLength=100), "directory": S, "limit": integer(1, 20)}, ["keyword"]
        ),
        10,
    ),
    "arrange_windows": (
        obj(
            {
                "layout": string(
                    enum=["code_left_browser_right", "maximize", "split_half", "custom"]
                ),
                "custom": {"type": "object"},
            },
            ["layout"],
        ),
        10,
    ),
    "get_open_windows": (obj({}), 5),
    "read_clipboard": (obj({}), 3),
    "write_clipboard": (obj({"text": S}, ["text"]), 3),
    "get_selected_text": (obj({}), 3),
    "take_screenshot": (
        obj(
            {
                "target": string(enum=["screen", "latest_desktop_file"]),
                "max_side": integer(64, 1280),
            }
        ),
        10,
    ),
    "create_note": (obj({"title": string(maxLength=100), "content": S}, ["title", "content"]), 5),
    "show_win_toast": (
        obj({"title": string(maxLength=100), "message": S}, ["title", "message"]),
        4,
    ),
    "edge_config_update": (
        obj(
            {
                k: {"type": "array", "items": S}
                for k in (
                    "app_whitelist",
                    "study_apps",
                    "entertainment_apps",
                    "voice_takeover_prefixes",
                )
            }
        ),
        5,
    ),
}
ENV_TOOLS = {"lamp_set", "lamp_effect", "ac_set", "plug_set"}
PC_TOOLS = {
    "open_app",
    "open_folder",
    "open_url",
    "find_files",
    "arrange_windows",
    "get_open_windows",
    "read_clipboard",
    "write_clipboard",
    "get_selected_text",
    "create_note",
    "show_win_toast",
}


class ToolError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code, self.message = code, message or code
        super().__init__(self.message)


def spec(name: str, schema: dict[str, Any], description: str = "") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {"name": name, "description": description or name, "parameters": schema},
    }


def validate_call(name: str, args: dict[str, Any], settings: dict[str, Any]) -> None:
    if name not in TOOL_SCHEMAS:
        raise ToolError("NOT_ALLOWED")
    if list(Draft202012Validator(TOOL_SCHEMAS[name][0]).iter_errors(args)):
        raise ToolError("BAD_ARGS")
    if name == "open_url":
        try:
            safe_url(args["url"])
        except ValueError as exc:
            raise ToolError("BAD_ARGS") from exc
    if name == "open_app":
        requested = args["name"].casefold().removesuffix(".exe")
        allowed = {v.casefold().removesuffix(".exe") for v in settings["app_whitelist"]}
        if requested not in allowed:
            raise ToolError("NOT_ALLOWED", "应用不在白名单")
    if name in {"open_folder", "find_files"}:
        path = args.get("path", args.get("directory", "D:\\"))
        if not re.match(r"^[A-Za-z]:[\\/]", path) or any(
            part == ".." for part in re.split(r"[\\/]", path)
        ):
            raise ToolError("NOT_ALLOWED", "仅接受本地绝对路径，不接受网络和父目录跳转")
    if name == "create_note" and re.search(r'[\\/:*?"<>|]', args["title"]):
        raise ToolError("BAD_ARGS", "笔记标题不可含路径")


def speech(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`#*_>\[\]]", "", text).strip()
    return (text or "处理完成，详细结果请查看网页")[:60]
