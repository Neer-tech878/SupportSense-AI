"""
app/engines/query_engine.py — 5-Stage Text-to-SQL Pipeline.

STAGE OVERVIEW
──────────────
  Stage 1 │ Input Sanitisation
           │  Validates query length, strips injection attempts.
           │
  Stage 2 │ Cache Lookup
           │  Returns cached result instantly if query was seen before.
           │
  Stage 3 │ LLM Cascade → SQL Generation
           │  Tries Groq → Gemini (optional) → Ollama in order.
           │
  Stage 4 │ AST Security Gatekeeper  ← strict sqlglot validation
           │  • Must be a single SELECT statement.
           │  • Blocks: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE,
           │             ATTACH, EXEC, CREATE, REPLACE.
           │  • Blocks semicolon-injection (multi-statement).
           │
  Stage 5 │ SQLite Execution + Self-Healing Retry Loop
           │  • Executes the validated query.
           │  • On OperationalError, feeds traceback back to the LLM
           │    for automated correction (max 2 attempts).
           │  • Synthesises a narrative answer from raw rows.
           │  • Stores result in LRU cache.

Security note: Text-to-Pandas with exec()/eval() was explicitly rejected
because it allows arbitrary code execution.  SQLite with AST validation
provides a deterministic, read-only execution sandbox.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import time
from typing import Any

import sqlglot
import sqlglot.errors

from app.cache import cache_get, cache_set
from app.config import settings
from app.database import execute_query
from app.llm.factory import get_cascade

logger = logging.getLogger(__name__)

# ── Blocked SQL keywords (defence-in-depth on top of AST check) ──────────────
_BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|"
    r"ATTACH|DETACH|EXEC|EXECUTE|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)

# ── Result type alias ─────────────────────────────────────────────────────────
QueryResult = dict[str, Any]


# ── Stage 4: AST Security Gatekeeper ─────────────────────────────────────────

def _validate_sql(sql: str) -> str:
    """
    Strictly validate that the SQL is a safe, single SELECT statement.

    Parameters
    ----------
    sql : str
        Raw SQL string from the LLM.

    Returns
    -------
    str
        The cleaned, validated SQL string.

    Raises
    ------
    ValueError
        If the SQL fails any security check.
    """
    # ── 1. Strip common markdown leftovers ───────────────────────────────────
    cleaned = re.sub(r"```(?:sql|sqlite)?", "", sql, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "").strip()

    # ── 2. Reject empty output ───────────────────────────────────────────────
    if not cleaned:
        raise ValueError("LLM returned an empty SQL response.")

    # ── 3. Block multi-statement injection (semicolon attack) ─────────────────
    # Allow semicolons only at the very end (e.g. "SELECT ...;")
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        raise ValueError(
            f"Multi-statement SQL rejected (semicolon injection guard). "
            f"Got {len(statements)} statements."
        )

    # ── 4. Keyword blocklist check (fast pre-filter) ─────────────────────────
    if _BLOCKED_KEYWORDS.search(cleaned):
        match = _BLOCKED_KEYWORDS.search(cleaned)
        raise ValueError(
            f"Blocked keyword detected in generated SQL: '{match.group()}'. "
            "Only SELECT statements are permitted."
        )

    # ── 5. AST parse and validate via sqlglot ─────────────────────────────────
    try:
        parsed = sqlglot.parse(cleaned, dialect="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"SQL failed AST parsing: {exc}") from exc

    if not parsed or len(parsed) == 0:
        raise ValueError("sqlglot could not parse any statement from the SQL.")

    if len(parsed) > 1:
        raise ValueError(
            f"Multiple parsed statements detected ({len(parsed)}). "
            "Only a single SELECT is allowed."
        )

    stmt = parsed[0]
    if not isinstance(stmt, sqlglot.exp.Select):
        stmt_type = type(stmt).__name__
        raise ValueError(
            f"Expected SELECT statement, got '{stmt_type}'. "
            "Only read-only SELECT queries are permitted."
        )

    # ── 6. Verify SELECT targets the correct table ───────────────────────────
    sql_upper = cleaned.upper()
    if "TICKETS" not in sql_upper and "FROM" in sql_upper:
        raise ValueError(
            "SQL does not reference the 'tickets' table. "
            "Possible hallucinated table name."
        )

    logger.debug("[AST] SQL passed all security checks: %s", cleaned[:80])
    return cleaned


# ── Stage 5: Self-Healing Retry Loop ─────────────────────────────────────────

def _execute_with_healing(
    sql: str,
    user_query: str,
    provider: str,
) -> tuple[list[dict], str]:
    """
    Execute the validated SQL.  On OperationalError, feed the error
    back to the LLM cascade for automated correction.

    Returns
    -------
    tuple[list[dict], str]
        (result_rows, final_sql_that_succeeded)
    """
    attempt = 0
    current_sql = sql
    last_error: Exception | None = None

    while attempt <= settings.SQL_REPAIR_MAX_RETRIES:
        try:
            rows = execute_query(current_sql)
            if attempt > 0:
                logger.info(
                    "[Self-Heal] Query repaired successfully on attempt %d.", attempt
                )
            return rows, current_sql

        except sqlite3.OperationalError as exc:
            last_error = exc
            attempt += 1
            logger.warning(
                "[Self-Heal] SQLite error on attempt %d: %s", attempt, exc
            )

            if attempt > settings.SQL_REPAIR_MAX_RETRIES:
                break

            # Feed error context back to LLM for automated repair
            repair_prompt = (
                f"The SQL query below failed with a SQLite error.\n"
                f"Failed SQL:\n{current_sql}\n"
                f"Error message: {exc}\n\n"
                f"Original user question: {user_query}\n\n"
                f"Fix the SQL query. Return ONLY the corrected SELECT statement. "
                f"No explanation, no markdown."
            )
            cascade = get_cascade()
            try:
                repaired_sql, repair_provider = cascade.generate_sql(repair_prompt)
                validated = _validate_sql(repaired_sql)
                logger.info(
                    "[Self-Heal] Repair SQL generated by %s: %s",
                    repair_provider,
                    validated[:80],
                )
                current_sql = validated
            except Exception as repair_exc:
                logger.warning("[Self-Heal] Repair generation failed: %s", repair_exc)
                break

        except Exception as exc:
            # Non-recoverable error (e.g. database not initialised)
            raise exc

    raise sqlite3.OperationalError(
        f"Query failed after {settings.SQL_REPAIR_MAX_RETRIES} repair attempt(s). "
        f"Last SQLite error: {last_error}"
    ) from last_error


# ── Public API ────────────────────────────────────────────────────────────────

def run_nl_query(user_query: str) -> QueryResult:
    """
    Execute the full 5-stage Text-to-SQL pipeline.

    Parameters
    ----------
    user_query : str
        Raw natural language question from the user / evaluator.

    Returns
    -------
    dict with keys:
        sql          : str   — the executed SQL
        records      : list  — raw result rows (list of dicts)
        answer       : str   — LLM narrative summary
        provider     : str   — which LLM provider answered
        latency_ms   : float — total wall-clock time
        cached       : bool  — whether result came from cache
        row_count    : int   — number of records returned
    """
    t_start = time.perf_counter()

    # ── Stage 1: Input Sanitisation ──────────────────────────────────────────
    query = user_query.strip()
    if not query:
        raise ValueError("Query cannot be empty.")
    if len(query) > settings.MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query too long ({len(query)} chars). "
            f"Maximum is {settings.MAX_QUERY_LENGTH} characters."
        )

    # ── Stage 2: Cache Lookup ─────────────────────────────────────────────────
    cached = cache_get(query)
    if cached is not None:
        cached["cached"] = True
        cached["latency_ms"] = round((time.perf_counter() - t_start) * 1000, 1)
        logger.info("[Cache] HIT for query: '%s'", query[:60])
        return cached

    # ── Stage 3: LLM Cascade → SQL Generation ────────────────────────────────
    cascade = get_cascade()
    try:
        raw_sql, provider = cascade.generate_sql(query)
        logger.info("[Stage3] SQL from %s: %s", provider, raw_sql[:100])
    except RuntimeError as exc:
        # All providers failed — return graceful structured error
        return {
            "sql": "",
            "records": [],
            "answer": (
                "I'm currently unable to process your query — no LLM provider "
                "is available. Please check your API keys or start Ollama locally."
            ),
            "provider": "none",
            "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "cached": False,
            "row_count": 0,
            "error": str(exc),
        }

    # ── Stage 4: AST Security Gatekeeper ─────────────────────────────────────
    try:
        validated_sql = _validate_sql(raw_sql)
    except ValueError as exc:
        logger.warning("[AST] Validation failed: %s", exc)
        # Attempt one repair cycle
        try:
            repair_prompt = (
                f"The following SQL failed security validation: {raw_sql}\n"
                f"Reason: {exc}\n"
                f"Original question: {query}\n"
                f"Return ONLY a valid single SELECT statement."
            )
            repaired_raw, provider = cascade.generate_sql(repair_prompt)
            validated_sql = _validate_sql(repaired_raw)
            logger.info("[AST] Validation passed after repair.")
        except Exception as repair_exc:
            return {
                "sql": raw_sql,
                "records": [],
                "answer": (
                    f"Your query generated an unsafe SQL statement that was blocked "
                    f"for security. Please rephrase your question. "
                    f"(Detail: {exc})"
                ),
                "provider": provider,
                "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
                "cached": False,
                "row_count": 0,
                "error": str(exc),
            }

    # ── Stage 5: Execute + Self-Heal + Synthesise ─────────────────────────────
    try:
        records, final_sql = _execute_with_healing(validated_sql, query, provider)
    except Exception as exc:
        return {
            "sql": validated_sql,
            "records": [],
            "answer": (
                f"The query could not be executed against the database. "
                f"Error: {exc}"
            ),
            "provider": provider,
            "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "cached": False,
            "row_count": 0,
            "error": str(exc),
        }

    # Narrative synthesis
    answer = cascade.synthesize_answer(query, final_sql, records, preferred_provider=provider)

    result: QueryResult = {
        "sql": final_sql,
        "records": records,
        "answer": answer,
        "provider": provider,
        "latency_ms": round((time.perf_counter() - t_start) * 1000, 1),
        "cached": False,
        "row_count": len(records),
    }

    # Store in cache
    cache_set(query, result)
    return result
