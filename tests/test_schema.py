"""迁移是真的：空库 upgrade 显式建四表，downgrade base 能拆能回。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect

from jiyao.adapters.store import alembic_config


def test_upgrade_creates_four_tables(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    command.upgrade(alembic_config(db), "head")
    engine = create_engine(f"sqlite:///{db}")
    names = set(inspect(engine).get_table_names())
    assert {"meetings", "decisions", "actions", "jobs", "alembic_version"} <= names

    action_cols = {c["name"] for c in inspect(engine).get_columns("actions")}
    assert action_cols == {"id", "meeting_id", "text", "assignee", "due", "status"}


def test_downgrade_then_upgrade(tmp_path: Path) -> None:
    cfg = alembic_config(tmp_path / "round.db")
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{tmp_path / 'round.db'}")
    assert "meetings" not in set(inspect(engine).get_table_names())
    command.upgrade(cfg, "head")
    assert "meetings" in set(inspect(engine).get_table_names())
