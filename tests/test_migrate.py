from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from jiyao.adapters.migrate import migrate
from jiyao.adapters.store import Store


def _legacy(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE meetings (id INTEGER PRIMARY KEY, topic TEXT, held_on TEXT, participants TEXT,"
        " template TEXT, decisions INTEGER, todos INTEGER, open_items INTEGER, detail TEXT)"
    )
    conn.execute(
        "CREATE TABLE todos (id INTEGER PRIMARY KEY, meeting_id INTEGER, action TEXT, owner TEXT,"
        " due TEXT, complete INTEGER, detail TEXT)"
    )
    conn.execute(
        "INSERT INTO meetings (id,topic,held_on,detail) VALUES (1,?,?,?)",
        ("支付评审", "2026-11-20", json.dumps({"transcript": "讨论支付流程"}, ensure_ascii=False)),
    )
    conn.execute(
        "INSERT INTO todos (meeting_id,action,owner,due,complete) VALUES (?,?,?,?,?)",
        (1, "补接口文档", "老王", "2026-11-25", 0),
    )
    conn.commit()
    conn.close()


def test_migrate_legacy_tables(tmp_path):
    db = tmp_path / "old.db"
    _legacy(db)
    result = migrate(db)
    assert result["status"] == "converted"
    assert result["rows"] == 2
    store = Store(db)
    assert store.open_actions()[0].text == "补接口文档"
    assert store.decisions(1) == []


def test_migrate_unknown_schema_keeps_file(tmp_path):
    db = tmp_path / "odd.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE strange (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError):
        migrate(db)
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()[0] == "strange"
    conn.close()


def test_migrate_current_and_missing(tmp_path):
    db = tmp_path / "new.db"
    Store(db).job_keys()
    assert migrate(db)["status"] == "current"
    assert migrate(tmp_path / "absent.db")["status"] == "created"
