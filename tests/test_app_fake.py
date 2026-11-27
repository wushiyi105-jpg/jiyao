"""内存假实现跑 digest_and_save，全程不建 SQLite 文件。"""

from __future__ import annotations

from datetime import date

from jiyao.app.run import digest_and_save
from jiyao.domain.models import Action, Decision, Report
from jiyao.ports import StorePort


class InMemoryStore:
    def __init__(self) -> None:
        self.saved: list[tuple[Report, str]] = []

    def save(self, report: Report, title: str = "") -> int:
        self.saved.append((report, title))
        return 3

    def open_actions(self) -> list[Action]:
        return []

    def complete(self, action_id: int) -> bool:
        return False

    def decisions(self, meeting_id: int) -> list[Decision]:
        return []

    def mark_job(self, key: str, body: str, kind: str = "remind") -> bool:
        return True

    def job_keys(self) -> list[str]:
        return []


def test_digest_and_save_with_fake_store() -> None:
    fake = InMemoryStore()
    store: StorePort = fake
    report, mid = digest_and_save(store, "主持人：下周三前交验证脚本。小李：我负责。", date(2026, 11, 27), "周会")
    assert mid == 3
    assert report.actions
    assert fake.saved[0][1] == "周会"
