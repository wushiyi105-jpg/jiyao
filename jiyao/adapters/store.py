"""SQLite：会议、决议、待办、提醒任务 + Alembic 建表。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Date, Integer, String, create_engine, inspect, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from ..domain.models import Action, Decision, Report

MIGRATIONS_DIR = Path(__file__).resolve().parents[2]


class Base(DeclarativeBase):
    pass


class MeetingRow(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    transcript: Mapped[str] = mapped_column(String)
    created_on: Mapped[date] = mapped_column(Date, default=date.today)


class DecisionRow(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(String(500))
    quote: Mapped[str] = mapped_column(String(500))
    offset: Mapped[int] = mapped_column(Integer, default=0)


class ActionRow(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(String(500))
    assignee: Mapped[str] = mapped_column(String(40), default="")
    due: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(String(12), default="open")


class JobRow(Base):
    """提醒任务：key 唯一，保证同一天只发一条。"""

    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="remind")
    body: Mapped[str] = mapped_column(String, default="")
    created_on: Mapped[date] = mapped_column(Date, default=date.today)


def alembic_config(db_path: Path) -> Config:
    cfg = Config(str(MIGRATIONS_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def ensure_schema(db_path: Path, engine) -> None:
    tables = set(inspect(engine).get_table_names())
    cfg = alembic_config(db_path)
    if "alembic_version" not in tables:
        if tables:
            command.stamp(cfg, "head")
        else:
            command.upgrade(cfg, "head")
        return
    command.upgrade(cfg, "head")


class Store:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", future=True)
        ensure_schema(db_path, self.engine)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    def save(self, report: Report, title: str = "") -> int:
        with self.session_factory() as s:
            meeting = MeetingRow(title=title[:200], transcript=report.transcript)
            s.add(meeting)
            s.flush()
            for d in report.decisions:
                s.add(
                    DecisionRow(
                        meeting_id=meeting.id, text=d.text[:500], quote=d.quote[:500], offset=d.offset
                    )
                )
            for a in report.actions:
                s.add(
                    ActionRow(
                        meeting_id=meeting.id,
                        text=a.text[:500],
                        assignee=a.assignee,
                        due=a.due,
                    )
                )
            s.commit()
            return meeting.id

    def open_actions(self) -> list[Action]:
        with self.session_factory() as s:
            rows = s.scalars(select(ActionRow).where(ActionRow.status == "open")).all()
            return [Action(text=r.text, assignee=r.assignee, due=r.due, status=r.status) for r in rows]

    def open_action_ids(self) -> list[tuple[int, str]]:
        with self.session_factory() as s:
            rows = s.scalars(select(ActionRow).where(ActionRow.status == "open")).all()
            return [(r.id, r.text) for r in rows]

    def complete(self, action_id: int) -> bool:
        with self.session_factory() as s:
            row = s.get(ActionRow, action_id)
            if not row:
                return False
            row.status = "done"
            s.commit()
            return True

    def decisions(self, meeting_id: int) -> list[Decision]:
        with self.session_factory() as s:
            rows = s.scalars(select(DecisionRow).where(DecisionRow.meeting_id == meeting_id)).all()
            return [Decision(text=r.text, quote=r.quote, offset=r.offset) for r in rows]

    def meeting(self, meeting_id: int) -> tuple[str, str] | None:
        """返回 (标题, 转写)；找不到返回 None。"""
        with self.session_factory() as s:
            row = s.get(MeetingRow, meeting_id)
            return (row.title, row.transcript) if row else None

    def mark_job(self, key: str, body: str, kind: str = "remind") -> bool:
        """写入提醒任务；同 key 已存在返回 False（幂等）。"""
        with self.session_factory() as s:
            exists = s.scalar(select(JobRow).where(JobRow.key == key))
            if exists:
                return False
            s.add(JobRow(key=key, kind=kind, body=body))
            s.commit()
            return True

    def job_keys(self) -> list[str]:
        with self.session_factory() as s:
            return list(s.scalars(select(JobRow.key)).all())
