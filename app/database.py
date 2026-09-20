"""
app/database.py — Persistent In-Memory SQLite Engine.

Loads support_tickets.csv into a persistent in-memory SQLite database at
application startup. All downstream modules call get_connection() (or get_db())
to obtain the active singleton connection to the database.

Design decisions:
  • In-memory SQLite: zero external dependencies, sub-millisecond aggregations
    over 500 rows, and a fully sandboxed execution environment.
  • Persistent singleton: connection is initialized once with check_same_thread=False
    and kept open for the entire lifetime of the process.
  • Protected connection: close() calls are no-ops on the singleton to guarantee
    the database is never accidentally closed.
  • Structural NULLs: empty CSV cells for resolution_time_hrs / customer_rating
    are converted to SQL NULL (not 0 or mean), preserving lifecycle invariants.
  • Indexes on priority, status, created_at for fast anomaly filtering.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings


# ── Persistent SQLite Connection Class ───────────────────────────────────────

class _PersistentSQLiteConnection(sqlite3.Connection):
    """
    Subclass that suppresses close() calls.
    Keeps the in-memory SQLite database alive for the entire process lifetime.
    """
    def close(self) -> None:
        # Intentionally a no-op to preserve in-memory database singleton
        pass


# ── Module-level state ────────────────────────────────────────────────────────

_lock = threading.Lock()
_initialised = False
_db_conn: sqlite3.Connection | None = None   # the persistent in-memory singleton connection


# ── DDL ───────────────────────────────────────────────────────────────────────

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_priority ON tickets(priority);",
    "CREATE INDEX IF NOT EXISTS idx_status   ON tickets(status);",
    "CREATE INDEX IF NOT EXISTS idx_created  ON tickets(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_agent    ON tickets(agent_id);",
]


# ── Public API ────────────────────────────────────────────────────────────────

def init_db(csv_path: str | None = None) -> int:
    """
    Load the CSV dataset into the persistent in-memory SQLite singleton database.

    Idempotent: calling this multiple times safely reuses the active connection.
    Never closes the connection.

    Returns
    -------
    int
        Number of rows loaded into the database.
    """
    global _initialised, _db_conn

    with _lock:
        if _initialised and _db_conn is not None:
            return _db_conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

        path = Path(csv_path or settings.CSV_PATH)
        if not path.exists():
            raise FileNotFoundError(
                f"Dataset not found at '{path}'. "
                "Ensure support_tickets.csv is in the project root."
            )

        # ── Load CSV with explicit types and null handling ───────────────────
        df = pd.read_csv(
            path,
            dtype={
                "ticket_id": str,
                "category": str,
                "priority": str,
                "status": str,
                "agent_id": str,
                "issue_summary": str,
            },
        )

        # Normalise column names
        df.columns = df.columns.str.strip().str.lower()

        # Numeric coercion: empty string → NaN → SQL NULL
        df["response_time_hrs"] = pd.to_numeric(
            df["response_time_hrs"], errors="coerce"
        )
        df["resolution_time_hrs"] = pd.to_numeric(
            df["resolution_time_hrs"], errors="coerce"
        )
        df["customer_rating"] = pd.to_numeric(
            df["customer_rating"], errors="coerce"
        )

        # Normalise created_at to consistent format
        df["created_at"] = pd.to_datetime(
            df["created_at"], format="mixed"
        ).dt.strftime("%Y-%m-%d %H:%M")

        # ── Create persistent in-memory singleton connection ──────────────────
        conn = sqlite3.connect(
            ":memory:",
            check_same_thread=False,
            factory=_PersistentSQLiteConnection,
        )
        conn.row_factory = sqlite3.Row

        # Write data
        df.to_sql("tickets", conn, if_exists="replace", index=False, chunksize=500)

        # Create indexes
        for idx_sql in _CREATE_INDEXES_SQL:
            conn.execute(idx_sql)
        conn.commit()

        _db_conn = conn
        _initialised = True

        return conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]


# Backward compatibility alias
initialise_database = init_db


def get_connection() -> sqlite3.Connection:
    """
    Return the persistent in-memory SQLite connection singleton.

    Auto-initialises the database if not yet loaded.
    Thread-safe with check_same_thread=False.
    """
    global _db_conn
    if _db_conn is None:
        init_db()
    return _db_conn


# Backward compatibility alias
get_db = get_connection


def execute_query(sql: str) -> list[dict[str, Any]]:
    """
    Execute a validated SELECT query and return rows as a list of dicts.

    Never closes the connection.

    Raises
    ------
    sqlite3.Error
        Propagated to caller for self-healing error correction.
    """
    conn = get_connection()
    cursor = conn.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchmany(settings.MAX_QUERY_RESULTS)
    return [dict(zip(columns, row)) for row in rows]


def get_stats() -> dict[str, Any]:
    """
    Return quick summary statistics used by /health and UI metrics.
    Accesses the active in-memory instance and never closes the connection.
    """
    conn = get_connection()
    stats: dict[str, Any] = {}

    stats["total_tickets"] = conn.execute(
        "SELECT COUNT(*) FROM tickets"
    ).fetchone()[0]

    stats["open_tickets"] = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Open'"
    ).fetchone()[0]

    stats["critical_tickets"] = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE priority = 'Critical'"
    ).fetchone()[0]

    stats["avg_customer_rating"] = conn.execute(
        "SELECT ROUND(AVG(customer_rating), 2) FROM tickets "
        "WHERE customer_rating IS NOT NULL"
    ).fetchone()[0]

    stats["resolved_tickets"] = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Resolved'"
    ).fetchone()[0]

    stats["escalated_tickets"] = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'Escalated'"
    ).fetchone()[0]

    return stats
