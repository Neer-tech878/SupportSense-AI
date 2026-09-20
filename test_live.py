"""
Live end-to-end test: runs all 5 assessment sample queries through the
complete 5-stage Text-to-SQL pipeline with real LLM calls.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("  DOTMappers Live LLM Pipeline Test")
print("=" * 60)

# Init DB
from app.database import initialise_database
rows = initialise_database()
print(f"\n✅ SQLite loaded: {rows} tickets\n")

# Show cascade providers
from app.llm.factory import get_cascade
cascade = get_cascade()
print(f"✅ LLM Cascade: {' → '.join(cascade.all_providers)}")
print(f"   Active provider: {cascade.active_provider}\n")

# Run all 5 assessment queries
from app.engines.query_engine import run_nl_query

queries = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets this month?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "What is the average customer rating for Technical category tickets?",
    "Are there any anomalies in resolution times this week?",
]

print("=" * 60)
print("  ASSESSMENT QUERY RESULTS")
print("=" * 60)

all_passed = True
for i, q in enumerate(queries, 1):
    print(f"\n[Q{i}] {q}")
    t0 = time.time()
    result = run_nl_query(q)
    elapsed = round((time.time() - t0) * 1000, 0)

    if result.get("error") and not result.get("sql"):
        print(f"  ❌ FAILED: {result['error']}")
        all_passed = False
    else:
        print(f"  SQL      : {result['sql'][:80]}{'...' if len(result.get('sql',''))>80 else ''}")
        print(f"  Rows     : {result['row_count']}")
        print(f"  Answer   : {result['answer'][:120]}")
        print(f"  Provider : {result['provider']}  |  Latency: {result['latency_ms']}ms  |  Cached: {result['cached']}")

print("\n" + "=" * 60)
print("  ANOMALY ENGINE TEST")
print("=" * 60)
from app.engines.anomaly_engine import detect_anomalies
anom = detect_anomalies()
print(f"\n  Total anomalies : {anom['total_count']}")
print(f"  By severity     : {anom['counts_by_severity']}")
print(f"  Summary         : {anom['summary'][:100]}")

print("\n" + "=" * 60)
if all_passed:
    print("  ALL LIVE TESTS PASSED ✅")
else:
    print("  SOME TESTS FAILED ❌")
print("=" * 60)
