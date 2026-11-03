"""验证工作台、离座、计时及 C 接口接线，避免把模拟当作真机验收。"""

import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.agent.tools import TOOL_SCHEMAS, ToolError
from app.clock import iso


async def test_workspace_parallel_failure_and_threshold(rt):
    workspace = rt.workspaces()[0]
    workspace["items"] = [
        {"type": "folder", "path": "D:\\课程"},
        {"type": "url", "url": "https://example.org"},
        {"type": "app", "name": "Code.exe"},
    ]
    rt.store.device("climate", {"online": True, "temperature": 27.4, "humidity": 55.0})
    rt.virtual.fail_tools.add("open_url")
    result = await rt.workspace.start(workspace, "完成作业", 25)
    assert result["ok"] is False
    assert result["focus"]["remaining_seconds"] == 25 * 60
    assert any(item["tool"] == "open_url" and not item["ok"] for item in result["branches"])
    names = [name for name, _ in rt.virtual.calls]
    assert "ac_set" not in names
    assert names.index("arrange_windows") > names.index("open_app")
    assert rt.store.data["devices"]["lamp"]["brightness"] == 80
    rt.store.device("climate", {"online": True, "temperature": 27.5, "humidity": 55.0})
    await rt.workspace.start(workspace)
    assert rt.store.data["devices"]["ac"]["on"]
    assert rt.store.data["devices"]["ac"]["inferred"]


async def test_workspace_env_and_pc_really_overlap(rt, monkeypatch):
    workspace = rt.workspaces()[0]
    workspace["items"] = [{"type": "folder", "path": "D:\\作业"}]
    arrived: set[str] = set()
    both = asyncio.Event()
    original = rt.edge.call

    async def call(name, args, timeout=None):
        if name in {"lamp_set", "open_folder"}:
            arrived.add(name)
            if len(arrived) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), 0.3)
        return await original(name, args, timeout)

    monkeypatch.setattr(rt.edge, "call", call)
    await rt.workspace.start(workspace)
    assert both.is_set()


async def test_presence_cascade_return_and_retry(rt):
    await rt.workspace.start(rt.workspaces()[0], minutes=45)
    rt.clock.advance(60)
    rt.virtual.fail_tools.add("lamp_set")
    await rt.inject("lock", True)
    assert rt.focus.state["state"] == "paused"
    assert "sleep" not in rt.presence.completed
    rt.virtual.fail_tools.clear()
    await rt.tick()
    assert rt.store.data["devices"]["lamp"]["color_temp"] == 2500
    rt.clock.advance(15 * 60)
    await rt.tick()
    assert not rt.store.data["devices"]["lamp"]["on"]
    assert not rt.store.data["devices"]["plug"]["on"]
    rt.clock.advance(15 * 60)
    await rt.tick()
    assert not rt.store.data["devices"]["ac"]["on"]
    rt.virtual.fail_tools.add("lamp_set")
    await rt.inject("lock", False)
    assert rt.focus.state["state"] == "focusing"
    assert rt.presence.pending_return
    rt.virtual.fail_tools.clear()
    await rt.tick()
    assert not rt.presence.pending_return
    assert rt.focus.state["remaining_seconds"] == 44 * 60
    assert rt.store.data["devices"]["lamp"]["brightness"] == 80
    assert rt.store.data["devices"]["plug"]["on"]


async def test_presence_idle_and_scroll(rt):
    rt.store.update(demo_mode=False)
    rt.presence.last_motion = rt.clock.now() - timedelta(minutes=10)
    rt.presence.last_input = rt.clock.now() - timedelta(seconds=179)
    await rt.presence.tick()
    assert rt.store.data["presence"]["present"]
    rt.clock.advance(1)
    await rt.presence.tick()
    assert not rt.store.data["presence"]["present"]
    await rt.event(
        "pc.input_stats",
        {
            "minute": iso(rt.clock),
            "keys": 0,
            "clicks": 0,
            "scrolls": 10,
            "active_seconds": 10,
            "app_switches": 0,
            "front_process": "Acrobat.exe",
            "front_title_category": "reading",
            "activity_rate": 10.0,
        },
    )
    await rt.presence.tick()
    assert rt.store.data["presence"]["present"]
    with pytest.raises(ValidationError):
        await rt.event("pc.input_stats", {"minute": iso(rt.clock), "key_contents": "secret"})


async def test_demo_inject_stats_voice_and_leave(rt):
    await rt.inject("typing_rate", 180)
    rt.clock.advance(60)
    await rt.tick()
    assert rt.store.data["current_input_stats"]["activity_rate"] == 180
    await rt.inject("temperature", 29)
    assert rt.store.data["devices"]["climate"]["temperature"] == 29
    result = await rt.inject("voice", "开灯")
    assert result["ok"]
    await rt.inject("leave", None)
    assert not rt.store.data["presence"]["present"]
    rt.clock.advance(60)
    await rt.tick()
    assert rt.store.data["current_input_stats"]["keys"] == 0
    await rt.inject("motion", None)
    assert rt.store.data["presence"]["present"]


async def test_focus_full_cycle_and_c_flow_hook(rt):
    class CStub:
        def check_flow_extension(self, session_id):
            return True

    rt.focus.wellbeing = CStub()
    rt.focus.start(rt.workspaces()[0], "", 1)
    rt.clock.advance(60)
    assert rt.focus.tick(rt.settings) == "flow_extended"
    assert rt.focus.state["flow_extensions"] == 1
    rt.clock.advance(10 * 60)
    assert rt.focus.tick(rt.settings) == "flow_extended"
    rt.clock.advance(10 * 60)
    assert rt.focus.tick(rt.settings) == "break"
    rt.clock.advance(rt.config.break_minutes * 60)
    assert rt.focus.tick(rt.settings) == "focus"
    assert rt.focus.state["pomodoro_index"] == 2
    result = rt.focus.stop()
    assert result["flow_extensions"] == 2 and result["pomodoros_done"] == 1


async def test_c_actions_are_only_adapted(rt):
    rt.focus.start(rt.workspaces()[0], "", 1)
    await rt.apply_wellbeing_action({"action_type": "lamp_breathe"})
    assert rt.virtual.calls[-1][0] == "lamp_effect"
    await rt.apply_wellbeing_action({"action_type": "force_break", "speech_text": "休息一下"})
    assert rt.focus.state["state"] == "short_break"


async def test_start_while_away_keeps_session_paused(rt):
    await rt.inject("lock", True)
    result = await rt.workspace.start(rt.workspaces()[0])
    assert result["focus"]["state"] == "paused"
    assert rt.store.data["devices"]["lamp"]["brightness"] == 10


async def test_fractional_ticks_do_not_lose_focus_time(rt):
    rt.focus.start(rt.workspaces()[0], "", 1)
    for _ in range(10):
        rt.clock.advance(0.6)
        rt.focus.tick(rt.settings)
    assert rt.focus.stop()["focus_seconds"] == 6


async def test_today_counter_resets_at_local_midnight(rt):
    # 当前为北京时间20点，推进至23:59:50后启动。
    rt.clock.advance(4 * 3600 - 10)
    rt.focus.start(rt.workspaces()[0], "", 1)
    rt.clock.advance(20)
    rt.focus.tick(rt.settings)
    assert rt.focus.state["focus_seconds_today"] == 10
    assert rt.focus.stop()["focus_seconds"] == 20


async def test_focus_does_not_end_before_the_deadline(rt):
    rt.focus.start(rt.workspaces()[0], "", 1)
    rt.clock.advance(59.8)
    assert rt.focus.tick(rt.settings) is None
    assert rt.focus.state["state"] == "focusing"
    rt.clock.advance(0.2)
    assert rt.focus.tick(rt.settings) == "break"
    assert rt.focus.stop()["focus_seconds"] == 60


VIRTUAL_CASES = [
    ("lamp_set", {"on": True}),
    ("lamp_effect", {"effect": "breathe"}),
    ("ac_set", {"mode": "cool", "temperature": 25}),
    ("plug_set", {"on": False}),
    ("speaker_tts", {"text": "你好"}),
    ("speaker_stop", {}),
    ("speaker_exec_directive", {"directive": "打开空调"}),
    ("voice_expect_reply", {"seconds": 30}),
    ("open_app", {"name": "Code.exe"}),
    ("open_folder", {"path": "D:\\中文目录"}),
    ("open_url", {"url": "https://example.org"}),
    ("find_files", {"keyword": "软工"}),
    ("arrange_windows", {"layout": "maximize"}),
    ("get_open_windows", {}),
    ("read_clipboard", {}),
    ("write_clipboard", {"text": "代码"}),
    ("get_selected_text", {}),
    ("take_screenshot", {}),
    ("create_note", {"title": "笔记", "content": "中文"}),
    ("show_win_toast", {"title": "已复制", "message": "代码已复制"}),
    ("edge_config_update", {"app_whitelist": ["Code.exe"]}),
]


@pytest.mark.parametrize("name,args", VIRTUAL_CASES)
async def test_every_virtual_tool(rt, name, args):
    assert set(TOOL_SCHEMAS) == {entry[0] for entry in VIRTUAL_CASES}
    assert isinstance(await rt.edge.call(name, args), dict)


@pytest.mark.parametrize(
    "name,args",
    [
        ("run_shell", {"command": "echo x"}),
        ("open_app", {"name": "powershell.exe"}),
        ("open_url", {"url": "file:///C:/private"}),
        ("open_folder", {"path": "\\\\server\\share"}),
        ("open_folder", {"path": "D:\\..\\private"}),
        ("create_note", {"title": "../secret", "content": "x"}),
    ],
)
async def test_tool_permission_boundary(rt, name, args):
    with pytest.raises(ToolError):
        await rt.edge.call(name, args)


async def test_clipboard_roundtrip_and_speech_limit(rt):
    await rt.edge.call("write_clipboard", {"text": "def sort(): pass"})
    assert (await rt.edge.call("read_clipboard", {}))["text"] == "def sort(): pass"
    await rt.speak("#" + "字" * 100)
    assert len(rt.virtual.calls[-1][1]["text"]) == 60
