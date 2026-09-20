"""
app/config.py — Centralised settings loaded from .env / environment.

All application-wide constants live here.  No other module should call
os.getenv() directly; import from this module instead.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from dotenv import load_dotenv

# Load .env from project root — override=True ensures .env always wins
load_dotenv(override=True)


# ── LLM Provider Settings ────────────────────────────────────────────────────

class Settings:
    """All configuration values with environment-variable overrides."""

    # Provider preference (first-choice, not the whole cascade order)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq").lower()

    # Groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    GROQ_TIMEOUT: int = 15

    # Gemini — strictly optional; empty string → skip
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_TIMEOUT: int = 20

    # Ollama — local GPU inference
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
    OLLAMA_TIMEOUT: int = 60

    # Application
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    UI_PORT: int = int(os.getenv("UI_PORT", "8501"))

    # Dataset
    CSV_PATH: str = os.getenv("CSV_PATH", "support_tickets.csv")
    DATASET_ANCHOR_DATE: str = os.getenv("DATASET_ANCHOR_DATE", "2024-03-30 18:06")

    # Query limits
    MAX_QUERY_LENGTH: int = 500
    MAX_QUERY_RESULTS: int = 200
    SQL_REPAIR_MAX_RETRIES: int = 2

    # LRU cache size (number of unique queries to keep)
    QUERY_CACHE_SIZE: int = 128

    # ── Derived helpers ──────────────────────────────────────────────────────

    @property
    def groq_available(self) -> bool:
        return bool(self.GROQ_API_KEY)

    @property
    def gemini_available(self) -> bool:
        """Gemini is strictly optional — only added to cascade when key is set."""
        return bool(self.GEMINI_API_KEY)

    @property
    def active_providers(self) -> list[str]:
        """Returns the ordered list of providers that will be attempted."""
        providers = []
        if self.groq_available:
            providers.append("groq")
        if self.gemini_available:
            providers.append("gemini")
        providers.append("ollama")  # always last resort
        return providers


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance (cached after first call)."""
    return Settings()


settings = get_settings()
