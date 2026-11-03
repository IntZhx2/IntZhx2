"""受控模型响应验证多智能体分发、流式协议、确认和异常边界。"""

import asyncio
import json

import httpx
import pytest

from app.agent.llm import LLMClient
from app.agent.services import analyze_screen, web_search
from app.agent.tools import ToolError


def tool(name, args, call_id="call-1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
    }


def answer(text):
    return {"role": "assistant", "content": text}


def calling(*calls):
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


class ScriptedLLM:
    def __init__(self, frames):
        self.frames = list(frames)
        self.inputs = []

    async def complete(self, messages, tools, model, on_delta=None, extra=None):
        self.inputs.append((list(messages), tools, model))
        frame = self.frames.pop(0)
        if on_delta and frame.get("content"):
            await on_delta(frame["content"])
        return frame


@pytest.mark.parametrize(
    "text,device,key,value",
    [
        ("开灯", "lamp", "on", True),
        ("把灯关了", "lamp", "on", False),
        ("调亮", "lamp", "brightness", 100),
        ("暗一点", "lamp", "brightness", 60),
        ("开空调", "ac", "on", True),
        ("关空调", "ac", "on", False),
        ("空调调到25度", "ac", "temperature", 25),
    ],
)
async def test_fast_path_never_uses_llm(rt, text, device, key, value):
    rt.llm = ScriptedLLM([])
    result = await rt.handle(text)
    assert result["ok"]
    assert rt.store.data["devices"][device][key] == value
    assert not rt.llm.inputs


async def test_fast_path_exact_contract_and_focus_background(rt):
    rt.llm = ScriptedLLM([answer("可以为你调整灯光")])
    assert (await rt.handle("现在多少度"))["ok"]
    assert (await rt.handle("还剩多久"))["ok"]
    await rt.handle("把灯调亮一点")  # PRD 示例不命中 §7，必须经协调者。
    assert len(rt.llm.inputs) == 1
    await rt.handle("开始学习")
    await rt.workspace_task
    assert rt.focus.state["state"] == "focusing"
    await rt.handle("结束学习")
    assert rt.focus.state["state"] == "idle"


async def test_coordinator_start_and_multiturn(rt):
    rt.llm = ScriptedLLM(
        [
            calling(tool("start_work", {"workspace": "软工", "minutes": 25})),
            answer("已准备工作台"),
            answer("剩余25分钟"),
        ]
    )
    events = []

    async def sink(kind, payload):
        events.append((kind, payload))

    first = await rt.handle("帮我准备软工工作台", sink=sink)
    assert first["ok"] and first["conversation_id"]
    assert rt.focus.state["remaining_seconds"] == 1500
    assert any(kind == "tool" and data["status"] == "running" for kind, data in events)
    assert any(kind == "delta" for kind, data in events)
    await rt.handle("刚才我准备了什么", first["conversation_id"])
    assert any(message.get("content") == "帮我准备软工工作台" for message in rt.llm.inputs[-1][0])
    rejected = await rt.handle("x", "other-users-conversation")
    assert not rejected["ok"]


async def test_pc_delegation_clipboard_and_result_event(rt):
    rt.llm = ScriptedLLM(
        [
            calling(tool("delegate_pc", {"task": "写代码至剪贴板"})),
            calling(tool("write_clipboard", {"text": "print('hello')"})),
            calling(tool("show_win_toast", {"title": "已复制", "message": "参考代码已复制"})),
            answer("参考代码已复制"),
            answer("代码已经准备好"),
        ]
    )
    result = await rt.handle("帮我写代码至剪贴板")
    assert result["ok"]
    assert rt.virtual.clipboard == "print('hello')"
    assert "print('hello')" not in str(rt.traces)
    assert all(name != "take_screenshot" for name, _ in rt.virtual.calls)


async def test_environment_agent_and_allowed_tool_surface(rt):
    rt.llm = ScriptedLLM(
        [
            calling(tool("delegate_env", {"task": "调成温馨灯光"})),
            calling(tool("lamp_set", {"brightness": 40, "color_temp": 2700})),
            answer("灯光已调好"),
            answer("环境已准备好"),
        ]
    )
    assert (await rt.handle("帮我把灯光调温馨"))["ok"]
    assert rt.store.data["devices"]["lamp"]["color_temp"] == 2700
    env_names = {entry["function"]["name"] for entry in rt.llm.inputs[1][1]}
    assert "lamp_set" in env_names and "open_app" not in env_names


async def test_missing_workspace_confirmation_and_expiry(rt):
    # 删除默认别名以使请求走 find_files，而非已知工作台匹配。
    rt.llm = ScriptedLLM(
        [
            calling(tool("start_work", {"workspace": "软件工程大作业"})),
            answer("是打开这个目录吗"),
        ]
    )
    assert (await rt.handle("帮我准备软件工程大作业"))["ok"]
    assert rt.confirmation
    assert not any(name == "open_folder" for name, _ in rt.virtual.calls)
    await rt.handle("好")
    assert any(name == "open_folder" for name, _ in rt.virtual.calls)
    rt.expect_confirmation("开空调吗", "ac_set", {"on": True})
    await rt.handle("取消")
    assert rt.confirmation is None
    rt.expect_confirmation("开空调吗", "ac_set", {"on": True})
    rt.clock.advance(31)
    rt.llm = ScriptedLLM([answer("请重新确认要执行的操作")])
    await rt.handle("好")
    assert not rt.store.data["devices"]["ac"]["on"]


async def test_ac_ask_policy_confirmation(rt):
    rt.settings["ac"]["auto_rule"] = "ask"
    rt.store.device("climate", {"online": True, "temperature": 29.0, "humidity": 55.0})
    await rt.workspace.start(rt.workspaces()[0])
    assert rt.confirmation and not rt.store.data["devices"]["ac"]["on"]
    assert (await rt.handle("好"))["ok"]
    assert rt.store.data["devices"]["ac"]["on"]


@pytest.mark.parametrize(
    "frame",
    [
        calling(tool("shell", {"cmd": "ls"})),
        calling(tool("start_work", {"minutes": -1})),
        calling(tool("get_status", {}, "same"), tool("get_status", {}, "same")),
        answer(""),
    ],
)
async def test_bad_model_frames_do_not_execute(rt, frame):
    rt.llm = ScriptedLLM([frame])
    assert not (await rt.handle("帮我执行一个复杂任务"))["ok"]
    assert not any(name == "lamp_set" for name, _ in rt.virtual.calls)


async def test_step_limit_timeout_and_acknowledgement(rt):
    rt.llm = ScriptedLLM([calling(tool("get_status", {}, str(i))) for i in range(6)])
    assert not (await rt.handle("帮我持续规划"))["ok"]
    assert len(rt.llm.inputs) == 6

    class SlowLLM:
        async def complete(self, *args, **kwargs):
            await asyncio.sleep(0.05)
            return answer("处理完毕")

    rt.llm = SlowLLM()
    rt.config.acknowledgement_s = 0.01
    assert (await rt.handle("帮我分析一下"))["ok"]
    spoken = [args["text"] for name, args in rt.virtual.calls if name == "speaker_tts"]
    assert any("稍等" in text for text in spoken)
    rt.config.agent_timeout_s = 0.01
    assert not (await rt.handle("帮我分析一下"))["ok"]


async def test_busy_request_is_logged_without_waiting_for_llm(rt):
    async with rt.lock:
        result = await rt.handle("开灯")
    assert not result["ok"] and "上一条" in result["reply"]


async def test_vision_demo_is_explicit_and_no_image_trace(rt):
    result = await analyze_screen(rt, "screen", "分析这段代码")
    assert "占位图" in result["analysis"]
    assert "image_b64" not in str(rt.traces)


async def test_search_missing_key_and_c_summary(rt):
    rt.config.search_provider = "bocha"
    with pytest.raises(ToolError, match="BOCHA_API_KEY"):
        await web_search(rt, "Dijkstra")
    with pytest.raises(ToolError, match="报告模块"):
        await rt.orchestrator.dispatch("orchestrator", "get_today_summary", {})


async def test_llm_stream_assembles_tool_fragments(config):
    chunks = [
        {"content": "正在处理"},
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call-1",
                    "function": {"name": "lamp_set", "arguments": '{"on":'},
                }
            ]
        },
        {"tool_calls": [{"index": 0, "function": {"arguments": "true}"}}]},
    ]
    content = "".join(
        "data: " + json.dumps({"choices": [{"delta": chunk}]}) + "\n\n" for chunk in chunks
    )
    content += "data: [DONE]\n\n"
    from pydantic import SecretStr

    config.llm_api_key = SecretStr("test-key")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=content))
    ) as http:
        result = await LLMClient(config, http).complete([], [], "test")
    assert result["content"] == "正在处理"
    assert json.loads(result["tool_calls"][0]["function"]["arguments"]) == {"on": True}
