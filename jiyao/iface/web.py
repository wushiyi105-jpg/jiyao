"""FastAPI + Jinja2。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..adapters.store import Store
from ..config import Settings
from ..domain.engine import analyze

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[2] / "templates"))


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="jiyao", version="1.0.0")
    store = Store(settings.db_path)

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(request, "index.html", {"result": None, "open": store.open_actions()})

    @app.post("/digest", response_class=HTMLResponse)
    def do_digest(request: Request, transcript: str = Form(""), title: str = Form("")) -> HTMLResponse:
        report = analyze(transcript, date.today())
        store.save(report, title)
        result = {
            "decisions": [d.text for d in report.decisions],
            "actions": [(a.text, a.assignee or "—", a.due.isoformat() if a.due else "—") for a in report.actions],
            "findings": [(f.rule_id, f.message) for f in report.findings],
        }
        return TEMPLATES.TemplateResponse(request, "index.html", {"result": result, "open": store.open_actions()})

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def app_factory(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        from ..config import settings as default_settings

        settings = default_settings
    return create_app(settings)
