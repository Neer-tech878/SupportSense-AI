"""
app/engines/anomaly_engine.py — Dual-Track Anomaly Detection Pipeline.

TRACK 1 — Deterministic SLA Rules (Heuristic / Business Logic)
  Flags tickets that violate operational SLA thresholds regardless of
  statistical distribution.  No maths required — pure business rules.

  Rule A — CRITICAL_SLA_BREACH:
    priority IN ('High', 'Critical')
    AND status IN ('Open', 'Escalated')
    AND age_hours > 24.0
    where age_hours = anchor_timestamp - created_at

  Rule B — RESPONSE_TIME_BREACH:
    priority = 'Critical'
    AND response_time_hrs > 4.0   (SLA: critical tickets must be acked in 4h)

TRACK 2 — Non-Parametric Statistical Outlier Detection
  Resolution_time_hrs displays extreme right-skew (range: 1.2–119.7 hrs).
  Standard Z-scores over this distribution inflate σ and mask real outliers.
  We use two robust non-parametric methods instead:

  Method A — IQR Fence (Interquartile Range):
    Upper fence = Q3 + 1.5 × IQR  (Tukey fence)
    Applied to: resolved tickets only (resolution_time_hrs IS NOT NULL)
    Anomaly type: STATISTICAL_RESOLUTION (severity: HIGH)

  Method B — MAD Robust Z-Score:
    MAD = median(|xi − x̃|)
    Modified Z-score: Mi = 0.6745 × (xi − x̃) / MAD
    Threshold: |Mi| > 3.0
    Applied to: response_time_hrs (all tickets)
    Anomaly type: ROBUST_ZSCORE_OUTLIER (severity: MEDIUM)

  Method C — Service Dissatisfaction Combo:
    status = 'Resolved'
    AND customer_rating = 1          (lowest possible rating)
    AND resolution_time_hrs > Q3     (resolved but still slow)
    Anomaly type: SERVICE_DISSATISFACTION (severity: MEDIUM)

All anomaly records include:
  ticket_id, anomaly_type, severity, description, observed_value,
  threshold_value, created_at, priority, status, agent_id
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

# Dataset anchor timestamp (maximum created_at in the dataset)
_ANCHOR_TS = datetime.strptime(settings.DATASET_ANCHOR_DATE, "%Y-%m-%d %H:%M")

# Severity constants
CRITICAL = "CRITICAL"
HIGH = "HIGH"
MEDIUM = "MEDIUM"


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class AnomalyRecord:
    ticket_id: str
    anomaly_type: str
    severity: str
    description: str
    observed_value: float | str | None
    threshold_value: float | str | None
    created_at: str
    priority: str
    status: str
    agent_id: str
    issue_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Severity ordering for sorting ─────────────────────────────────────────────
_SEVERITY_ORDER = {CRITICAL: 0, HIGH: 1, MEDIUM: 2}


# ── Data Loading ──────────────────────────────────────────────────────────────

def _load_dataframe() -> pd.DataFrame:
    """Load full tickets table into a Pandas DataFrame."""
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM tickets", conn)

    df["created_at"] = pd.to_datetime(df["created_at"], format="mixed", errors="coerce")
    df["resolution_time_hrs"] = pd.to_numeric(df["resolution_time_hrs"], errors="coerce")
    df["response_time_hrs"] = pd.to_numeric(df["response_time_hrs"], errors="coerce")
    df["customer_rating"] = pd.to_numeric(df["customer_rating"], errors="coerce")
    return df


# ── TRACK 1: SLA Heuristic Rules ─────────────────────────────────────────────

def _detect_sla_breaches(df: pd.DataFrame) -> list[AnomalyRecord]:
    anomalies: list[AnomalyRecord] = []

    # Rule A: High/Critical tickets stuck open > 24 hours
    active = df[df["status"].isin(["Open", "Escalated"])].copy()
    active["age_hrs"] = (
        _ANCHOR_TS - active["created_at"]
    ).dt.total_seconds() / 3600.0

    breaches = active[
        active["priority"].isin(["High", "Critical"])
        & (active["age_hrs"] > 24.0)
    ]

    for _, row in breaches.iterrows():
        age = round(float(row["age_hrs"]), 1)
        anomalies.append(
            AnomalyRecord(
                ticket_id=row["ticket_id"],
                anomaly_type="CRITICAL_SLA_BREACH",
                severity=CRITICAL,
                description=(
                    f"{row['priority']} priority ticket has been {row['status']} "
                    f"for {age} hours — exceeds 24-hour SLA threshold."
                ),
                observed_value=age,
                threshold_value=24.0,
                created_at=row["created_at"].strftime("%Y-%m-%d %H:%M"),
                priority=row["priority"],
                status=row["status"],
                agent_id=row["agent_id"],
                issue_summary=row.get("issue_summary", ""),
            )
        )

    # Rule B: Critical tickets with slow first response (> 4 hours)
    slow_response = df[
        (df["priority"] == "Critical")
        & (df["response_time_hrs"] > 4.0)
    ]

    for _, row in slow_response.iterrows():
        resp = round(float(row["response_time_hrs"]), 1)
        anomalies.append(
            AnomalyRecord(
                ticket_id=row["ticket_id"],
                anomaly_type="RESPONSE_TIME_BREACH",
                severity=HIGH,
                description=(
                    f"Critical ticket received first response in {resp} hours "
                    f"— exceeds 4-hour critical response SLA."
                ),
                observed_value=resp,
                threshold_value=4.0,
                created_at=row["created_at"].strftime("%Y-%m-%d %H:%M"),
                priority=row["priority"],
                status=row["status"],
                agent_id=row["agent_id"],
                issue_summary=row.get("issue_summary", ""),
            )
        )

    return anomalies


# ── TRACK 2: Statistical Outlier Detection ────────────────────────────────────

def _detect_statistical_outliers(df: pd.DataFrame) -> list[AnomalyRecord]:
    anomalies: list[AnomalyRecord] = []

    # ── Method A: IQR Fence on resolution_time_hrs ────────────────────────
    resolved = df[
        (df["status"] == "Resolved")
        & df["resolution_time_hrs"].notna()
    ].copy()

    if len(resolved) > 4:  # Need enough data for meaningful quartiles
        q1 = resolved["resolution_time_hrs"].quantile(0.25)
        q3 = resolved["resolution_time_hrs"].quantile(0.75)
        iqr = q3 - q1
        upper_fence = round(q3 + 1.5 * iqr, 2)

        iqr_outliers = resolved[resolved["resolution_time_hrs"] > upper_fence]
        for _, row in iqr_outliers.iterrows():
            val = round(float(row["resolution_time_hrs"]), 1)
            anomalies.append(
                AnomalyRecord(
                    ticket_id=row["ticket_id"],
                    anomaly_type="STATISTICAL_RESOLUTION",
                    severity=HIGH,
                    description=(
                        f"Resolution time of {val} hrs is a statistical outlier "
                        f"(IQR upper fence: {upper_fence} hrs). "
                        f"Q1={round(q1,1)}, Q3={round(q3,1)}, IQR={round(iqr,1)}."
                    ),
                    observed_value=val,
                    threshold_value=upper_fence,
                    created_at=row["created_at"].strftime("%Y-%m-%d %H:%M"),
                    priority=row["priority"],
                    status=row["status"],
                    agent_id=row["agent_id"],
                    issue_summary=row.get("issue_summary", ""),
                )
            )

    # ── Method B: MAD Robust Z-Score on response_time_hrs ─────────────────
    resp_series = df["response_time_hrs"].dropna()
    if len(resp_series) > 4:
        median_resp = resp_series.median()
        mad = (resp_series - median_resp).abs().median()

        if mad > 0:
            modified_z = 0.6745 * (df["response_time_hrs"] - median_resp) / mad
            mad_outliers = df[modified_z.abs() > 3.0]

            for _, row in mad_outliers.iterrows():
                val = round(float(row["response_time_hrs"]), 2)
                z_val = round(
                    float(abs(0.6745 * (val - median_resp) / mad)), 2
                )
                anomalies.append(
                    AnomalyRecord(
                        ticket_id=row["ticket_id"],
                        anomaly_type="ROBUST_ZSCORE_OUTLIER",
                        severity=MEDIUM,
                        description=(
                            f"Response time of {val} hrs has a robust Z-score of "
                            f"{z_val} (threshold: 3.0). "
                            f"Median response time: {round(median_resp,2)} hrs."
                        ),
                        observed_value=val,
                        threshold_value=3.0,
                        created_at=row["created_at"].strftime("%Y-%m-%d %H:%M"),
                        priority=row["priority"],
                        status=row["status"],
                        agent_id=row["agent_id"],
                        issue_summary=row.get("issue_summary", ""),
                    )
                )

    # ── Method C: Service Dissatisfaction ─────────────────────────────────
    if len(resolved) > 0:
        q3_resol = resolved["resolution_time_hrs"].quantile(0.75)
        dissatisfied = resolved[
            (resolved["customer_rating"] == 1)
            & (resolved["resolution_time_hrs"] > q3_resol)
        ]

        for _, row in dissatisfied.iterrows():
            val = round(float(row["resolution_time_hrs"]), 1)
            anomalies.append(
                AnomalyRecord(
                    ticket_id=row["ticket_id"],
                    anomaly_type="SERVICE_DISSATISFACTION",
                    severity=MEDIUM,
                    description=(
                        f"Resolved ticket received a rating of 1/5 with a "
                        f"resolution time of {val} hrs (Q3 = {round(q3_resol,1)} hrs). "
                        f"Combined signal: slow resolution + lowest customer rating."
                    ),
                    observed_value=val,
                    threshold_value=round(q3_resol, 1),
                    created_at=row["created_at"].strftime("%Y-%m-%d %H:%M"),
                    priority=row["priority"],
                    status=row["status"],
                    agent_id=row["agent_id"],
                    issue_summary=row.get("issue_summary", ""),
                )
            )

    return anomalies


# ── Public API ────────────────────────────────────────────────────────────────

def detect_anomalies(severity_filter: str | None = None) -> dict[str, Any]:
    """
    Run the complete dual-track anomaly detection pipeline.

    Parameters
    ----------
    severity_filter : str | None
        Optional filter: 'CRITICAL', 'HIGH', or 'MEDIUM'.
        Returns all severities if None.

    Returns
    -------
    dict with keys:
        anomalies         : list[dict] — all detected anomalies (sorted by severity)
        total_count       : int
        counts_by_severity: dict[str, int]
        counts_by_type    : dict[str, int]
        summary           : str — plain-English executive summary
    """
    try:
        df = _load_dataframe()
    except Exception as exc:
        logger.error("[Anomaly] Failed to load data: %s", exc)
        return {
            "anomalies": [],
            "total_count": 0,
            "counts_by_severity": {},
            "counts_by_type": {},
            "summary": f"Anomaly detection failed: {exc}",
        }

    # Run both tracks
    sla_anomalies = _detect_sla_breaches(df)
    stat_anomalies = _detect_statistical_outliers(df)

    all_anomalies = sla_anomalies + stat_anomalies

    # Deduplicate: if same ticket_id appears in multiple types, keep both
    # (a ticket can have multiple distinct anomaly signals)

    # Apply severity filter
    if severity_filter and severity_filter.upper() in (CRITICAL, HIGH, MEDIUM):
        all_anomalies = [
            a for a in all_anomalies
            if a.severity == severity_filter.upper()
        ]

    # Sort: CRITICAL → HIGH → MEDIUM, then by ticket_id
    all_anomalies.sort(
        key=lambda a: (
            _SEVERITY_ORDER.get(a.severity, 99),
            a.ticket_id,
        )
    )

    # Compute counts
    counts_by_severity: dict[str, int] = {CRITICAL: 0, HIGH: 0, MEDIUM: 0}
    counts_by_type: dict[str, int] = {}
    for a in all_anomalies:
        counts_by_severity[a.severity] = counts_by_severity.get(a.severity, 0) + 1
        counts_by_type[a.anomaly_type] = counts_by_type.get(a.anomaly_type, 0) + 1

    # Build summary
    total = len(all_anomalies)
    summary_parts = []
    if counts_by_severity.get(CRITICAL, 0):
        summary_parts.append(
            f"{counts_by_severity[CRITICAL]} CRITICAL SLA breach(es)"
        )
    if counts_by_severity.get(HIGH, 0):
        summary_parts.append(
            f"{counts_by_severity[HIGH]} HIGH-severity outlier(s)"
        )
    if counts_by_severity.get(MEDIUM, 0):
        summary_parts.append(
            f"{counts_by_severity[MEDIUM]} MEDIUM-severity flag(s)"
        )

    if summary_parts:
        summary = (
            f"Anomaly scan complete: {total} total anomalies detected — "
            + ", ".join(summary_parts) + "."
        )
    else:
        summary = "No anomalies detected in the current dataset."

    return {
        "anomalies": [a.to_dict() for a in all_anomalies],
        "total_count": total,
        "counts_by_severity": counts_by_severity,
        "counts_by_type": counts_by_type,
        "summary": summary,
    }
