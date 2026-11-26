"""引擎：抽取 → 校验 → 逾期。"""

from __future__ import annotations

from datetime import date

from .models import Report
from .rules import extract, track


def analyze(transcript: str, today: date | None = None) -> Report:
    today = today or date.today()
    decisions, actions = extract.extract(transcript, today)
    report = Report(transcript=transcript, decisions=decisions, actions=actions)

    bad = track.validate_quotes(transcript, decisions, actions)
    bad_ids = {f.evidence for f in bad}
    if bad:
        # 引用对不上的条目丢弃，避免脏数据入库
        report.decisions = [d for d in decisions if f"引用：{d.quote[:30]}…" not in bad_ids]
        report.actions = [a for a in actions if f"引用：{a.quote[:30]}…" not in bad_ids]
        report.findings += bad

    report.findings += track.completeness(report.actions)
    report.findings += track.overdue(report.actions, today)
    report.findings.sort(key=lambda f: {"high": 0, "warn": 1, "info": 2}[f.severity])
    return report


def followup_email(report: Report) -> str:
    lines = ["各位好，同步一下本次会议的结论与待办：", ""]
    if report.decisions:
        lines.append("一、已定事项")
        lines += [f"- {d.text}" for d in report.decisions]
        lines.append("")
    if report.actions:
        lines.append("二、待办")
        for a in report.actions:
            owner = a.assignee or "（待指派）"
            due = a.due.isoformat() if a.due else "（待定期限）"
            lines.append(f"- {a.text} —— {owner}，{due}")
    if report.questions:
        lines += ["", "三、待确认"] + [f"- {q}" for q in report.questions]
    lines += ["", "如有出入请直接回复更正。"]
    return "\n".join(lines)
