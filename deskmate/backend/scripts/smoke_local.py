"""通过真实 localhost HTTP/WS 验证登录、设备、SSE、锁屏与演示隔离。"""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import websockets
from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


async def main(base: str) -> None:
    env = await asyncio.to_thread(dotenv_values, ENV_FILE)
    async with httpx.AsyncClient(base_url=base, timeout=15) as client:
        health = await client.get("/api/health")
        health.raise_for_status()
        assert health.json()["ok"]
        response = await client.post(
            "/api/auth/login", json={"username": "demo", "password": env["DEMO_PASSWORD"]}
        )
        response.raise_for_status()
        token = response.json()["token"]
        client.headers["Authorization"] = "Bearer " + token
        ws_url = base.replace("http://", "ws://").replace("https://", "wss://")
        async with websockets.connect(ws_url + "/ws/web?token=" + token) as ws:
            assert json.loads(await ws.recv())["name"] == "state.snapshot"
            response = await client.post("/api/focus/start", json={"minutes": 1})
            response.raise_for_status()
            assert response.json()["state"] == "focusing"
            for _ in range(20):
                message = json.loads(await asyncio.wait_for(ws.recv(), 3))
                if message["name"] == "state.patch":
                    break
            else:
                raise AssertionError("未收到 state.patch")
            await client.post("/api/demo/inject", json={"kind": "lock", "value": True})
            snapshot = (await client.get("/api/state")).json()
            assert snapshot["focus"]["state"] == "paused"
            assert snapshot["devices"]["lamp"]["brightness"] == 10
            await client.post("/api/demo/inject", json={"kind": "lock", "value": False})
            response = await client.post("/api/chat", json={"message": "空调调到25度"})
            response.raise_for_status()
            assert "event: done" in response.text
            snapshot = (await client.get("/api/state")).json()
            assert snapshot["devices"]["ac"]["temperature"] == 25
            assert snapshot["demo_mode"]
            await client.post("/api/focus/stop")
        response = await client.get("/docs")
        response.raise_for_status()
        report = await client.get("/api/reports/daily")
        assert report.status_code == 503
        print(
            json.dumps(
                {
                    "base_url": base,
                    "health": "ok",
                    "login": "ok",
                    "websocket": "ok",
                    "focus_pause_resume": "ok",
                    "sse_fast_path": "ok",
                    "demo_mode": True,
                    "api_docs": "ok",
                    "c_module": "not_installed",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    asyncio.run(main(args.base_url.rstrip("/")))
