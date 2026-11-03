"""验证 RPC 关联、断线/超时清理和真实 Edge 与演示隔离。"""

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from app.agent.tools import TOOL_SCHEMAS, ToolError, spec
from app.ws.envelope import envelope


class Socket:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_json(self, message):
        self.sent.append(message)

    async def close(self, code=1000):
        self.closed = True


def hello():
    return {
        "devices": {"lamp": {"online": True, "on": False, "brightness": 60, "color_temp": 4000}},
        "tools": [spec(name, schema) for name, (schema, _) in TOOL_SCHEMAS.items()],
    }


async def test_rpc_result_timeout_disconnect_cleanup(rt):
    socket = Socket()
    rt.edge.demo_only = False
    await rt.edge.register(socket, hello())
    task = asyncio.create_task(rt.edge.call("lamp_set", {"brightness": 70}))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    call_id = socket.sent[-1]["id"]
    rt.edge.resolve({"call_id": "wrong", "ok": True, "data": {}})
    assert not task.done()
    rt.edge.resolve(
        {
            "call_id": call_id,
            "ok": True,
            "data": {"online": True, "on": True, "brightness": 70, "color_temp": 4000},
        }
    )
    assert (await task)["brightness"] == 70
    assert not rt.edge.pending
    with pytest.raises(ToolError, match="TIMEOUT"):
        await rt.edge.call("read_clipboard", {}, timeout=0.01)
    assert not rt.edge.pending
    task = asyncio.create_task(rt.edge.call("read_clipboard", {}))
    await asyncio.sleep(0)
    rt.edge.disconnect(socket)
    with pytest.raises(ToolError, match="DEVICE_OFFLINE"):
        await task
    assert not rt.edge.pending
    assert rt.store.data["demo_mode"]
    assert not rt.virtual.calls  # 正在执行的调用没有自动改走模拟器。
    assert await rt.edge.call("read_clipboard", {}) == {"text": ""}


async def test_dynamic_schema_and_second_edge(rt):
    rt.edge.demo_only = False
    payload = hello()
    payload["tools"].append(spec("run_shell", {"type": "object"}))
    socket = Socket()
    await rt.edge.register(socket, payload)
    assert "run_shell" not in rt.edge.tools
    with pytest.raises(ToolError):
        await rt.edge.register(Socket(), payload)
    rt.edge.disconnect(socket)


async def test_web_snapshot_and_patch_coalescing(rt):
    socket = Socket()
    rt.web.attach(socket, rt.store.snapshot())
    queue = rt.web.clients[socket]
    assert (await queue.get())["name"] == "state.snapshot"
    rt.store.device("lamp", {"brightness": 10})
    rt.store.device("lamp", {"brightness": 30})
    rt.store.update(edge_online=True)
    await asyncio.sleep(0.23)
    message = await queue.get()
    assert message["name"] == "state.patch"
    assert message["payload"]["devices"]["lamp"]["brightness"] == 30
    assert message["payload"]["edge_online"]
    assert queue.empty()
    rt.web.detach(socket)


def test_websocket_auth_and_snapshot(client, headers):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/web?token=bad"):
            pass
    token = headers["Authorization"].split()[1]
    with client.websocket_connect("/ws/web?token=" + token) as ws:
        assert ws.receive_json()["name"] == "state.snapshot"
        client.post("/api/devices/lamp/command", json={"on": True}, headers=headers)
        assert ws.receive_json()["payload"]["devices"]["lamp"]["on"]


def test_real_edge_hello_config_and_demo_isolation(client, headers, app, config, clock):
    admin_token = client.post(
        "/api/auth/login", json={"username": "admin", "password": "test-admin-password"}
    ).json()["token"]
    admin_headers = {"Authorization": "Bearer " + admin_token}
    with client.websocket_connect("/ws/edge?token=" + config.edge_token.get_secret_value()) as ws:
        ws.send_json(envelope(clock, "edge.hello", hello()))
        command = ws.receive_json()
        assert command["payload"]["tool"] == "edge_config_update"
        ws.send_json(
            envelope(
                clock,
                "tool.result",
                {"call_id": command["id"], "ok": True, "data": {}, "error": None},
                "result",
            )
        )
        assert client.get("/api/state", headers=admin_headers).json()["edge_online"]
        client.post("/api/devices/lamp/command", json={"brightness": 35}, headers=headers)
        live = client.get("/api/state", headers=admin_headers).json()
        assert live["devices"]["lamp"]["brightness"] == 60
        assert client.get("/api/state", headers=headers).json()["demo_mode"]
        ws.send_json(envelope(clock, "unknown.event", {}))
        ws.send_json(envelope(clock, "", {}, "ping"))
        assert ws.receive_json()["type"] == "pong"
