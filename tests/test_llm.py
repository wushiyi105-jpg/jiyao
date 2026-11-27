from __future__ import annotations

from datetime import date

from jiyao.app.run import digest
from jiyao.ports import LLMPort


class FakeLLM:
    def write(self, system: str, facts: str) -> str:
        return "会议确认了支付小额验证和脚本交付，风险是责任人未填。"


def test_digest_uses_model_summary() -> None:
    llm: LLMPort = FakeLLM()
    report = digest("主持人：确认支付先做小额验证。小李：我下周三写脚本。", date(2026, 11, 27), llm)
    assert report.decisions
    assert report.summary.startswith("会议确认")


class BrokenLLM:
    def write(self, system: str, facts: str) -> str:
        raise RuntimeError("offline")


def test_digest_keeps_local_result_when_model_fails() -> None:
    report = digest("主持人：确认支付先做小额验证。", date(2026, 11, 27), BrokenLLM())
    assert report.summary == ""
    assert report.decisions
