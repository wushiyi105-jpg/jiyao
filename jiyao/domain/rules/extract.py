"""离线抽取：不依赖模型也能开工的规则版。"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from ..models import Action, Decision

DECISION_MARKERS = ("决定", "确认", "敲定", "定为", "通过", "同意", "定了", "就这么")
ACTION_MARKERS = ("负责", "跟进", "下周", "本周", "月底", "之前", "安排", "补")

CN_NUM = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
SPEAKER_RE = re.compile(r"^([\u4e00-\u9fa5]{2,4})[：:]")
OWNER_RE = re.compile(r"(?:由|让|请)\s*([\u4e00-\u9fa5]{2,4})\s*(?:负责|跟进|来做)")


def split_sentences(text: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    start = 0
    for m in re.finditer(r"[。！？\n]", text):
        seg = text[start : m.start() + 1].strip()
        if seg:
            out.append((seg, start))
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append((tail, start))
    return out


def _next_week_start(today: date) -> date:
    """下周一。"""
    days_to_next_monday = 7 - today.weekday()
    return today + timedelta(days=days_to_next_monday)


def parse_due(sentence: str, today: date) -> date | None:
    if "月底" in sentence:
        last = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last)

    m = re.search(r"(下|本|这)周([一二三四五六日天])", sentence)
    if m:
        prefix, cn = m.group(1), m.group(2)
        offset = CN_NUM[cn]
        if prefix == "下":
            return _next_week_start(today) + timedelta(days=offset)
        # 本周 / 这周：本周内，已过则顺延到下周
        monday = today - timedelta(days=today.weekday())
        candidate = monday + timedelta(days=offset)
        return candidate if candidate >= today else candidate + timedelta(days=7)

    if "下周" in sentence:
        return today + timedelta(days=7)
    if "本周" in sentence or "这周" in sentence:
        return today + timedelta(days=7 - today.weekday())
    if "今天" in sentence:
        return today
    if "明天" in sentence:
        return today + timedelta(days=1)
    if "后天" in sentence:
        return today + timedelta(days=2)

    m = re.search(r"(\d{1,2})月(\d{1,2})[日号]", sentence)
    if m:
        try:
            return date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def _owner(sentence: str) -> str:
    speaker = SPEAKER_RE.match(sentence)
    if speaker and any(k in sentence for k in ("我负责", "我来", "我补", "我跟进")):
        return speaker.group(1)
    m = OWNER_RE.search(sentence)
    return m.group(1) if m else ""


def extract(transcript: str, today: date) -> tuple[list[Decision], list[Action]]:
    decisions: list[Decision] = []
    actions: list[Action] = []
    for sentence, offset in split_sentences(transcript):
        if any(k in sentence for k in DECISION_MARKERS):
            decisions.append(Decision(text=sentence.strip(), quote=sentence.strip(), offset=offset))
        if any(k in sentence for k in ACTION_MARKERS):
            actions.append(
                Action(
                    text=sentence.strip(),
                    assignee=_owner(sentence),
                    due=parse_due(sentence, today),
                    quote=sentence.strip(),
                )
            )
    return decisions, actions
