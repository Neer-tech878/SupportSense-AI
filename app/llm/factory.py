"""
app/llm/factory.py — LLM provider cascade factory.

Implements the three-tier failover strategy:
  [1] Groq Cloud      (PRIMARY  — sub-400ms, 30 RPM free)
  [2] Gemini Flash    (SECONDARY — optional, only if GEMINI_API_KEY set)
  [3] Local Ollama    (TERTIARY  — fully offline, NVIDIA GPU)
  [4] Structured fallback response (server NEVER crashes)

Gemini is STRICTLY OPTIONAL: if GEMINI_API_KEY is absent or empty, the
cascade silently skips it and goes directly Groq → Ollama.

Design: LLMCascade wraps a list of BaseLLMClient instances.  On each call it
tries providers in order, catching ALL exceptions before falling through.
The first successful response wins.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.config import settings
from app.llm.base import BaseLLMClient

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _build_cascade() -> list[BaseLLMClient]:
    """
    Build the ordered list of LLM clients based on available credentials
    and the LLM_PROVIDER preference setting.

    LLM_PROVIDER controls which provider is tried first:
      - 'ollama'  → Ollama first (fast local GPU, best for testing)
      - 'groq'    → Groq first (cloud, default for production)
      - 'gemini'  → Gemini first (optional cloud)

    Gemini is added ONLY when GEMINI_API_KEY is non-empty.
    Ollama is always included.
    """
    preferred = settings.LLM_PROVIDER.lower()
    logger.info("[LLM] Preferred provider from LLM_PROVIDER=%s", preferred)

    def _make_groq() -> BaseLLMClient | None:
        if not settings.groq_available:
            return None
        try:
            from app.llm.groq_client import GroqClient
            client = GroqClient()
            logger.info("[LLM] Groq client initialised (model=%s)", settings.GROQ_MODEL)
            return client
        except Exception as exc:
            logger.warning("[LLM] Groq init failed: %s — skipping.", exc)
            return None

    def _make_gemini() -> BaseLLMClient | None:
        if not settings.gemini_available:
            logger.info("[LLM] Gemini skipped (GEMINI_API_KEY not set — expected).")
            return None
        try:
            from app.llm.gemini_client import GeminiClient
            client = GeminiClient()
            logger.info("[LLM] Gemini client initialised (model=%s)", settings.GEMINI_MODEL)
            return client
        except Exception as exc:
            logger.info("[LLM] Gemini skipped (reason: %s).", exc)
            return None

    def _make_ollama() -> BaseLLMClient | None:
        try:
            from app.llm.ollama_client import OllamaClient
            client = OllamaClient()
            logger.info(
                "[LLM] Ollama client added (model=%s, url=%s)",
                settings.OLLAMA_MODEL,
                settings.OLLAMA_BASE_URL,
            )
            return client
        except Exception as exc:
            logger.warning("[LLM] Ollama client init failed: %s", exc)
            return None

    # Build all available clients
    all_clients: dict[str, BaseLLMClient | None] = {
        "groq": _make_groq(),
        "gemini": _make_gemini(),
        "ollama": _make_ollama(),
    }

    # Order: preferred first, then the rest in default order
    default_order = ["groq", "gemini", "ollama"]
    order = [preferred] + [p for p in default_order if p != preferred]

    clients = [all_clients[p] for p in order if all_clients.get(p) is not None]

    if not clients:
        logger.error("[LLM] No providers initialised! Cascade will return fallback responses.")

    logger.info("[LLM] Active cascade order: %s", [c.provider_name for c in clients])
    return clients



class LLMCascade:
    """
    Provider-agnostic LLM interface that tries each client in order.

    Usage
    -----
    cascade = get_cascade()
    sql = cascade.generate_sql("How many open tickets are there?")
    answer = cascade.synthesize_answer(query, sql, rows)
    """

    def __init__(self) -> None:
        self._clients: list[BaseLLMClient] = _build_cascade()

    @property
    def active_provider(self) -> str:
        """Name of the highest-priority available provider."""
        return self._clients[0].provider_name if self._clients else "none"

    @property
    def all_providers(self) -> list[str]:
        return [c.provider_name for c in self._clients]

    def generate_sql(self, user_query: str) -> tuple[str, str]:
        """
        Attempt SQL generation across the cascade.

        Returns
        -------
        tuple[str, str]
            (generated_sql, provider_name_used)

        Raises
        ------
        RuntimeError
            If all providers fail.
        """
        last_exc: Exception | None = None

        for client in self._clients:
            t0 = time.perf_counter()
            try:
                sql = client.generate_sql(user_query)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.info(
                    "[LLM] SQL generated via %s in %.0fms",
                    client.provider_name,
                    elapsed_ms,
                )
                return sql, client.provider_name
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - t0) * 1000
                logger.warning(
                    "[LLM] %s failed after %.0fms: %s — trying next provider.",
                    client.provider_name,
                    elapsed_ms,
                    exc,
                )
                last_exc = exc
                continue

        raise RuntimeError(
            f"All LLM providers exhausted. Last error: {last_exc}. "
            "Check API keys in .env or start Ollama locally."
        ) from last_exc

    def synthesize_answer(
        self,
        user_query: str,
        sql: str,
        results: list[dict],
        preferred_provider: str | None = None,
    ) -> str:
        """
        Synthesize a narrative answer.  Tries the preferred provider first
        (the one that generated the SQL), then cascades on failure.
        """
        # Re-order so preferred provider goes first
        ordered = sorted(
            self._clients,
            key=lambda c: 0 if c.provider_name == preferred_provider else 1,
        )

        for client in ordered:
            try:
                return client.synthesize_answer(user_query, sql, results)
            except Exception as exc:
                logger.warning(
                    "[LLM] Synthesis via %s failed: %s — trying next.",
                    client.provider_name,
                    exc,
                )

        # Hard fallback if all providers fail synthesis
        if not results:
            return "No tickets matched your criteria in the current dataset."
        if len(results) == 1 and len(results[0]) == 1:
            val = list(results[0].values())[0]
            return f"Result: {val}"
        return f"Query returned {len(results)} record(s)."


# ── Module-level singleton ────────────────────────────────────────────────────

_cascade: LLMCascade | None = None


def get_cascade() -> LLMCascade:
    """Return the shared LLMCascade singleton (initialised once)."""
    global _cascade
    if _cascade is None:
        _cascade = LLMCascade()
    return _cascade


def reset_cascade() -> LLMCascade:
    """Force-rebuild the cascade singleton (picks up .env changes at runtime)."""
    global _cascade
    _cascade = LLMCascade()
    logger.info("[LLM] Cascade reset. New order: %s", _cascade.all_providers)
    return _cascade
