"""CLI：Typer + rich。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ..adapters.store import Store
from ..app.run import digest as run_digest
from ..app.run import digest_and_save, finish, open_actions, reminder
from ..app.run import email as build_email
from ..config import settings as base_settings

app = typer.Typer(add_completion=False, help="jiyao —— 会议纪要与决议追踪")
console = Console()


def _settings(db: Path | None):
    return base_settings.model_copy(update={"db_path": db}) if db else base_settings


@app.command()
def digest(
    file: Path = typer.Option(None, "--file", help="转写文件（.txt/.md）"),
    text: str = typer.Option(None, "--text", help="直接给一段转写"),
    title: str = typer.Option("", help="会议标题"),
    save: bool = typer.Option(False, "--save", help="写入数据库"),
    as_json: bool = typer.Option(False, "--json"),
    db: Path = typer.Option(None),
) -> None:
    """把一段会议转写变成决议与待办。"""
    if file is None and text is None:
        console.print("[red]需要 --file 或 --text[/]")
        raise typer.Exit(code=2)
    transcript = file.read_text(encoding="utf-8") if file else (text or "")
    store = Store(_settings(db).db_path)
    if save:
        report, meeting_id = digest_and_save(store, transcript, date.today(), title)
        console.print(f"[green]已保存[/] 会议 #{meeting_id}")
    else:
        report = run_digest(transcript, date.today())

    if as_json:
        console.print_json(json.dumps({
            "decisions": [d.text for d in report.decisions],
            "actions": [
                {"text": a.text, "assignee": a.assignee, "due": a.due.isoformat() if a.due else None}
                for a in report.actions
            ],
            "findings": [{"rule": f.rule_id, "message": f.message} for f in report.findings],
        }, ensure_ascii=False))
        return

    if report.decisions:
        console.print("[bold]已定事项[/]")
        for d in report.decisions:
            console.print(f"  · {d.text}")
    if report.actions:
        console.print("\n[bold]待办[/]")
        table = Table()
        for col in ("事项", "负责人", "期限"):
            table.add_column(col)
        for a in report.actions:
            table.add_row(a.text[:40], a.assignee or "—", a.due.isoformat() if a.due else "—")
        console.print(table)
    if report.findings:
        console.print("\n[bold]问题[/]")
        for f in report.findings:
            color = "red" if f.severity == "high" else "yellow"
            console.print(f"  · [{color}]{f.rule_id}[/] {f.message}")


@app.command()
def email(file: Path = typer.Option(..., "--file")) -> None:
    """生成跟进邮件。"""
    console.print(build_email(file.read_text(encoding="utf-8"), date.today()))


@app.command()
def actions(db: Path = typer.Option(None)) -> None:
    """所有未完成待办。"""
    store = Store(_settings(db).db_path)
    rows = open_actions(store)
    if not rows:
        console.print("[green]没有未完成待办[/]")
        return
    table = Table(title=f"未完成 {len(rows)} 条")
    for col in ("事项", "负责人", "期限", "状态"):
        table.add_column(col)
    for a in rows:
        table.add_row(a.text[:40], a.assignee or "—", a.due.isoformat() if a.due else "—", a.status)
    console.print(table)


@app.command()
def done(action_id: int, db: Path = typer.Option(None)) -> None:
    """标记完成。"""
    if not finish(Store(_settings(db).db_path), action_id):
        console.print(f"[red]没有这条待办[/] #{action_id}")
        raise typer.Exit(code=2)
    console.print(f"[green]已完成[/] #{action_id}")


@app.command()
def remind(db: Path = typer.Option(None), force: bool = typer.Option(False, "--force")) -> None:
    """今天的待办提醒：过期 / 今天到期 / 三天内，同一天只发一条。"""

    settings = _settings(db)
    store = Store(settings.db_path)
    text = reminder(store, date.today(), settings.remind_ahead_days)
    if not text:
        console.print("[green]今天没有要提醒的待办[/]")
        return
    key = f"remind:{date.today().isoformat()}"
    fresh = store.mark_job(key, text)
    if not fresh and not force:
        console.print(f"[yellow]{key} 已提醒过[/]，加 --force 可重发")
        return
    console.print(text)
    if settings.webhook_url:
        import httpx

        resp = httpx.post(
            settings.webhook_url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10,
        )
        console.print(f"[dim]webhook HTTP {resp.status_code}[/]")


@app.command()
def migrate(db: Path = typer.Option(None)) -> None:
    """0.x 旧库迁到 1.0（meetings.topic / todos），先备份。"""
    from ..adapters.migrate import migrate as run_migrate

    path = _settings(db).db_path
    if not path.exists():
        console.print(f"[red]没有这个库：{path}[/]")
        raise typer.Exit(code=2)
    try:
        result = run_migrate(path)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]迁移失败，原文件未改动[/] {exc}")
        raise typer.Exit(code=2) from exc
    if result["status"] == "current":
        console.print("[green]已是最新 schema[/]")
        return
    console.print(f"[green]{result['status']}[/] 转换 {result['rows']} 行，备份 {result['backup']}")


@app.command()
def doctor(db: Path = typer.Option(None)) -> None:
    """环境自检：配置 / 数据库 / 模型 / webhook。"""
    from ..doctor import run_doctor

    bad = 0
    for name, ok, detail in run_doctor(_settings(db)):
        console.print(f"{'[green]ok[/]' if ok else '[red]fail[/]'}  {name:10} {detail}")
        bad += 0 if ok else 1
    raise typer.Exit(code=1 if bad else 0)


@app.command()
def serve(port: int = typer.Option(0, help="0 表示用配置里的 8021"), db: Path = typer.Option(None)) -> None:
    """Web 界面。"""
    import uvicorn

    from .web import app_factory

    settings = _settings(db)
    uvicorn.run(app_factory(settings), host="127.0.0.1", port=port or settings.port)


if __name__ == "__main__":  # pragma: no cover
    app()
