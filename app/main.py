"""
app/main.py — FastAPI application entry point.

Startup sequence:
  1. Load .env
  2. Ingest support_tickets.csv into in-memory SQLite (lifespan event)
  3. Initialise LLM cascade (Groq → Gemini → Ollama)
  4. Mount API router and serve

Single-command launch:
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.database import initialise_database
from app.llm.factory import get_cascade

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle manager.

    On startup:
      • Ingests CSV into in-memory SQLite
      • Warms up the LLM cascade
      • Logs provider status

    On shutdown:
      • Logs graceful shutdown
    """
    logger.info("=" * 60)
    logger.info("  DOTMappers AI Support Analytics — Starting Up")
    logger.info("=" * 60)

    # ── Load dataset ──────────────────────────────────────────────────────
    try:
        row_count = initialise_database()
        logger.info("[DB] Loaded %d ticket records into in-memory SQLite.", row_count)
    except FileNotFoundError as exc:
        logger.critical("[DB] FATAL: %s", exc)
        raise

    # ── Warm up LLM cascade ───────────────────────────────────────────────
    cascade = get_cascade()
    logger.info(
        "[LLM] Cascade ready. Active provider: %s | Full cascade: %s",
        cascade.active_provider,
        " → ".join(cascade.all_providers),
    )

    logger.info("[API] Swagger UI: http://localhost:%d/docs", settings.API_PORT)
    logger.info("[UI]  Streamlit:  http://localhost:%d", settings.UI_PORT)
    logger.info("=" * 60)

    yield  # Application runs here

    logger.info("[Shutdown] DOTMappers AI Analytics — Shutting down gracefully.")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="DOTMappers AI Support Analytics",
    description=(
        "AI-powered customer support ticket analytics system. "
        "Features: Text-to-SQL natural language querying, dual-track anomaly detection, "
        "and real-time operational KPIs. "
        "Built for the DOTMappers AI Engineer 48-hour assessment."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — required for Streamlit → FastAPI calls ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tightened in production; open for assessment demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Routes ──────────────────────────────────────────────────────────────
app.include_router(router)


# ── Direct execution shortcut ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level="info",
    )
