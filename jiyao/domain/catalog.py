"""本地会议知识：模板、决议句式、责任人别名。模型挂了也不影响抽取。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[2] / "data"


def _load(name: str) -> dict[str, Any]:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def templates() -> list[dict[str, Any]]:
    return list(_load("meeting_templates.json")["templates"])


@lru_cache(maxsize=1)
def patterns() -> list[dict[str, Any]]:
    return list(_load("decision_patterns.json")["patterns"])


@lru_cache(maxsize=1)
def owner_aliases() -> dict[str, str]:
    return dict(_load("owner_aliases.json")["aliases"])


@lru_cache(maxsize=1)
def seed_meetings() -> list[dict[str, Any]]:
    return list(_load("seed_meetings.json")["meetings"])


def decision_markers() -> tuple[str, ...]:
    base = ("决定", "确认", "敲定", "定为", "通过", "同意", "定了", "就这么")
    extra = tuple(str(p["keyword"]) for p in patterns() if p["keyword"] not in base)
    return base + extra


def template_by_id(template_id: str) -> dict[str, Any] | None:
    for item in templates():
        if item["id"] == template_id:
            return item
    return None


def template_for(title: str) -> dict[str, Any] | None:
    """标题里带“周会 / 复盘 / 启动会”就自动匹配；匹配不到返回 None。"""
    for item in templates():
        if item["id"] in title or item["name"] in title:
            return item
    return None


def normalize_owner(name: str) -> str:
    return owner_aliases().get(name, name)


def transcript_path(rel: str) -> Path:
    return DATA / rel
