"""
app/api/schemas.py — Pydantic v2 request/response models.

All API contracts are defined here. Pydantic v2 provides:
  • Automatic JSON serialisation
  • Request body validation with clear error messages
  • OpenAPI schema generation (visible at /docs)
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Request Models ────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Request body for POST /api/v1/query"""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about the support ticket dataset.",
        examples=[
            "How many tickets are currently open?",
            "Which agent resolved the most tickets this month?",
            "Show me all Critical tickets not resolved within 12 hours.",
        ],
    )

    @field_validator("query")
    @classmethod
    def sanitise_query(cls, v: str) -> str:
        return v.strip()


# ── Response Models ───────────────────────────────────────────────────────────

class QueryResponse(BaseModel):
    """Response from POST /api/v1/query"""

    sql: str = Field(description="The SQL query generated and executed.")
    records: list[dict[str, Any]] = Field(
        description="Raw result rows from the database."
    )
    answer: str = Field(description="LLM-generated plain-English narrative answer.")
    provider: str = Field(description="LLM provider that handled this request.")
    latency_ms: float = Field(description="Total pipeline execution time in ms.")
    cached: bool = Field(description="True if result was served from LRU cache.")
    row_count: int = Field(description="Number of records returned.")
    error: str | None = Field(default=None, description="Error message if query failed.")


class AnomalyRecord(BaseModel):
    """A single detected anomaly."""

    ticket_id: str
    anomaly_type: str = Field(
        description=(
            "CRITICAL_SLA_BREACH | RESPONSE_TIME_BREACH | "
            "STATISTICAL_RESOLUTION | ROBUST_ZSCORE_OUTLIER | SERVICE_DISSATISFACTION"
        )
    )
    severity: str = Field(description="CRITICAL | HIGH | MEDIUM")
    description: str = Field(description="Human-readable explanation of the anomaly.")
    observed_value: float | str | None
    threshold_value: float | str | None
    created_at: str
    priority: str
    status: str
    agent_id: str
    issue_summary: str = ""


class AnomalyResponse(BaseModel):
    """Response from GET /api/v1/anomalies"""

    anomalies: list[AnomalyRecord]
    total_count: int
    counts_by_severity: dict[str, int]
    counts_by_type: dict[str, int]
    summary: str = Field(description="Executive plain-English summary.")


class HealthResponse(BaseModel):
    """Response from GET /health"""

    status: str = Field(description="'healthy' or 'degraded'")
    db_rows: int = Field(description="Number of ticket rows loaded in SQLite.")
    active_provider: str = Field(description="Primary LLM provider in cascade.")
    all_providers: list[str] = Field(description="Ordered cascade provider list.")
    cache_stats: dict[str, int]
    uptime_seconds: float
    dataset_anchor: str
