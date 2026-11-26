"""校验与逾期：引用必须能回溯，待办必须有主有期。"""

from __future__ import annotations

from datetime import date

from ..models import Action, Decision, Finding


def validate_quotes(transcript: str, decisions: list[Decision], actions: list[Action]) -> list[Finding]:
    out: list[Finding] = []
    for d in decisions:
        if d.quote and d.quote not in transcript:
            out.append(
                Finding(
                    rule_id="trace.decision",
                    severity="high",
                    message="决议引用的原文在转写里找不到",
                    evidence=f"引用：{d.quote[:30]}…",
                    suggestion="该条已丢弃，请人工确认",
                )
            )
    for a in actions:
        if a.quote and a.quote not in transcript:
            out.append(
                Finding(
                    rule_id="trace.action",
                    severity="high",
                    message="待办引用的原文在转写里找不到",
                    evidence=f"引用：{a.quote[:30]}…",
                    suggestion="该条已丢弃，请人工确认",
                )
            )
    return out


def completeness(actions: list[Action]) -> list[Finding]:
    out: list[Finding] = []
    for a in actions:
        if not a.assignee:
            out.append(
                Finding(
                    rule_id="action.no_owner",
                    severity="warn",
                    message="待办没有负责人",
                    evidence=a.text[:40],
                    suggestion="会上补一句“谁来做”，否则不会有人做",
                )
            )
        if a.due is None:
            out.append(
                Finding(
                    rule_id="action.no_due",
                    severity="warn",
                    message="待办没有期限",
                    evidence=a.text[:40],
                    suggestion="补一个日期，逾期才能提醒",
                )
            )
    return out


def overdue(actions: list[Action], today: date) -> list[Finding]:
    out: list[Finding] = []
    for a in actions:
        if a.status == "done" or a.due is None:
            continue
        days = (today - a.due).days
        if days > 0:
            out.append(
                Finding(
                    rule_id="action.overdue",
                    severity="high" if days > 7 else "warn",
                    message=f"待办逾期 {days} 天",
                    evidence=f"{a.assignee or '未指派'} · {a.text[:40]}",
                    suggestion="今天问一次进展",
                )
            )
    return out
