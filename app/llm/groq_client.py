"""
app/llm/groq_client.py — Groq Cloud LLM adapter (PRIMARY provider).

Model: llama-3.3-70b-versatile
Latency: ~300ms for Text-to-SQL
Free tier: 30 RPM, 14,400 RPD — sufficient for any evaluator walkthrough.
"""
from __future__ import annotations

import re

from groq import Groq, RateLimitError, APIError

from app.config import settings
from app.llm.base import BaseLLMClient, SCHEMA_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT


def _strip_markdown(text: str) -> str:
    """Remove markdown code fences the model sometimes wraps SQL in."""
    text = re.sub(r"```(?:sql|sqlite)?", "", text, flags=re.IGNORECASE)
    text = text.replace("```", "").strip()
    # Remove leading label like "SQL:" or "Query:"
    text = re.sub(r"^(?:sql|sqlite|query)\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


class GroqClient(BaseLLMClient):
    """Groq Cloud API adapter — primary inference engine."""

    provider_name = "groq"

    def __init__(self) -> None:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set.")
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    def _chat(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            max_tokens=512,
            timeout=settings.GROQ_TIMEOUT,
        )
        return response.choices[0].message.content.strip()

    def generate_sql(self, user_query: str) -> str:
        raw = self._chat(SCHEMA_SYSTEM_PROMPT, user_query)
        return _strip_markdown(raw)

    def synthesize_answer(self, user_query: str, sql: str, results: list[dict]) -> str:
        if not results:
            return "No tickets matched your criteria in the current dataset."

        # Build a compact result representation for the synthesis prompt
        sample = results[:10]  # cap context to 10 rows
        result_text = "\n".join(str(row) for row in sample)
        total = len(results)

        user_content = (
            f"User question: {user_query}\n"
            f"SQL executed: {sql}\n"
            f"Total rows returned: {total}\n"
            f"Sample results (up to 10):\n{result_text}"
        )
        return self._chat(SYNTHESIS_SYSTEM_PROMPT, user_content)
