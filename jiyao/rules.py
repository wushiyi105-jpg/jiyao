"""Local extraction: people, dates, numbers, todos, decisions, suspended issues."""

import json
import os
import re
from datetime import date, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_CACHE = {}


def load(name):
    if name not in _CACHE:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            _CACHE[name] = json.load(f)
    return _CACHE[name]


def meeting():
    return load("meeting.json")


WEEK = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
SPEAKER_RE = re.compile(r"^(?:\[\d{1,2}:\d{2}(?::\d{2})?\]\s*)?([^\s:：,，]{1,12})\s*[:：]\s*(.*)$")
MONTH_DAY_RE = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*(?:日|号)")
ISO_RE = re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def parse_date(text, base=None):
    """Return date from an explicit date in the header, else base/default today."""
    base = base or date.today()
    iso = ISO_RE.search(text or "")
    if iso:
        y, m, d = (int(x) for x in iso.groups())
        try:
            return date(y, m, d)
        except ValueError:
            return base
    md = MONTH_DAY_RE.search(text or "")
    if md:
        m, d = int(md.group(1)), int(md.group(2))
        try:
            return date(base.year, m, d)
        except ValueError:
            return base
    return base


def parse_header(text):
    first_lines = "\n".join((text or "").splitlines()[:4])
    topic = None
    m = re.search(r"(?:主题|议题|会议)\s*[:：]\s*(.+)", first_lines)
    if m:
        topic = m.group(1).strip().splitlines()[0]
    elif first_lines.strip():
        topic = first_lines.strip().splitlines()[0][:40]
    if topic:
        topic = re.split(r"\s*(?:参会|参与|参加|出席)\s*[:：]", topic)[0]
        topic = ISO_RE.sub("", topic)
        topic = MONTH_DAY_RE.sub("", topic).strip(" ，,")
    people = []
    for kw in ("参会", "参与", "参加", "出席"):
        m = re.search(kw + r"\s*[:：]\s*(.+)", first_lines)
        if m:
            people = [x.strip(" 、,，和及") for x in re.split(r"[、,，/]", m.group(1)) if x.strip()]
            break
    return topic, people, parse_date(first_lines)


def lines(text):
    out = []
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = SPEAKER_RE.match(raw)
        if m:
            out.append((m.group(1), m.group(2).strip()))
        else:
            out.append((None, raw))
    return out


def people(text, participants=None):
    known = list(participants or [])
    found = []
    for speaker, body in lines(text):
        if speaker and speaker not in ("会议", "主题", "参会", "记录"):
            if speaker not in found:
                found.append(speaker)
        for name in known:
            if name and name in body and name not in found:
                found.append(name)
    return found


def dates_in(text, base=None):
    """All resolvable date expressions in a sentence, with their phrase."""
    base = base or date.today()
    hits = []
    iso = ISO_RE.search(text or "")
    if iso:
        y, m, d = (int(x) for x in iso.groups())
        try:
            hits.append((iso.group(0), date(y, m, d)))
        except ValueError:
            pass
    md = MONTH_DAY_RE.search(text or "")
    if md:
        m, d = int(md.group(1)), int(md.group(2))
        try:
            hits.append((md.group(0), date(base.year, m, d)))
        except ValueError:
            pass
    for word, delta in meeting()["deadline_words"].items():
        if word in (text or ""):
            hits.append((word, base + timedelta(days=delta)))
    for key in ("本周", "下周", "这周"):
        m = re.search(key + r"[一二三四五六日天]", text or "")
        if m:
            sign = 1 if key == "下周" else 0
            target = WEEK[m.group(0)[-1]]
            monday = base - timedelta(days=base.weekday())
            hits.append((m.group(0), monday + timedelta(days=7 * sign + target - 1)))
    if "月底" in (text or ""):
        nxt = date(base.year + (base.month == 12), base.month % 12 + 1, 1)
        hits.append(("月底", nxt - timedelta(days=1)))
    return hits


def first_date(text, base=None):
    hits = dates_in(text, base)
    return hits[0] if hits else (None, None)


def numbers(text):
    return [x.group(0) for x in NUM_RE.finditer(text or "")]


def sentences(text):
    out = []
    for speaker, body in lines(text):
        for piece in re.split(r"[。！？；\n]", body):
            piece = piece.strip()
            if piece:
                out.append((speaker, piece))
    return out


def decisions(text, base=None):
    out = []
    for speaker, s in sentences(text):
        if any(m in s for m in meeting()["decision_markers"]) and not any(
                m in s for m in meeting()["suspend_markers"]):
            out.append({"text": s, "speaker": speaker, "date": None})
    return out


def suspended(text):
    out = []
    for speaker, s in sentences(text):
        if any(m in s for m in meeting()["suspend_markers"]):
            out.append({"text": s, "speaker": speaker, "question": _question(s)})
    return out


def _question(s):
    s = s.strip()
    for m in meeting()["suspend_markers"]:
        s = s.replace(m, "")
    s = s.strip(" ，,。；")
    return s + " —— 需要下次会上明确结论" if s else "未明确结论，需要下次会上定"


def todos(text, participants=None, base=None):
    base = base or date.today()
    names = people(text, participants)
    verbs = meeting()["verbs"]
    out = []
    for speaker, s in sentences(text):
        if any(m in s for m in meeting()["decision_markers"]) or any(
                m in s for m in meeting()["suspend_markers"]):
            continue
        owner = None
        for name in names:
            if name and name in s:
                owner = name
                break
        if owner is None and speaker in names:
            owner = speaker
        verb = next((v for v in verbs if v in s), None)
        if owner is None or verb is None:
            continue
        phrase, due = first_date(s, base)
        dependency = next((d for d in meeting()["dependency_markers"] if d in s), None)
        vague = next((v for v in meeting()["vague"] if v in s), None)
        missing = []
        if not owner:
            missing.append("负责人")
        if not due:
            missing.append("截止")
        if not verb:
            missing.append("动作")
        out.append({
            "action": s,
            "owner": owner,
            "verb": verb,
            "due": due.isoformat() if due else None,
            "due_phrase": phrase,
            "dependency": dependency,
            "vague": vague,
            "missing": missing,
            "complete": not missing,
        })
    return out


def overdue(todo_list, today=None):
    today = today or date.today()
    out = []
    for t in todo_list:
        if t.get("due") and date.fromisoformat(t["due"]) < today:
            out.append(t)
    return out


def vague_hits(text):
    return [{"word": w, "count": (text or "").count(w)} for w in meeting()["vague"] if w in (text or "")]


def agenda(suspended_list, todo_list, today=None):
    items = []
    for s in suspended_list:
        items.append({"type": "悬置", "text": s["question"], "owner": s.get("speaker")})
    for t in overdue(todo_list, today):
        items.append({"type": "超期", "text": "%s 的「%s」应于 %s 完成" % (t["owner"], t["action"], t["due"]),
                      "owner": t["owner"]})
    for t in todo_list:
        if not t["complete"] and not t.get("due"):
            items.append({"type": "待补", "text": "%s 的「%s」缺截止时间" % (t["owner"], t["action"]),
                          "owner": t["owner"]})
    return items


def template_for(topic):
    name = None
    if topic:
        for t in meeting()["templates"]:
            if t["name"] in topic:
                name = t["name"]
                break
    return next((t for t in meeting()["templates"] if t["name"] == name), meeting()["templates"][0])


def analyze(text, topic=None, participants=None, meeting_date=None, today=None):
    base = parse_date(meeting_date, date.today()) if meeting_date else parse_header(text)[2]
    head_topic, head_people, _ = parse_header(text)
    topic = topic or head_topic or "会议"
    participants = participants or head_people
    names = people(text, participants)
    todo_list = todos(text, names, base)
    result = {
        "topic": topic,
        "date": base.isoformat(),
        "participants": names,
        "template": template_for(topic)["name"],
        "decisions": decisions(text, base),
        "suspended": suspended(text),
        "todos": todo_list,
        "overdue": [t["action"] for t in overdue(todo_list, today)],
        "vague": vague_hits(text),
        "agenda": agenda(suspended(text), todo_list, today),
        "numbers": numbers(text),
    }
    return result


def minutes_markdown(result, summary=None):
    tpl = template_for(result["template"])
    out = ["# %s · %s 会议纪要" % (result["topic"], result["date"]), ""]
    out.append("**模板**:%s · **参会**:%s" % (tpl["name"], "、".join(result["participants"]) or "未列明"))
    out.append("")
    if summary:
        out += ["## 摘要", "", summary, ""]
    out += ["## 决议", ""]
    if result["decisions"]:
        for i, d in enumerate(result["decisions"], 1):
            out.append("%d. %s" % (i, d["text"]))
            if d["speaker"]:
                out.append("   - 发言:%s" % d["speaker"])
    else:
        out.append("本次未记录到明确决议。")
    out += ["", "## 待办", "", "| # | 动作 | 负责人 | 截止 | 依赖 | 完整性 |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(result["todos"], 1):
        mark = "✅" if t["complete"] else "⚠️ 缺 " + "、".join(t["missing"])
        out.append("| %d | %s | %s | %s | %s | %s |" % (
            i, t["action"], t["owner"], t["due"] or "—", t["dependency"] or "—", mark))
    if not result["todos"]:
        out.append("| — | 无 | — | — | — | — |")
    out += ["", "## 悬置问题", ""]
    if result["suspended"]:
        for s in result["suspended"]:
            out.append("- %s(%s)" % (s["question"], s["speaker"]))
    else:
        out.append("无")
    out += ["", "## 下次议程", ""]
    if result["agenda"]:
        for a in result["agenda"]:
            out.append("- [%s] %s" % (a["type"], a["text"]))
    else:
        out.append("无待定项。")
    return "\n".join(out)

