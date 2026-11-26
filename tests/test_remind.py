from __future__ import annotations

from datetime import date

from jiyao.adapters.store import Store
from jiyao.domain.engine import analyze
from jiyao.domain.models import Action
from jiyao.domain.remind import buckets, reminder_text

TODAY = date(2026, 11, 27)

TRANSCRIPT = (
    "主持人：把支付流程定了，先做小额支付验证。"
    "小李：我负责下周三把验证脚本写完。"
    "主持人：好，散会。"
)


def _acts() -> list[Action]:
    return [
        Action(text="过期的事", assignee="小李", due=date(2026, 11, 20)),
        Action(text="今天到期的事", assignee="老王", due=TODAY),
        Action(text="两天后到期", assignee="小张", due=date(2026, 11, 29)),
        Action(text="五天后到期", assignee="小赵", due=date(2026, 12, 2)),
        Action(text="已完成的事", assignee="小赵", due=date(2026, 11, 20), status="done"),
    ]


def test_buckets_split_by_due():
    b = buckets(_acts(), TODAY, ahead=3)
    assert [a.text for a in b["overdue"]] == ["过期的事"]
    assert [a.text for a in b["today"]] == ["今天到期的事"]
    assert [a.text for a in b["soon"]] == ["两天后到期"]


def test_reminder_text_none_when_nothing_due():
    assert reminder_text([Action(text="以后再说", due=date(2027, 1, 1))], TODAY) is None


def test_reminder_text_lists_overdue_days():
    text = reminder_text(_acts(), TODAY, ahead=3)
    assert text and "已过期 1 条" in text
    assert "逾期 7 天" in text
    assert "3 天内到期" in text


def test_store_jobs_are_idempotent(tmp_path):
    store = Store(tmp_path / "job.db")
    report = analyze(TRANSCRIPT, TODAY)
    store.save(report, "周会")
    assert store.mark_job("remind:2026-11-27", "第一次") is True
    assert store.mark_job("remind:2026-11-27", "第二次") is False
    assert store.job_keys() == ["remind:2026-11-27"]


def test_store_open_actions_and_complete(tmp_path):
    store = Store(tmp_path / "act.db")
    store.save(analyze(TRANSCRIPT, TODAY), "周会")
    ids = store.open_action_ids()
    assert ids
    assert store.complete(ids[0][0]) is True
    assert store.complete(9999) is False
    assert len(store.open_actions()) == len(ids) - 1


def test_decisions_roundtrip(tmp_path):
    store = Store(tmp_path / "dec.db")
    mid = store.save(analyze(TRANSCRIPT, TODAY), "周会")
    assert store.decisions(mid)
