"""隔离临时数据库和可推进时钟，不访问真实硬件或外部模型。"""

from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.clock import ManualClock
from app.config import Config
from app.db import Database, User
from app.main import create_app
from app.runtime import Runtime


@pytest.fixture
def clock():
    return ManualClock(datetime(2026, 11, 2, 12, 0, tzinfo=UTC))


@pytest.fixture
def config(tmp_path):
    return Config(
        _env_file=None,
        edge_token="e" * 40,
        jwt_secret="j" * 40,
        admin_password="test-admin-password",
        demo_password="test-demo-password",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        demo_mode=False,
    )


@pytest.fixture
def app(config, clock):
    return create_app(config, clock, run_scheduler=False)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers(client):
    response = client.post(
        "/api/auth/login", json={"username": "demo", "password": "test-demo-password"}
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


@pytest_asyncio.fixture
async def rt(config, clock):
    db = Database(config.database_url)
    db.migrate_and_seed(config)
    with Session(db.engine) as session:
        user = session.exec(select(User).where(User.username == "demo")).one()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(AssertionError("测试禁止外网调用"))
        )
    ) as http:
        runtime = Runtime(user, db, config, clock, http)
        yield runtime
        await runtime.close()
    db.engine.dispose()
