"""
app/llm/gemini_client.py — Google Gemini adapter (SECONDARY provider).

Strictly optional: only added to the cascade when GEMINI_API_KEY is present.
Uses the new google-genai SDK (google.genai) — replaces deprecated google.generativeai.
Model: gemini-1.5-flash (fastest free-tier Gemini model)
"""
from __future__ import annotations

import re

from google import genai
from google.genai import types as genai_types

from app.config import settings
from app.llm.base import BaseLLMClient, SCHEMA_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```(?:sql|sqlite)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    text = re.sub(r"^(?:sql|sqlite|query)\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


class GeminiClient(BaseLLMClient):
    """Google Gemini Flash adapter — secondary cloud inference engine."""

    provider_name = "gemini"

    def __init__(self) -> None:
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set — Gemini client cannot be initialised. "
                "This is expected; the cascade will skip Gemini automatically."
            )
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_MODEL

    def _generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=512,
            ),
        )
        return response.text.strip()

    def generate_sql(self, user_query: str) -> str:
        prompt = f"{SCHEMA_SYSTEM_PROMPT}\n\nUser question: {user_query}\nSQL query:"
        raw = self._generate(prompt)
        return _strip_markdown(raw)

    def synthesize_answer(self, user_query: str, sql: str, results: list[dict]) -> str:
        if not results:
            return "No tickets matched your criteria in the current dataset."

        sample = results[:10]
        result_text = "\n".join(str(row) for row in sample)
        total = len(results)

        prompt = (
            f"{SYNTHESIS_SYSTEM_PROMPT}\n\n"
            f"User question: {user_query}\n"
            f"SQL executed: {sql}\n"
            f"Total rows returned: {total}\n"
            f"Sample results:\n{result_text}"
        )
        return self._generate(prompt)
