"""提醒文案：过期、今天到期、三天内到期。纯函数，不碰数据库。"""

from __future__ import annotations

from datetime import date, timedelta

from .models import Action


def buckets(actions: list[Action], today: date, ahead: int = 3) -> dict[str, list[Action]]:
    overdue = [a for a in actions if a.status == "open" and a.due and a.due < today]
    due_today = [a for a in actions if a.status == "open" and a.due == today]
    soon = [
        a
        for a in actions
        if a.status == "open" and a.due and today < a.due <= today + timedelta(days=ahead)
    ]
    return {"overdue": overdue, "today": due_today, "soon": soon}


def reminder_text(actions: list[Action], today: date, ahead: int = 3) -> str | None:
    """没有要提醒的就返回 None。"""
    b = buckets(actions, today, ahead)
    if not any(b.values()):
        return None
    lines: list[str] = [f"{today.isoformat()} 待办提醒"]
    if b["overdue"]:
        lines.append(f"已过期 {len(b['overdue'])} 条：")
        for a in b["overdue"]:
            assert a.due is not None
            lines.append(f"- {a.text}（{a.assignee or '未指派'}，{a.due}，逾期 {(today - a.due).days} 天）")
    if b["today"]:
        lines.append(f"今天到期 {len(b['today'])} 条：")
        for a in b["today"]:
            lines.append(f"- {a.text}（{a.assignee or '未指派'}）")
    if b["soon"]:
        lines.append(f"{ahead} 天内到期 {len(b['soon'])} 条：")
        for a in b["soon"]:
            lines.append(f"- {a.text}（{a.assignee or '未指派'}，{a.due}）")
    return "\n".join(lines)
