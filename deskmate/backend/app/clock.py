"""统一 UTC 时钟及可手动推进的测试时钟。"""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.fromtimestamp(time.time(), UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class ManualClock(SystemClock):
    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            raise ValueError("测试时间必须带时区")
        self.at = at.astimezone(UTC)
        self.elapsed = 0.0

    def now(self) -> datetime:
        return self.at

    def monotonic(self) -> float:
        return self.elapsed

    def advance(self, seconds: float) -> None:
        self.at += timedelta(seconds=seconds)
        self.elapsed += seconds


def iso(clock: Clock) -> str:
    return clock.now().astimezone(UTC).isoformat()


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("时间必须带时区")
    return result.astimezone(UTC)
