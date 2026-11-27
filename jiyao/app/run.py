"""用例：转写 → 决议/待办、跟进邮件、提醒文本。只认 domain + ports。"""

from __future__ import annotations

from datetime import date

from ..domain.engine import analyze, followup_email
from ..domain.models import Action, Report
from ..domain.remind import reminder_text
from ..ports import LLMPort, StorePort

SUMMARY_PROMPT = (
    "你是会议纪要助手。只根据给定转写写 2-3 句中文摘要，"
    "点出已定事项、关键待办和风险。不要编造转写里没有的人、日期或数字。"
)


def digest(transcript: str, today: date, llm: LLMPort | None = None) -> Report:
    report = analyze(transcript, today)
    if llm is None:
        return report
    try:
        report.summary = llm.write(SUMMARY_PROMPT, transcript).strip()
    except Exception:  # noqa: BLE001 模型失败不挡住本地抽取
        report.summary = ""
    return report


def digest_and_save(
    store: StorePort,
    transcript: str,
    today: date,
    title: str = "",
    llm: LLMPort | None = None,
) -> tuple[Report, int]:
    report = digest(transcript, today, llm)
    return report, store.save(report, title)


def email(transcript: str, today: date) -> str:
    return followup_email(analyze(transcript, today))


def open_actions(store: StorePort) -> list[Action]:
    return store.open_actions()


def finish(store: StorePort, action_id: int) -> bool:
    return store.complete(action_id)


def reminder(store: StorePort, today: date, ahead_days: int = 3) -> str:
    return reminder_text(store.open_actions(), today, ahead_days) or ""
