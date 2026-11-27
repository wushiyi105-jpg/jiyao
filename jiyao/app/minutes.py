"""三件套一次成文：会议纪要 + 邮件草稿 + 可复制群消息。"""

from __future__ import annotations

from datetime import date
from typing import Any

from ..domain.catalog import template_for
from ..domain.models import Report


def _quote(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def group_message(report: Report, title: str, today: date) -> str:
    lines = [f"【{title or '会议'}纪要】{today.isoformat()}", f"结论 {len(report.decisions)} 条："]
    for i, d in enumerate(report.decisions, 1):
        lines.append(f"{i}. {_quote(d.text, 50)}")
    lines.append(f"待办 {len(report.actions)} 条：")
    for a in report.actions:
        owner = a.assignee or "待指派"
        due = a.due.isoformat() if a.due else "待定期限"
        lines.append(f"- {_quote(a.text, 40)}（{owner}，{due}）")
    if report.unassigned or report.undated:
        lines.append(f"另有 {len(report.unassigned)} 条缺负责人、{len(report.undated)} 条缺期限，请会上补齐。")
    lines.append("有出入请直接回复更正。")
    return "\n".join(lines)


def build_minutes(
    report: Report,
    title: str,
    today: date,
    template: dict[str, Any] | None = None,
) -> str:
    tpl = template or template_for(title)
    lines = [
        f"# {title or '会议纪要'} · {today.isoformat()}",
        "",
        f"> 模板：{tpl['name'] if tpl else '未匹配（按通用纪要输出）'}；"
        f"结论 {len(report.decisions)} 条，待办 {len(report.actions)} 条，"
        f"缺负责人 {len(report.unassigned)} 条，缺期限 {len(report.undated)} 条。",
        "",
    ]
    if tpl:
        lines += [
            f"**这份纪要按「{tpl['name']}」检查：** {'、'.join(tpl['must_have'])}。",
            "",
            f"_{tpl['hint']}_",
            "",
        ]

    lines += ["## 一、结论（每条都能回到原文）", ""]
    if report.decisions:
        for i, d in enumerate(report.decisions, 1):
            lines.append(f"{i}. {d.text}")
            lines.append(f"   > 原文（第 {d.offset} 字）：{_quote(d.quote, 100)}")
            lines.append("")
    else:
        lines += ["- 本次没有识别到明确结论。", ""]

    lines += ["## 二、待办", ""]
    if report.actions:
        lines += ["| # | 事项 | 负责人 | 期限 | 原文 |", "| ---: | --- | --- | --- | --- |"]
        for i, a in enumerate(report.actions, 1):
            owner = a.assignee or "**待指派**"
            due = a.due.isoformat() if a.due else "**待定期限**"
            lines.append(f"| {i} | {_quote(a.text, 40)} | {owner} | {due} | {_quote(a.quote, 30)} |")
    else:
        lines.append("- 本次没有识别到待办。")
    lines += ["", "标记完成：`jiyao actions` 查编号，`jiyao done <编号>` 关掉。", ""]

    lines += ["## 三、需要确认 / 风险", ""]
    risky = [f for f in report.findings if f.severity in {"high", "warn"}]
    if risky:
        for f in risky:
            lines.append(f"- **{f.rule_id}**：{f.message}（{f.evidence}）")
    else:
        lines.append("- 没有发现缺主、缺期或引用对不上的问题。")
    if report.questions:
        lines += [f"- 待确认：{q}" for q in report.questions]
    lines.append("")

    lines += ["## 四、邮件草稿（可直接发）", "", "```text", _email_body(report, title, today), "```", ""]
    lines += [
        "## 五、群消息（可直接复制）",
        "",
        "```text",
        group_message(report, title, today),
        "```",
        "",
        "---",
        "",
        "说明：结论与待办由本地规则抽取，每条附原文位置；模型只写摘要，不参与结论。",
        "",
    ]
    return "\n".join(lines)


def _email_body(report: Report, title: str, today: date) -> str:
    lines = [f"主题：{title or '会议'}纪要（{today.isoformat()}）", "", "各位好，", ""]
    lines.append("同步本次会议的结论与待办：")
    lines.append("")
    lines.append("一、已定事项")
    if report.decisions:
        lines += [f"{i}. {d.text}" for i, d in enumerate(report.decisions, 1)]
    else:
        lines.append("（本次没有明确结论）")
    lines += ["", "二、待办"]
    if report.actions:
        for a in report.actions:
            owner = a.assignee or "待指派"
            due = a.due.isoformat() if a.due else "待定期限"
            lines.append(f"- {a.text} —— {owner}，{due}")
    else:
        lines.append("（本次没有待办）")
    if report.findings:
        lines += ["", "三、需要补齐"]
        lines += [f"- {f.message}：{f.evidence}" for f in report.findings if f.severity != "info"]
    lines += ["", "如有出入请直接回复更正。", "", "谢谢。"]
    return "\n".join(lines)
