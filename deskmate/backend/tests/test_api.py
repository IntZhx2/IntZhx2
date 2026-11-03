"""验证契约路由、JWT、所有权校验和数据库重启恢复。"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import Database, SchemaVersion, User, verify_password
from app.main import create_app


def test_login_auth_expiry_and_health(client, headers, clock):
    assert client.get("/api/health").json() == {"ok": True, "edge_online": False, "demo_mode": True}
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/state", headers=headers).status_code == 200
    assert (
        client.post("/api/auth/login", json={"username": "demo", "password": "wrong"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "unknown", "password": "wrong"}
        ).status_code
        == 401
    )
    clock.advance(481 * 60)
    assert client.get("/api/state", headers=headers).status_code == 401


def test_crud_and_owner_isolation(client, headers):
    body = {"name": "中文工作台", "items": [{"type": "folder", "path": "D:\\课程\\软工"}]}
    result = client.post("/api/workspaces", json=body, headers=headers)
    assert result.status_code == 201
    key = result.json()["id"]
    assert "user_id" not in result.json()
    assert (
        client.put(
            f"/api/workspaces/{key}", json={**body, "name": "修改后"}, headers=headers
        ).json()["name"]
        == "修改后"
    )
    admin = client.post(
        "/api/auth/login", json={"username": "admin", "password": "test-admin-password"}
    ).json()["token"]
    auth = {"Authorization": "Bearer " + admin}
    assert client.delete(f"/api/workspaces/{key}", headers=auth).status_code == 404
    assert (
        client.post("/api/focus/start", json={"workspace_id": key}, headers=auth).status_code == 404
    )
    assert client.post("/api/demo/inject", json={"kind": "leave"}, headers=auth).status_code == 403
    assert client.delete(f"/api/workspaces/{key}", headers=headers).status_code == 200
    assert client.delete(f"/api/workspaces/{key}", headers=headers).status_code == 404


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/devices/lamp/command", {"brightness": 0}),
        ("/api/devices/ac/command", {"temperature": 99}),
        ("/api/devices/plug/command", {"on": "true"}),
        ("/api/devices/motion/command", {"on": True}),
        ("/api/workspaces", {"name": "", "items": []}),
        (
            "/api/workspaces",
            {"name": "x", "items": [{"type": "url", "url": "javascript:alert(1)"}]},
        ),
        ("/api/demo/inject", {"kind": "temperature", "value": True}),
        ("/api/demo/inject", {"kind": "lock", "value": "true"}),
        ("/api/demo/inject", {"kind": "typing_rate", "value": -1}),
        ("/api/demo/inject", {"kind": "unknown"}),
    ],
)
def test_invalid_requests(client, headers, path, body):
    assert client.post(path, json=body, headers=headers).status_code in {404, 422}


def test_settings_live_merge_and_validation(client, headers):
    updated = client.put("/api/settings", json={"ac": {"trigger_on_temp": 29.0}}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["ac"]["summer_temp"] == 26
    assert (
        client.put(
            "/api/settings", json={"wellbeing": {"l1_score": 99}}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.put("/api/settings", json={"absent_lamp_off_min": -1}, headers=headers).status_code
        == 422
    )
    assert (
        client.put("/api/settings", json={"shell": "anything"}, headers=headers).status_code == 422
    )
    assert client.get("/api/settings", headers=headers).json()["ac"]["trigger_on_temp"] == 29.0


def test_virtual_focus_cycle_session_and_lock(client, headers, clock):
    result = client.post("/api/focus/start", json={"minutes": 1}, headers=headers)
    assert result.status_code == 200
    assert result.json()["remaining_seconds"] == 60
    clock.advance(20)
    assert (
        client.post(
            "/api/demo/inject", json={"kind": "lock", "value": True}, headers=headers
        ).status_code
        == 200
    )
    paused = client.get("/api/state", headers=headers).json()
    assert paused["focus"]["state"] == "paused"
    assert paused["devices"]["lamp"]["brightness"] == 10
    clock.advance(180)
    client.post("/api/demo/inject", json={"kind": "lock", "value": False}, headers=headers)
    assert client.get("/api/state", headers=headers).json()["focus"]["remaining_seconds"] == 40
    clock.advance(40)
    client.post("/api/demo/inject", json={"kind": "temperature", "value": 28.0}, headers=headers)
    assert client.get("/api/state", headers=headers).json()["focus"]["state"] == "short_break"
    record = client.post("/api/focus/stop", headers=headers).json()["session"]
    assert record["focus_seconds"] == 60 and record["pause_count"] == 1
    assert record["pomodoros_done"] == 1
    assert (
        client.get("/api/focus/sessions?from=2026-11-02&to=2026-11-02", headers=headers).json()[0][
            "id"
        ]
        == record["id"]
    )
    assert (
        client.get("/api/focus/sessions?from=2026-11-03&to=2026-11-02", headers=headers).status_code
        == 422
    )


def test_missing_c_module_is_explicit(client, headers):
    for path in ("/api/reports/daily", "/api/reports/weekly", "/api/timeline"):
        assert client.get(path, headers=headers).status_code == 503


def test_persistence_and_seed_idempotence(config, clock):
    with TestClient(create_app(config, clock, run_scheduler=False)) as client:
        token = client.post(
            "/api/auth/login", json={"username": "demo", "password": "test-demo-password"}
        ).json()["token"]
        headers = {"Authorization": "Bearer " + token}
        client.put("/api/settings", json={"absent_confirm_min": 2.0}, headers=headers)
        client.post("/api/focus/start", json={}, headers=headers)
    with TestClient(create_app(config, clock, run_scheduler=False)) as client:
        assert client.get("/api/settings", headers=headers).json()["absent_confirm_min"] == 2
        assert client.get("/api/state", headers=headers).json()["focus"]["state"] == "paused"
    db = Database(config.database_url)
    with Session(db.engine) as session:
        users = list(session.exec(select(User)))
        assert len(users) == 2
        assert verify_password("test-demo-password", users[1].password_hash)
        session.add(SchemaVersion(version=99))
        session.commit()
    with pytest.raises(RuntimeError, match="版本"):
        db.migrate_and_seed(config)
    db.engine.dispose()


def test_request_limits_and_login_rate(client):
    assert client.post("/api/auth/login", content="x" * 70000).status_code == 413
    for _ in range(10):
        client.post("/api/auth/login", json={"username": "attacker", "password": "wrong"})
    assert (
        client.post(
            "/api/auth/login", json={"username": "attacker", "password": "wrong"}
        ).status_code
        == 429
    )


def test_chat_fast_and_unconfigured_llm(client, headers):
    response = client.post("/api/chat", json={"message": "开灯"}, headers=headers)
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in response.text
    assert client.get("/api/state", headers=headers).json()["devices"]["lamp"]["on"]
    response = client.post("/api/chat", json={"message": "帮我解释代码"}, headers=headers)
    assert "event: error" in response.text and "LLM_API_KEY" in response.text
    assert len(client.get("/api/logs/voice", headers=headers).json()) == 2
