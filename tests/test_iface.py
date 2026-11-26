from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from jiyao.config import Settings
from jiyao.doctor import run_doctor
from jiyao.iface.cli import app
from jiyao.iface.web import create_app

runner = CliRunner()


def _seed(db: str) -> None:
    runner.invoke(
        app,
        ["digest", "--text", "主持人：小李负责下周三交验证脚本。", "--title", "周会", "--save", "--db", db],
    )


def test_remind_once_per_day(tmp_path):
    db = str(tmp_path / "r.db")
    runner.invoke(
        app,
        ["digest", "--text", "负责人：小李。下周一交脚本。", "--title", "周会", "--save", "--db", db],
    )
    first = runner.invoke(app, ["remind", "--db", db])
    second = runner.invoke(app, ["remind", "--db", db])
    assert first.exit_code == 0
    assert ("已提醒过" in second.stdout) or ("没有要提醒" in second.stdout)


def test_remind_force_resends(tmp_path):
    db = str(tmp_path / "f.db")
    _seed(db)
    runner.invoke(app, ["remind", "--db", db])
    forced = runner.invoke(app, ["remind", "--db", db, "--force"])
    assert forced.exit_code == 0


def test_migrate_missing_exit_2(tmp_path):
    result = runner.invoke(app, ["migrate", "--db", str(tmp_path / "none.db")])
    assert result.exit_code == 2


def test_done_missing_exit_2(tmp_path):
    result = runner.invoke(app, ["done", "999", "--db", str(tmp_path / "d.db")])
    assert result.exit_code == 2


def test_doctor_reports_offline(tmp_path):
    settings = Settings(db_path=Path(tmp_path) / "doc.db", llm_api_key="", webhook_url="")
    checks = {n: (ok, d) for n, ok, d in run_doctor(settings)}
    assert "离线模式" in checks["llm"][1]
    assert "跳过" in checks["webhook"][1]
    assert checks["database"][0] is False


def test_doctor_cli_ok_after_save(tmp_path):
    db = str(tmp_path / "ok.db")
    _seed(db)
    result = runner.invoke(app, ["doctor", "--db", db])
    assert result.exit_code == 0


def test_web_digest_and_health(tmp_path):
    settings = Settings(db_path=Path(tmp_path) / "web.db", llm_api_key="")
    client = TestClient(create_app(settings))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
    resp = client.post(
        "/digest",
        data={"transcript": "主持人：确认支付先做小额验证。小李：我下周三写脚本。", "title": "周会"},
    )
    assert resp.status_code == 200


def test_buckets_ignores_far_future():
    from jiyao.domain.models import Action
    from jiyao.domain.remind import buckets

    far = Action(text="很久以后", due=date.today() + timedelta(days=30))
    assert buckets([far], date.today())["soon"] == []
