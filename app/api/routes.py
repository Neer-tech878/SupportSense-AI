"""
app/api/routes.py — FastAPI route definitions.

Endpoints:
  GET  /health            — Service readiness + LLM provider status
  POST /api/v1/query      — Natural language Text-to-SQL pipeline
  GET  /api/v1/anomalies  — Dual-track anomaly detection results

All endpoints return structured JSON even on error (no raw 500s).
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    AnomalyRecord,
    AnomalyResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from app.cache import cache_clear, cache_stats
from app.config import settings
from app.database import get_stats
from app.engines.anomaly_engine import detect_anomalies
from app.engines.query_engine import run_nl_query
from app.llm.factory import get_cascade, reset_cascade

logger = logging.getLogger(__name__)
router = APIRouter()

# Track startup time for uptime reporting
_START_TIME = time.time()


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description=(
        "Returns service readiness, database row count, "
        "active LLM provider, and cache statistics."
    ),
    tags=["Infrastructure"],
)
def health_check() -> HealthResponse:
    cascade = get_cascade()
    db = get_stats()

    return HealthResponse(
        status="healthy",
        db_rows=db.get("total_tickets", 0),
        active_provider=cascade.active_provider,
        all_providers=cascade.all_providers,
        cache_stats=cache_stats(),
        uptime_seconds=round(time.time() - _START_TIME, 1),
        dataset_anchor=settings.DATASET_ANCHOR_DATE,
    )


# ── POST /api/v1/query ────────────────────────────────────────────────────────

@router.post(
    "/api/v1/query",
    response_model=QueryResponse,
    summary="Natural Language Query",
    description=(
        "Accepts a natural language question about the support ticket dataset. "
        "Translates it to SQL via the LLM cascade, validates with AST gatekeeper, "
        "executes against in-memory SQLite, and returns a narrative answer."
    ),
    tags=["Analytics"],
)
def nl_query(request: QueryRequest) -> QueryResponse:
    logger.info("[API] /query received: '%s'", request.query[:80])
    result = run_nl_query(request.query)
    return QueryResponse(**result)


# ── GET /api/v1/anomalies ─────────────────────────────────────────────────────

@router.get(
    "/api/v1/anomalies",
    response_model=AnomalyResponse,
    summary="Anomaly Detection",
    description=(
        "Runs the dual-track anomaly detection pipeline. "
        "Track 1: Deterministic SLA breach rules. "
        "Track 2: Non-parametric IQR/MAD statistical outliers. "
        "Optionally filter by severity: CRITICAL, HIGH, or MEDIUM."
    ),
    tags=["Analytics"],
)
def anomaly_detection(
    severity: str | None = Query(
        default=None,
        description="Filter by severity: CRITICAL, HIGH, or MEDIUM",
        examples=["CRITICAL", "HIGH", "MEDIUM"],
    )
) -> AnomalyResponse:
    logger.info("[API] /anomalies requested (severity_filter=%s)", severity)

    if severity and severity.upper() not in ("CRITICAL", "HIGH", "MEDIUM"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity '{severity}'. Must be CRITICAL, HIGH, or MEDIUM.",
        )

    result = detect_anomalies(severity_filter=severity)

    anomaly_records = [AnomalyRecord(**a) for a in result["anomalies"]]

    return AnomalyResponse(
        anomalies=anomaly_records,
        total_count=result["total_count"],
        counts_by_severity=result["counts_by_severity"],
        counts_by_type=result["counts_by_type"],
        summary=result["summary"],
    )


# ── POST /api/v1/cache/clear ──────────────────────────────────────────────────

@router.post(
    "/api/v1/cache/clear",
    summary="Clear Query Cache & Reset Cascade",
    description="Wipes the in-memory LRU query cache and forces LLM cascade rebuild.",
    tags=["Infrastructure"],
)
def clear_cache() -> dict[str, Any]:
    cache_clear()
    cascade = reset_cascade()
    return {
        "status": "cleared",
        "cache_stats": cache_stats(),
        "active_provider": cascade.active_provider,
        "all_providers": cascade.all_providers,
    }
