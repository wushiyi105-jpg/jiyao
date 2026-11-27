"""端口口径：配置默认 = Dockerfile EXPOSE = CMD。"""

from __future__ import annotations

from pathlib import Path

from jiyao.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_default_port_is_8021() -> None:
    assert Settings().port == 8021


def test_dockerfile_exposes_8021() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "EXPOSE 8021" in text
    assert '"--port", "8021"' in text
