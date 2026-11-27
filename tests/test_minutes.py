"""新功能：三件套成文、3 场种子会议、模板与别名。"""

from __future__ import annotations

from typer.testing import CliRunner

from jiyao.domain.catalog import owner_aliases, patterns, templates
from jiyao.iface.cli import app

runner = CliRunner()


def test_catalog_counts() -> None:
    assert len(templates()) == 3
    assert len(patterns()) == 12
    assert len(owner_aliases()) == 14


def test_seed_three_meetings(tmp_path) -> None:
    result = runner.invoke(app, ["seed", "--db", str(tmp_path / "seed.db")])
    assert result.exit_code == 0
    assert "共 3 场会议" in result.output
    assert "启动会" in result.output


def test_minutes_writes_three_pieces(tmp_path) -> None:
    db = str(tmp_path / "m.db")
    runner.invoke(app, ["seed", "--db", db])
    out = tmp_path / "纪要.md"
    result = runner.invoke(app, ["minutes", "--meeting", "1", "--db", db, "--out", str(out)])
    assert result.exit_code == 0
    body = out.read_text(encoding="utf-8")
    assert "## 一、结论" in body
    assert "原文（第" in body
    assert "## 四、邮件草稿" in body
    assert "## 五、群消息" in body


def test_minutes_rejects_bad_template(tmp_path) -> None:
    result = runner.invoke(
        app,
        ["minutes", "--text", "主持人：决定先做小程序。", "--template", "nope", "--db", str(tmp_path / "x.db")],
    )
    assert result.exit_code == 2
