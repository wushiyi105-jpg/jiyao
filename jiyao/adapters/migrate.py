"""0.x → 1.0 数据迁移：旧库（meetings.topic / todos）转成新表，先备份。"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .store import ActionRow, MeetingRow, Store


def _backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = db_path.with_name(f"{db_path.stem}.bak-{stamp}.db")
    backup.write_bytes(db_path.read_bytes())
    return backup


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return None
    text = str(value).strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m月%d日"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date() if fmt != "%m月%d日" else parsed.replace(year=date.today().year).date()
        except ValueError:
            continue
    return None


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def migrate(db_path: Path) -> dict[str, Any]:
    if not db_path.exists():
        Store(db_path)
        return {"status": "created", "backup": None, "rows": 0}

    backup = _backup(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = _tables(conn)
        meeting_cols = _cols(conn, "meetings") if "meetings" in tables else set()
        if "alembic_version" in tables and "transcript" in meeting_cols:
            return {"status": "current", "backup": str(backup), "rows": 0}
        if "topic" not in meeting_cols:
            raise ValueError("库里有未知表结构，未改动原文件")
        meetings = conn.execute("SELECT * FROM meetings ORDER BY id").fetchall()
        todos = []
        if "todos" in tables:
            todos = conn.execute("SELECT * FROM todos ORDER BY id").fetchall()
    finally:
        conn.close()

    tmp = db_path.with_name(db_path.stem + ".migrating.db")
    if tmp.exists():
        tmp.unlink()
    try:
        store = Store(tmp)
        id_map: dict[int, int] = {}
        with store.session_factory() as s:
            for m in meetings:
                detail = m["detail"] or ""
                try:
                    transcript = json.loads(detail).get("transcript") or detail
                except (TypeError, ValueError):
                    transcript = detail
                row = MeetingRow(
                    title=(m["topic"] or "")[:200],
                    transcript=str(transcript)[:20000],
                    created_on=_parse_date(m["held_on"]) or date.today(),
                )
                s.add(row)
                s.flush()
                id_map[m["id"]] = row.id
            for t in todos:
                s.add(
                    ActionRow(
                        meeting_id=id_map.get(t["meeting_id"], 0),
                        text=(t["action"] or "")[:500],
                        assignee=(t["owner"] or "")[:40],
                        due=_parse_date(t["due"]),
                        status="done" if t["complete"] else "open",
                    )
                )
            s.commit()
        store.engine.dispose()
        tmp.replace(db_path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
    return {"status": "converted", "backup": str(backup), "rows": len(meetings) + len(todos)}
