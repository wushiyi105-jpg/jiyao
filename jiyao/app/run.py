"""用例：转写 → 决议/待办、跟进邮件、提醒文本。只认 domain + ports。"""

from __future__ import annotations

from datetime import date

from ..domain.engine import analyze, followup_email
from ..domain.models import Action, Report
from ..domain.remind import reminder_text
from ..ports import StorePort


def digest(transcript: str, today: date) -> Report:
    return analyze(transcript, today)


def digest_and_save(store: StorePort, transcript: str, today: date, title: str = "") -> tuple[Report, int]:
    report = analyze(transcript, today)
    return report, store.save(report, title)


def email(transcript: str, today: date) -> str:
    return followup_email(analyze(transcript, today))


def open_actions(store: StorePort) -> list[Action]:
    return store.open_actions()


def finish(store: StorePort, action_id: int) -> bool:
    return store.complete(action_id)


def reminder(store: StorePort, today: date, ahead_days: int = 3) -> str:
    return reminder_text(store.open_actions(), today, ahead_days) or ""
