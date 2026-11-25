"""SQLite persistence for meeting minutes."""

import json
import os
import sqlite3
import threading

DB_PATH = os.environ.get("JIYAO_DB") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jiyao.db")
_LOCK = threading.Lock()
_LOCAL = threading.local()


def use(path):
    global DB_PATH
    if path:
        DB_PATH = path
        _LOCAL.conn = None


def connect():
    conn = getattr(_LOCAL, "conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT, held_on TEXT, participants TEXT, template TEXT,
            decisions INTEGER, todos INTEGER, open_items INTEGER,
            detail TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER, action TEXT, owner TEXT, due TEXT,
            complete INTEGER, detail TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit()
        _LOCAL.conn = conn
    return conn


def save(result):
    with _LOCK:
        conn = connect()
        cur = conn.execute(
            "INSERT INTO meetings(topic, held_on, participants, template, decisions, todos, open_items, detail)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (result["topic"], result["date"], "、".join(result["participants"]),
             result["template"], len(result["decisions"]), len(result["todos"]),
             len(result["suspended"]), json.dumps(result, ensure_ascii=False)))
        mid = cur.lastrowid
        for t in result["todos"]:
            conn.execute("INSERT INTO todos(meeting_id, action, owner, due, complete, detail) VALUES (?,?,?,?,?,?)",
                         (mid, t["action"], t["owner"], t["due"], int(t["complete"]),
                          json.dumps(t, ensure_ascii=False)))
        conn.commit()
        return mid


def meetings(limit=20):
    with _LOCK:
        rows = connect().execute(
            "SELECT id, topic, held_on, participants, template, decisions, todos, open_items, created_at"
            " FROM meetings ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def open_todos():
    with _LOCK:
        rows = connect().execute(
            "SELECT id, action, owner, due, complete FROM todos WHERE complete = 0 ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]
