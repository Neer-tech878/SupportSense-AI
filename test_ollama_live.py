"""
Quick live test: fire all 5 assessment queries against local Ollama.
Prints timing so we can gauge Ollama speed vs Groq.
"""
import requests, time, sys

API = "http://localhost:8000"

QUERIES = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets this month?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "What is the average customer rating for Technical category tickets?",
    "Show me all the critical tickets",
]

print(f"\n{'='*60}")
print(f"  LIVE OLLAMA TEST — DOTMappers Assessment Queries")
print(f"{'='*60}\n")

# Confirm active provider
health = requests.get(f"{API}/health", timeout=5).json()
print(f"Active provider : {health['active_provider']}")
print(f"Full cascade    : {' → '.join(health['all_providers'])}\n")
print(f"{'─'*60}")

all_pass = True
for i, q in enumerate(QUERIES, 1):
    t0 = time.time()
    try:
        r = requests.post(f"{API}/api/v1/query", json={"query": q}, timeout=120)
        elapsed = (time.time() - t0) * 1000
        data = r.json()
        if r.status_code != 200 or data.get("error"):
            print(f"[Q{i}] ❌ FAIL ({elapsed:.0f}ms) — {data.get('error', r.text[:120])}")
            all_pass = False
        else:
            rows = data.get("row_count", 0)
            provider = data.get("provider", "?")
            answer = data.get("answer", "")[:120]
            sql = data.get("sql", "")[:80].replace("\n", " ")
            print(f"[Q{i}] ✅ {elapsed:.0f}ms | {provider} | {rows} rows")
            print(f"     SQL : {sql}...")
            print(f"     ANS : {answer}")
            print()
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        print(f"[Q{i}] ❌ Exception ({elapsed:.0f}ms) — {e}")
        all_pass = False

print(f"{'─'*60}")
print(f"\n{'ALL QUERIES PASSED ✅' if all_pass else 'SOME QUERIES FAILED ❌'}\n")
sys.exit(0 if all_pass else 1)
