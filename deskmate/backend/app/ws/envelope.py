"""生成和验证版本二 WebSocket 信封。"""

from typing import Any, Literal
from uuid import uuid4

from pydantic import Field, field_validator

from app.clock import Clock, iso, parse_time
from app.schemas.contracts import StrictModel


class Envelope(StrictModel):
    v: Literal[2] = 2
    type: Literal["event", "cmd", "result", "ping", "pong"]
    id: str = Field(min_length=1, max_length=100)
    ts: str
    name: str
    payload: dict[str, Any]

    @field_validator("ts")
    @classmethod
    def aware(cls, value: str) -> str:
        parse_time(value)
        return value


def envelope(
    clock: Clock,
    name: str,
    payload: dict[str, Any],
    kind: str = "event",
    message_id: str | None = None,
) -> dict[str, Any]:
    return {
        "v": 2,
        "type": kind,
        "id": message_id or str(uuid4()),
        "ts": iso(clock),
        "name": name,
        "payload": payload,
    }
