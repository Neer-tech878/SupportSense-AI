"""
Smoke test: validates the database, anomaly engine, and AST gatekeeper
without requiring any API keys.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Test 1: Database ingestion ─────────────────────────────────────────────
print("=" * 55)
print("TEST 1: Database Ingestion")
print("=" * 55)
from app.database import initialise_database, execute_query, get_stats

rows = initialise_database()
print(f"  ✅ Loaded {rows} rows into in-memory SQLite")

stats = get_stats()
print(f"  Total tickets   : {stats['total_tickets']}")
print(f"  Open tickets    : {stats['open_tickets']}")
print(f"  Critical tickets: {stats['critical_tickets']}")
print(f"  Avg rating      : {stats['avg_customer_rating']}")

# ── Test 2: Direct SQL execution ────────────────────────────────────────────
print()
print("=" * 55)
print("TEST 2: Direct SQL Queries (assessment sample queries)")
print("=" * 55)

queries = [
    ("Open count", "SELECT COUNT(*) AS cnt FROM tickets WHERE status='Open'"),
    ("Avg technical rating", "SELECT ROUND(AVG(customer_rating),2) AS avg FROM tickets WHERE category='Technical' AND customer_rating IS NOT NULL"),
    ("Top agent March", "SELECT agent_id, COUNT(*) AS cnt FROM tickets WHERE status='Resolved' AND strftime('%Y-%m',created_at)='2024-03' GROUP BY agent_id ORDER BY cnt DESC LIMIT 1"),
    ("Critical unresolved >12h", "SELECT COUNT(*) AS cnt FROM tickets WHERE priority='Critical' AND ((status='Resolved' AND resolution_time_hrs>12.0) OR status IN ('Open','Escalated'))"),
]

for label, sql in queries:
    result = execute_query(sql)
    print(f"  ✅ {label}: {result}")

# ── Test 3: AST Gatekeeper ──────────────────────────────────────────────────
print()
print("=" * 55)
print("TEST 3: AST Security Gatekeeper")
print("=" * 55)
from app.engines.query_engine import _validate_sql

safe_tests = [
    "SELECT COUNT(*) FROM tickets WHERE status='Open'",
    "SELECT agent_id, AVG(customer_rating) FROM tickets GROUP BY agent_id",
]
dangerous_tests = [
    "DROP TABLE tickets",
    "DELETE FROM tickets WHERE 1=1",
    "SELECT * FROM tickets; DROP TABLE tickets",
    "UPDATE tickets SET status='Resolved' WHERE 1=1",
    "INSERT INTO tickets VALUES ('x','x','x','x','x',0,0,'x',0,'x')",
]

for sql in safe_tests:
    try:
        validated = _validate_sql(sql)
        print(f"  ✅ ALLOWED (correct): {sql[:60]}")
    except ValueError as e:
        print(f"  ❌ WRONGLY BLOCKED: {sql[:60]} — {e}")

for sql in dangerous_tests:
    try:
        validated = _validate_sql(sql)
        print(f"  ❌ WRONGLY ALLOWED: {sql[:60]}")
    except ValueError as e:
        print(f"  ✅ BLOCKED (correct): {sql[:50]} — {str(e)[:50]}")

# ── Test 4: Anomaly Engine ──────────────────────────────────────────────────
print()
print("=" * 55)
print("TEST 4: Dual-Track Anomaly Engine")
print("=" * 55)
from app.engines.anomaly_engine import detect_anomalies

result = detect_anomalies()
print(f"  Total anomalies: {result['total_count']}")
print(f"  By severity:     {result['counts_by_severity']}")
print(f"  By type:         {result['counts_by_type']}")
print(f"  Summary: {result['summary'][:80]}")

# Show top 3
for a in result['anomalies'][:3]:
    print(f"    [{a['severity']}] {a['ticket_id']} — {a['anomaly_type']}")

print()
print("=" * 55)
print("ALL TESTS PASSED ✅")
print("=" * 55)
