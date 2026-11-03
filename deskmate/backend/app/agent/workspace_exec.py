"""环境分支先行，电脑分支并行执行，单项失败不阻断其他工作台动作。"""

import asyncio
from typing import TYPE_CHECKING, Any

from app.agent.tools import ToolError

if TYPE_CHECKING:
    from app.runtime import Runtime


class WorkspaceExecutor:
    def __init__(self, runtime: "Runtime") -> None:
        self.runtime = runtime
        self.lock = asyncio.Lock()

    async def start(
        self, workspace: dict[str, Any], goal: str = "", minutes: int | None = None
    ) -> dict[str, Any]:
        async with self.lock:
            rt = self.runtime
            branches: list[dict[str, Any]] = []

            async def call(name: str, args: dict[str, Any]) -> None:
                started = rt.clock.monotonic()
                await rt.trace("workspace", name, args, "running")
                try:
                    await rt.edge.call(name, args)
                    result = {"tool": name, "ok": True}
                except ToolError as exc:
                    result = {"tool": name, "ok": False, "error": exc.code}
                result["elapsed_ms"] = int((rt.clock.monotonic() - started) * 1000)
                branches.append(result)
                await rt.trace("workspace", name, args, "ok" if result["ok"] else "error")

            async def environment() -> None:
                actions = [call("lamp_set", {"on": True, **workspace["lamp"]})]
                ac = rt.settings["ac"]
                temperature = rt.store.data["devices"].get("climate", {}).get("temperature", 0)
                if (
                    workspace["ac"].get("auto_on", True)
                    and temperature >= ac["trigger_on_temp"]
                    and not rt.store.data["devices"].get("ac", {}).get("on")
                ):
                    if ac["auto_rule"] == "auto":
                        actions.append(
                            call(
                                "ac_set",
                                {
                                    "on": True,
                                    "mode": "cool",
                                    "temperature": workspace["ac"].get(
                                        "temperature", ac["summer_temp"]
                                    ),
                                },
                            )
                        )
                    elif ac["auto_rule"] == "ask":
                        rt.expect_confirmation(
                            "开启空调吗",
                            "ac_set",
                            {"on": True, "mode": "cool", "temperature": ac["summer_temp"]},
                        )
                        actions.append(call("voice_expect_reply", {"seconds": 30}))
                await asyncio.gather(*actions)

            async def computer() -> None:
                actions = []
                for item in workspace["items"]:
                    kind = item["type"]
                    if kind in {"vscode", "folder"}:
                        actions.append(
                            call(
                                "open_folder", {"path": item["path"], "in_vscode": kind == "vscode"}
                            )
                        )
                    elif kind == "url":
                        actions.append(call("open_url", {"url": item["url"]}))
                    else:
                        actions.append(call("open_app", {"name": item["name"]}))
                await asyncio.gather(*actions)
                if actions:
                    args = {"layout": workspace["layout"]}
                    if workspace.get("custom_layout"):
                        args["custom"] = workspace["custom_layout"]
                    await call("arrange_windows", args)

            await asyncio.gather(environment(), computer())
            state = rt.focus.start(workspace, goal, minutes)
            if not rt.store.data["presence"]["present"]:
                rt.focus.pause()
                rt.presence.completed.clear()
                await rt.presence.tick()
                state = rt.focus.state
            failed = [branch["tool"] for branch in branches if not branch["ok"]]
            minutes_left = state["remaining_seconds"] // 60
            reply = f"工作台已配置，台灯切入专注模式，预计专注{minutes_left}分钟，加油"
            if failed:
                reply = "工作台部分配置完成，失败项请查看网页，其余操作已完成"
            if rt.confirmation:
                reply += "。室内较热，要开启空调吗"
            await rt.speak(reply)
            return {"focus": state, "branches": branches, "reply": reply, "ok": not failed}
