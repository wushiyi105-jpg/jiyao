"""Orchestration: local extraction first, model for wording, guarded output."""

import json
import re

from . import llm, mock, rules

DATE_RE = re.compile(r"20\d{2}-\d{1,2}-\d{1,2}|20\d{2}年\d{1,2}月\d{1,2}日"
                     r"|\d{1,2}月\d{1,2}(?:日|号)|\d+月\d+日")


def strip_dates(text):
    return DATE_RE.sub("该日期", text or "")


def guard_email(email, result):
    """Reject anything the model made up: dates and numbers must come from local extraction."""
    if not email:
        return None
    allowed_dates = {result["date"]}
    for t in result["todos"]:
        if t["due"]:
            allowed_dates.add(t["due"])
    bad = [d for d in DATE_RE.findall(email) if not _date_ok(d, allowed_dates)]
    if bad:
        return None
    allowed_numbers = set(result["numbers"])
    for t in result["todos"]:
        if t["due"]:
            allowed_numbers.update(re.findall(r"\d+", t["due"]))
    invented = [n for n in re.findall(r"\d+(?:\.\d+)?", email) if n not in allowed_numbers]
    if invented:
        return None
    return email


def _date_ok(phrase, allowed):
    norm = phrase.replace("年", "-").replace("月", "-").replace("日", "").replace("号", "")
    parts = [p for p in re.split(r"-", norm) if p]
    for a in allowed:
        ap = a.split("-")
        if len(parts) >= 2 and parts[-2:] == ap[-2:]:
            return True
        if len(parts) == 1 and parts[0] == ap[-1]:
            return True
    return False


def local_email(result):
    tpl = rules.template_for(result["template"])
    subject = tpl["email_subject"].format(topic=result["topic"], date=result["date"])
    lines = [subject, "", "各位好，", "", tpl["email_intro"], "", "一、结论"]
    if result["decisions"]:
        for i, d in enumerate(result["decisions"][:3], 1):
            lines.append("%d. %s" % (i, d["text"]))
    else:
        lines.append("本次无明确决议，以下待办为过程事项。")
    lines += ["", "二、待办"]
    for i, t in enumerate(result["todos"], 1):
        due = t["due"] or "待定"
        flag = "" if t["complete"] else "(缺%s)" % "、".join(t["missing"])
        lines.append("%d. %s —— %s，截止 %s %s" % (i, t["action"], t["owner"], due, flag))
    if not result["todos"]:
        lines.append("无")
    lines += ["", "三、需下次明确"]
    for s in result["suspended"]:
        lines.append("- %s" % s["question"])
    if not result["suspended"]:
        lines.append("无")
    lines += ["", "下次会议建议议题："]
    for a in result["agenda"][:5]:
        lines.append("- [%s] %s" % (a["type"], a["text"]))
    lines += ["", "如有异议请直接回复本邮件，谢谢。"]
    return "\n".join(lines)


PROMPT = """你是会议纪要助手。下面是从转写里由程序抽好的结构化事实，你只负责措辞：
- 用 3 句以内写摘要
- 给每条待办补一句执行提示（不要改负责人、截止日期、金额）
- 指出 2-3 条风险
- 写一封跟进邮件；日期与数字只能照抄下面事实里的值，不得新造

只输出 JSON:
{"summary": "...", "todo_hints": [{"action": "...", "hint": "..."}], "risks": ["..."], "email": "..."}

会议事实:
%s
"""


def _payload(result):
    slim = {
        "topic": result["topic"], "date": result["date"], "participants": result["participants"],
        "decisions": [d["text"] for d in result["decisions"]],
        "suspended": [s["question"] for s in result["suspended"]],
        "todos": [{"action": t["action"], "owner": t["owner"], "due": t["due"],
                   "missing": t["missing"]} for t in result["todos"]],
    }
    return json.dumps(slim, ensure_ascii=False, indent=2)


def analyze(text, topic=None, participants=None, meeting_date=None, force_mock=False):
    result = rules.analyze(text, topic=topic, participants=participants, meeting_date=meeting_date)
    if force_mock or not llm.default_config().get("api_key"):
        draft = mock.draft(result)
        mode = "offline"
    else:
        try:
            raw = llm.chat([{"role": "user", "content": PROMPT % _payload(result)}])
            draft = llm.extract_json(raw)
            mode = "model"
        except Exception as e:
            draft = mock.draft(result)
            draft["error"] = str(e)
            mode = "offline"
    summary = strip_dates(draft.get("summary") or "")
    hints = {}
    for h in draft.get("todo_hints") or []:
        if isinstance(h, dict) and h.get("action"):
            hints[h["action"]] = strip_dates(str(h.get("hint") or ""))
    for t in result["todos"]:
        t["hint"] = hints.get(t["action"], "")
    result["summary"] = summary
    result["risks"] = [strip_dates(x) for x in (draft.get("risks") or [])][:4]
    email = guard_email(draft.get("email"), result) if draft.get("email") else None
    result["email"] = email or local_email(result)
    result["email_source"] = "model" if email else "local"
    result["minutes"] = rules.minutes_markdown(result, summary)
    result["mode"] = mode
    return result
