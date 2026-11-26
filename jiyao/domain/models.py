"""领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Decision:
    text: str
    quote: str  # 原文片段，必须能在转写里找到
    offset: int  # 在转写里的起始位置


@dataclass(frozen=True)
class Action:
    text: str
    assignee: str = ""
    due: date | None = None
    quote: str = ""
    status: str = "open"  # open / done


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    evidence: str
    suggestion: str = ""


@dataclass
class Report:
    transcript: str
    decisions: list[Decision] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def unassigned(self) -> list[Action]:
        return [a for a in self.actions if not a.assignee]

    @property
    def undated(self) -> list[Action]:
        return [a for a in self.actions if a.due is None]
