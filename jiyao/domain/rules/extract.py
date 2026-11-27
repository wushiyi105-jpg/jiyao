"""离线抽取：不依赖模型也能开工的规则版。"""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from ..catalog import decision_markers, normalize_owner
from ..models import Action, Decision

DECISION_MARKERS = decision_markers()
ACTION_MARKERS = (
    "负责", "跟进", "安排", "补", "修", "核对", "交付", "发", "改", "写",
    "给", "处理", "协调", "排期", "培训", "实现", "出", "上线", "完成",
)
TIME_MARKERS = ("下周", "本周", "这周", "月底", "今天", "明天", "后天", "之前", "月")

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
    if speaker and "我们" not in sentence:
        said = sentence[speaker.end():]
        if "我" in said and any(k in said for k in ACTION_MARKERS + TIME_MARKERS):
            return normalize_owner(speaker.group(1))
    m = OWNER_RE.search(sentence)
    return normalize_owner(m.group(1)) if m else ""


def _is_action(sentence: str) -> bool:
    owner = _owner(sentence)
    if any(k in sentence for k in DECISION_MARKERS) and not owner:
        return False
    has_verb = any(k in sentence for k in ACTION_MARKERS)
    has_time = any(k in sentence for k in TIME_MARKERS)
    return has_verb and (has_time or bool(owner))


def extract(transcript: str, today: date) -> tuple[list[Decision], list[Action]]:
    decisions: list[Decision] = []
    actions: list[Action] = []
    for sentence, offset in split_sentences(transcript):
        spoken = SPEAKER_RE.sub("", sentence).strip()
        if any(k in sentence for k in DECISION_MARKERS) and not sentence.rstrip().endswith(
            ("吗？", "吗?")
        ):
            decisions.append(Decision(text=spoken, quote=sentence.strip(), offset=offset))
        if _is_action(sentence):
            actions.append(
                Action(
                    text=spoken,
                    assignee=_owner(sentence),
                    due=parse_due(sentence, today),
                    quote=sentence.strip(),
                )
            )
    return decisions, actions
