"""
app/llm/ollama_client.py — Local Ollama adapter (TERTIARY / offline provider).

Connects to local Ollama server (http://localhost:11434).
Default model: qwen2.5-coder:7b (already installed on your NVIDIA GPU).

Advantages:
  • Zero API cost, zero egress, unlimited requests.
  • Runs fully offline — perfect for the live 30-minute walkthrough call.
  • qwen2.5-coder is purpose-built for code/SQL generation tasks.
"""
from __future__ import annotations

import re

import requests

from app.config import settings
from app.llm.base import BaseLLMClient, SCHEMA_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```(?:sql|sqlite)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    text = re.sub(r"^(?:sql|sqlite|query)\s*:\s*", "", text, flags=re.IGNORECASE)
    # Take only first non-empty line (models sometimes add commentary after)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Find the line that starts with SELECT
    for line in lines:
        if line.upper().startswith("SELECT"):
            return line
    return lines[0] if lines else text


class OllamaClient(BaseLLMClient):
    """Local Ollama inference adapter — fully offline, GPU-accelerated."""

    provider_name = "ollama"

    def __init__(self) -> None:
        self._base_url = settings.OLLAMA_BASE_URL
        self._model = settings.OLLAMA_MODEL
        self._generate_url = f"{self._base_url}/api/generate"

    def _call(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 512,
            },
        }
        resp = requests.post(
            self._generate_url,
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    def generate_sql(self, user_query: str) -> str:
        prompt = (
            f"{SCHEMA_SYSTEM_PROMPT}\n\n"
            f"User question: {user_query}\n"
            "SQL query (SELECT only, no explanation):"
        )
        raw = self._call(prompt)
        return _strip_markdown(raw)

    def synthesize_answer(self, user_query: str, sql: str, results: list[dict]) -> str:
        if not results:
            return "No tickets matched your criteria in the current dataset."

        sample = results[:5]  # smaller context for local model
        result_text = "\n".join(str(row) for row in sample)
        total = len(results)

        prompt = (
            f"{SYNTHESIS_SYSTEM_PROMPT}\n\n"
            f"User question: {user_query}\n"
            f"Total rows returned: {total}\n"
            f"Sample results:\n{result_text}\n"
            "Answer:"
        )
        return self._call(prompt)
