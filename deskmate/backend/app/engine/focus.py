"""专注和休息阶段计时、暂停恢复及持久化，心流决策委托 C 接口。"""

import logging
from datetime import UTC, datetime, time, timedelta
from math import ceil
from typing import Any
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.clock import Clock, iso, parse_time
from app.config import Config
from app.db import Database, FocusCheckpoint, FocusSession
from app.engine.state_store import StateStore
from app.integrations import WellbeingEngine

logger = logging.getLogger(__name__)


class FocusEngine:
    def __init__(
        self,
        user_id: int,
        db: Database,
        clock: Clock,
        store: StateStore,
        config: Config,
        wellbeing: WellbeingEngine | None = None,
    ) -> None:
        self.user_id, self.db, self.clock, self.store = user_id, db, clock, store
        self.config, self.wellbeing = config, wellbeing
        self.last_at = clock.now()
        self.resume_phase = "focusing"
        self.focus_minutes = config.default_focus_minutes
        self.account_remainder_us = 0
        self.today_remainder_us = 0
        self.focus_day = clock.now().astimezone(ZoneInfo(config.tz)).date()
        self.restore()

    @property
    def state(self) -> dict[str, Any]:
        return dict(self.store.data["focus"])

    def restore(self) -> None:
        with Session(self.db.engine) as session:
            checkpoint = session.get(FocusCheckpoint, self.user_id)
            if checkpoint and checkpoint.state.get("_day") == self.focus_day.isoformat():
                state = self.state
                state["focus_seconds_today"] = checkpoint.state.get("focus_seconds_today", 0)
                self.store.update(focus=state)
            if checkpoint and checkpoint.state["state"] != "idle":
                state = dict(checkpoint.state)
                saved_day = state.pop("_day", None)
                if saved_day != self.focus_day.isoformat():
                    state["focus_seconds_today"] = 0
                self.resume_phase = state.pop("_resume_phase", "focusing")
                self.focus_minutes = state.pop("_focus_minutes", self.focus_minutes)
                if state["state"] != "paused":
                    self.resume_phase = state["state"]
                state.update(state="paused", phase_ends_at=None)
                self.store.update(focus=state)
                self.persist()

    def persist(self) -> None:
        state = {
            **self.state,
            "_resume_phase": self.resume_phase,
            "_focus_minutes": self.focus_minutes,
            "_day": self.focus_day.isoformat(),
        }
        with Session(self.db.engine) as session:
            row = session.get(FocusCheckpoint, self.user_id)
            if row is None:
                row = FocusCheckpoint(user_id=self.user_id, state=state)
            else:
                row.state = state
            session.add(row)
            session.commit()

    def start(self, workspace: dict[str, Any], goal: str, minutes: int | None) -> dict[str, Any]:
        if self.state["state"] != "idle":
            self.stop("replaced")
        self.focus_minutes = minutes or workspace["focus_minutes"]
        with Session(self.db.engine) as session:
            row = FocusSession(
                user_id=self.user_id,
                workspace_id=workspace.get("id"),
                workspace_name=workspace["name"],
                started_at=iso(self.clock),
                goal=goal,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            state = {
                "state": "focusing",
                "session_id": row.id,
                "workspace_name": workspace["name"],
                "goal": goal,
                "phase_started_at": iso(self.clock),
                "phase_ends_at": (
                    self.clock.now() + timedelta(minutes=self.focus_minutes)
                ).isoformat(),
                "remaining_seconds": self.focus_minutes * 60,
                "pomodoro_index": 1,
                "flow_extensions": 0,
                "focus_seconds_today": self.state["focus_seconds_today"],
            }
        self.last_at = self.clock.now()
        self.account_remainder_us = 0
        self.store.update(focus=state)
        self.persist()
        return state

    def account(self) -> None:
        state = self.state
        now = self.clock.now()
        local_day = now.astimezone(ZoneInfo(self.config.tz)).date()
        if local_day != self.focus_day:
            self.focus_day = local_day
            self.today_remainder_us = 0
            state["focus_seconds_today"] = 0
            self.store.update(focus=state)
        if state["state"] == "focusing":
            stop = min(now, parse_time(state["phase_ends_at"]))
            elapsed = max(timedelta(0), stop - self.last_at)
            microseconds = (
                elapsed.days * 86_400_000_000
                + elapsed.seconds * 1_000_000
                + elapsed.microseconds
                + self.account_remainder_us
            )
            seconds, self.account_remainder_us = divmod(microseconds, 1_000_000)
            if seconds:
                with Session(self.db.engine) as session:
                    row = session.get(FocusSession, state["session_id"])
                    row.focus_seconds += seconds
                    session.add(row)
                    session.commit()
            midnight = datetime.combine(local_day, time(), ZoneInfo(self.config.tz)).astimezone(UTC)
            today_elapsed = max(timedelta(0), stop - max(self.last_at, midnight))
            today_us = (
                today_elapsed.days * 86_400_000_000
                + today_elapsed.seconds * 1_000_000
                + today_elapsed.microseconds
                + self.today_remainder_us
            )
            today_seconds, self.today_remainder_us = divmod(today_us, 1_000_000)
            state["focus_seconds_today"] += today_seconds
            self.store.update(focus=state)
        self.last_at = now

    def pause(self) -> None:
        if self.state["state"] not in {"focusing", "short_break"}:
            return
        self.account()
        state = self.state
        self.resume_phase = state["state"]
        remaining = max(
            0, ceil((parse_time(state["phase_ends_at"]) - self.clock.now()).total_seconds())
        )
        state.update(state="paused", remaining_seconds=remaining, phase_ends_at=None)
        self.store.update(focus=state)
        with Session(self.db.engine) as session:
            row = session.get(FocusSession, state["session_id"])
            row.pause_count += 1
            session.add(row)
            session.commit()
        self.persist()

    def resume(self) -> None:
        state = self.state
        if state["state"] != "paused":
            return
        state.update(
            state=self.resume_phase,
            phase_started_at=iso(self.clock),
            phase_ends_at=(
                self.clock.now() + timedelta(seconds=state["remaining_seconds"])
            ).isoformat(),
        )
        self.last_at = self.clock.now()
        self.store.update(focus=state)
        self.persist()

    def stop(self, reason: str = "user") -> dict[str, Any] | None:
        self.account()
        state = self.state
        if state["session_id"] is None:
            return None
        with Session(self.db.engine) as session:
            row = session.get(FocusSession, state["session_id"])
            row.ended_at, row.end_reason = iso(self.clock), reason
            session.add(row)
            session.commit()
            session.refresh(row)
            result = row.model_dump()
        state.update(
            state="idle",
            session_id=None,
            remaining_seconds=0,
            phase_started_at=None,
            phase_ends_at=None,
        )
        self.store.update(focus=state)
        self.persist()
        return result

    def force_break(self) -> None:
        if self.state["state"] != "focusing":
            return
        self.account()
        state = self.state
        state.update(
            state="short_break",
            phase_started_at=iso(self.clock),
            phase_ends_at=(
                self.clock.now() + timedelta(minutes=self.config.break_minutes)
            ).isoformat(),
            remaining_seconds=self.config.break_minutes * 60,
        )
        self.store.update(focus=state)
        self.persist()

    def tick(self, settings: dict[str, Any]) -> str | None:
        self.account()
        state = self.state
        if state["state"] not in {"focusing", "short_break"}:
            return None
        remaining = max(
            0, ceil((parse_time(state["phase_ends_at"]) - self.clock.now()).total_seconds())
        )
        state["remaining_seconds"] = remaining
        self.store.update(focus=state)
        action = None
        if remaining == 0:
            wb = settings["wellbeing"]
            extend = False
            if (
                state["state"] == "focusing"
                and self.wellbeing
                and (state["flow_extensions"] < wb["max_flow_extensions"])
            ):
                try:
                    extend = self.wellbeing.check_flow_extension(state["session_id"])
                except Exception:
                    logger.exception("C 心流接口异常，使用正常休息流程")
            if extend:
                state["flow_extensions"] += 1
                state["remaining_seconds"] = wb["flow_extension_min"] * 60
                action = "flow_extended"
            elif state["state"] == "focusing":
                state["state"] = "short_break"
                state["remaining_seconds"] = self.config.break_minutes * 60
                action = "break"
            else:
                state["state"] = "focusing"
                state["remaining_seconds"] = self.focus_minutes * 60
                state["pomodoro_index"] += 1
                action = "focus"
            state["phase_started_at"] = iso(self.clock)
            state["phase_ends_at"] = (
                self.clock.now() + timedelta(seconds=state["remaining_seconds"])
            ).isoformat()
            with Session(self.db.engine) as session:
                row = session.get(FocusSession, state["session_id"])
                row.flow_extensions = state["flow_extensions"]
                if action == "break":
                    row.pomodoros_done += 1
                session.add(row)
                session.commit()
            self.store.update(focus=state)
        self.persist()
        return action

    def sessions(self) -> list[FocusSession]:
        with Session(self.db.engine) as session:
            return list(
                session.exec(
                    select(FocusSession)
                    .where(FocusSession.user_id == self.user_id)
                    .order_by(FocusSession.id.desc())
                )
            )
