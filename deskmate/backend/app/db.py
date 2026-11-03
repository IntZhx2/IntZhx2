"""SQLModel 持久化、版本化迁移及用户隔离查询。"""

import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Column, Engine
from sqlmodel import Field, Session, SQLModel, create_engine, select

from app.config import DEFAULT_SETTINGS, Config


class SchemaVersion(SQLModel, table=True):
    version: int = Field(primary_key=True)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    is_demo: bool = False


class UserSettings(SQLModel, table=True):
    user_id: int = Field(primary_key=True, foreign_key="user.id")
    values: dict[str, Any] = Field(sa_column=Column(JSON))


class WorkspaceProfile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    aliases: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    focus_minutes: int = 45
    lamp: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    ac: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    items: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    layout: str = "code_left_browser_right"
    custom_layout: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))


class FocusSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    workspace_id: int | None = None
    workspace_name: str = "默认工作台"
    started_at: str
    ended_at: str | None = None
    goal: str = ""
    focus_seconds: int = 0
    pomodoros_done: int = 0
    pause_count: int = 0
    flow_extensions: int = 0
    end_reason: str = ""


class FocusCheckpoint(SQLModel, table=True):
    user_id: int = Field(primary_key=True)
    state: dict[str, Any] = Field(sa_column=Column(JSON))


class VoiceLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    at: str
    text: str
    route: str
    trace: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    reply: str
    latency_ms: int
    ok: bool


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    _, rounds, salt, expected = stored.split("$")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
    return hmac.compare_digest(actual, expected)


class Database:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///") and ":memory:" not in url:
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url:
                from sqlalchemy.pool import StaticPool

                kwargs["poolclass"] = StaticPool
        self.engine: Engine = create_engine(url, **kwargs)

    def migrate_and_seed(self, config: Config) -> None:
        # v1 首次建表。后续版本必须在此增加显式迁移，不用 create_all 伪装列迁移。
        SchemaVersion.__table__.create(self.engine, checkfirst=True)
        with Session(self.engine) as session:
            versions = list(session.exec(select(SchemaVersion.version)))
            if any(v > 1 for v in versions):
                raise RuntimeError("数据库版本比程序新，请使用匹配镜像")
            if 1 not in versions:
                SQLModel.metadata.create_all(self.engine)
                session.add(SchemaVersion(version=1))
                session.commit()
            for name, is_demo, password in (
                ("admin", False, config.admin_password),
                ("demo", True, config.demo_password),
            ):
                user = session.exec(select(User).where(User.username == name)).first()
                if user is None:
                    user = User(
                        username=name,
                        is_demo=is_demo,
                        password_hash=hash_password(password.get_secret_value()),
                    )
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                    session.add(UserSettings(user_id=user.id, values=DEFAULT_SETTINGS))
                    session.add(
                        WorkspaceProfile(
                            user_id=user.id,
                            name="默认工作台",
                            aliases=["软工", "软工大作业"],
                            lamp=DEFAULT_SETTINGS["focus_lamp"],
                            ac={"auto_on": True, "temperature": 26},
                            items=[],
                            focus_minutes=config.default_focus_minutes,
                        )
                    )
                    session.commit()

    def settings(self, user_id: int) -> dict[str, Any]:
        import copy

        with Session(self.engine) as session:
            row = session.get(UserSettings, user_id)
            return copy.deepcopy(row.values if row else DEFAULT_SETTINGS)
