"""端口：会议/决议/待办/提醒任务的读写协议。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..domain.models import Action, Decision, Report


@runtime_checkable
class LLMPort(Protocol):
    def write(self, system: str, facts: str) -> str: ...


@runtime_checkable
class StorePort(Protocol):
    def save(self, report: Report, title: str = "") -> int: ...

    def open_actions(self) -> list[Action]: ...

    def complete(self, action_id: int) -> bool: ...

    def decisions(self, meeting_id: int) -> list[Decision]: ...

    def mark_job(self, key: str, body: str, kind: str = "remind") -> bool: ...

    def job_keys(self) -> list[str]: ...
