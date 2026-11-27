from __future__ import annotations

from datetime import date

from jiyao.domain.engine import analyze, followup_email
from jiyao.domain.rules.extract import extract, parse_due, split_sentences
from jiyao.domain.rules.track import completeness, overdue, validate_quotes

TODAY = date(2026, 11, 27)

TRANSCRIPT = (
    "主持人：这周先把支付流程定了，先做小额支付验证。"
    "小李：那我负责下周把验证脚本写完。"
    "主持人：确认一下，风控先不接，等验证完再说。"
    "老王：接口文档我下周补。"
    "主持人：好，散会。"
)


def test_split_sentences_offsets_are_valid():
    for sentence, offset in split_sentences("第一句。第二句！第三句？"):
        assert "第一句" in "第一句。第二句！第三句？"
        assert offset >= 0


def test_decision_marker_detected():
    decisions, _ = extract(TRANSCRIPT, TODAY)
    assert any("支付流程" in d.text for d in decisions)


def test_action_owner_and_due():
    _, actions = extract(TRANSCRIPT, TODAY)
    owners = {a.assignee for a in actions}
    assert "李明" in owners  # 小李按 data/owner_aliases.json 归一为李明
    assert any(a.due == date(2026, 12, 4) for a in actions)  # 下周三


def test_parse_due_relative_and_absolute():
    # 2026-11-27 是周五：下周三 = 12-02
    assert parse_due("下周三给你", date(2026, 11, 27)) == date(2026, 12, 2)
    assert parse_due("本周五给", date(2026, 11, 27)) == date(2026, 11, 27)
    assert parse_due("12月5日前", date(2026, 11, 27)) == date(2026, 12, 5)
    assert parse_due("尽快", date(2026, 11, 27)) is None


def test_quote_validation_drops_unfindable():
    decisions, _ = extract(TRANSCRIPT, TODAY)
    fake = decisions[0].__class__(text="编的", quote="转写里没有这句", offset=0)
    found = validate_quotes(TRANSCRIPT, [fake], [])
    assert found and found[0].rule_id == "trace.decision"


def test_completeness_flags_missing_owner_and_due():
    from jiyao.domain.models import Action

    found = completeness([Action(text="补接口文档")])
    assert any(f.rule_id in {"action.no_owner", "action.no_due"} for f in found)


def test_overdue_detected():
    _, actions = extract(TRANSCRIPT, TODAY)
    later = date(2026, 12, 20)
    found = overdue(actions, later)
    assert any(f.rule_id == "action.overdue" for f in found)


def test_analyze_keeps_only_traceable_items():
    report = analyze(TRANSCRIPT, TODAY)
    for d in report.decisions:
        assert d.quote in TRANSCRIPT
    for a in report.actions:
        assert a.quote in TRANSCRIPT


def test_followup_email_contains_sections():
    report = analyze(TRANSCRIPT, TODAY)
    mail = followup_email(report)
    assert "已定事项" in mail and "待办" in mail
