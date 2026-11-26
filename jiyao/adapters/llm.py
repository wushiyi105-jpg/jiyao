"""模型适配：把规则抽不到的隐含待办补出来。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "extract.md"


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def extract(self, transcript: str, today: str) -> list[dict[str, Any]]:
        system = PROMPT.read_text(encoding="utf-8") if PROMPT.exists() else "抽取待办。"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"今天是 {today}\n\n转写：\n{transcript}"},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "max_tokens": 1500,
        }
        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
        try:
            return json.loads(content).get("actions", [])
        except json.JSONDecodeError:
            return []
