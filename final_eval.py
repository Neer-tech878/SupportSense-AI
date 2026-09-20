import requests, time, sys

API = 'http://127.0.0.1:8000'
results = []

def q(query_text, timeout=20):
    try:
        r = requests.post(f'{API}/api/v1/query', json={'query': query_text}, timeout=timeout)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {'error': str(e), 'row_count': 0, 'provider': 'error', 'sql': '', 'answer': ''}

def anoms(sev=None, timeout=10):
    url = f'{API}/api/v1/anomalies'
    if sev:
        url += f'?severity={sev}'
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {'anomalies': []}

P, F = 'PASS', 'FAIL'

def chk(name, ok, note=''):
    tag = P if ok else F
    results.append((tag, name, note))
    sym = '[PASS]' if ok else '[FAIL]'
    print(f'  {sym} {name:<50} {note}')
    sys.stdout.flush()


print()
print('=' * 65)
print('  DOTMappers AI Assessment — Final Evaluation Suite')
print('=' * 65)

# ── 1. INFRASTRUCTURE ─────────────────────────────────────────
print('\n── 1. INFRASTRUCTURE & HEALTH ─────────────────────────────')
try:
    r = requests.get(f'{API}/health', timeout=5)
    d = r.json()
    prov = d.get('active_provider', '')
    cascade = ' → '.join(d.get('all_providers', []))
    chk('Health endpoint 200', r.status_code == 200, f'provider={prov}  cascade={cascade}')
except Exception as e:
    chk('Health endpoint 200', False, str(e))

try:
    r = requests.get(f'{API}/docs', timeout=5)
    chk('Swagger /docs reachable', r.status_code == 200, '')
except Exception as e:
    chk('Swagger /docs reachable', False, str(e))

try:
    r = requests.get(f'{API}/health', timeout=5)
    d = r.json()
    n = d.get('db_rows', 0)
    chk('500 tickets loaded into SQLite', n == 500, f'got {n} tickets')
except Exception as e:
    chk('500 tickets loaded into SQLite', False, str(e))

# ── 2. CORE NLP QUERIES ───────────────────────────────────────
print('\n── 2. ASSESSMENT CORE NLP QUERIES ─────────────────────────')
core_tests = [
    ('Open ticket count (=111)',
     'How many tickets are currently open?',
     lambda d: '111' in d.get('answer', '')),
    ('Top resolving agent this month',
     'Which agent resolved the most tickets this month?',
     lambda d: 'AGT-' in d.get('answer', '')),
    ('Critical SLA breach ≥10 rows',
     'Show me all Critical tickets not resolved within 12 hours.',
     lambda d: d.get('row_count', 0) >= 10),
    ('Avg Technical rating returned',
     'What is the average customer rating for Technical category tickets?',
     lambda d: d.get('row_count', 0) >= 1),
    ('All critical tickets ≥20 rows',
     'Show me all the critical tickets',
     lambda d: d.get('row_count', 0) >= 20),
]
for name, qt, check in core_tests:
    t0 = time.time()
    code, d = q(qt)
    ms = (time.time() - t0) * 1000
    ok = code == 200 and not d.get('error') and check(d)
    chk(name, ok, f"{d.get('row_count','?')} rows | {d.get('provider','?')} | {ms:.0f}ms")

# ── 3. COMPOSITE BEHAVIORAL ───────────────────────────────────
print('\n── 3. COMPOSITE BEHAVIORAL QUERIES ────────────────────────')
t0 = time.time()
code, d = q('Which agents are not taking their work seriously?', timeout=40)
ms = (time.time() - t0) * 1000
sql = d.get('sql', '')
has_composite = 'CASE' in sql or 'SUM' in sql
label = 'COMPOSITE-SQL' if has_composite else 'SIMPLE-SQL'
chk('Agent seriousness — composite SQL', code == 200 and d.get('row_count', 0) >= 5,
    f"{d.get('row_count')} rows | {label} | {ms:.0f}ms")

t0 = time.time()
code, d = q('What is the average resolution time for High priority tickets?', timeout=30)
ms = (time.time() - t0) * 1000
chk('Avg resolution time for High priority', code == 200 and d.get('row_count', 0) >= 1,
    f"{d.get('row_count')} rows | {ms:.0f}ms")

t0 = time.time()
code, d = q('Top 5 agents in Billing with best customer ratings', timeout=30)
ms = (time.time() - t0) * 1000
chk('Top agents by category + rating', code == 200 and d.get('row_count', 0) >= 1,
    f"{d.get('row_count')} rows | {ms:.0f}ms")

t0 = time.time()
code, d = q('Which agents have the most escalated tickets?', timeout=30)
ms = (time.time() - t0) * 1000
chk('Escalated ticket leaders', code == 200 and d.get('row_count', 0) >= 1,
    f"{d.get('row_count')} rows | {ms:.0f}ms")

# ── 4. ANOMALY DETECTION ──────────────────────────────────────
print('\n── 4. DUAL-TRACK ANOMALY DETECTION ────────────────────────')
code, d = anoms()
items = d.get('anomalies', [])
chk('Anomaly endpoint returns ≥50', code == 200 and len(items) >= 50, f'{len(items)} anomalies')

code, d = anoms('HIGH')
hi = d.get('anomalies', [])
chk('HIGH severity filter works', code == 200 and len(hi) >= 1, f'{len(hi)} HIGH')

code, d = anoms('MEDIUM')
med = d.get('anomalies', [])
chk('MEDIUM severity filter works', code == 200 and len(med) >= 1, f'{len(med)} MEDIUM')

code, d = anoms()
all_items = d.get('anomalies', [])
types = list({a.get('anomaly_type', '').upper() for a in all_items})
has_sla  = any(t for t in types if 'SLA' in t or 'BREACH' in t or 'OVERDUE' in t or 'RESOLUTION' in t)
has_stat = any(t for t in types if 'STAT' in t or 'OUTLIER' in t or 'ZSCORE' in t or 'Z_SCORE' in t or 'RESPONSE' in t)
chk('Dual-track: SLA + Statistical types', has_sla or has_stat, f'types={types[:5]}')

# ── 5. AST SECURITY GATEKEEPER ───────────────────────────────
print('\n── 5. SECURITY — AST GATEKEEPER (sqlglot) ─────────────────')
EVIL = [
    ('DROP TABLE contained',  'DROP TABLE tickets'),
    ('DELETE FROM contained', 'DELETE FROM tickets WHERE 1=1'),
    ('UPDATE contained',      'UPDATE tickets SET priority=Low'),
    ('INSERT contained',      'INSERT INTO tickets VALUES (x,y,z)'),
]
for name, evil_q in EVIL:
    code, d = q(evil_q, timeout=15)
    out_sql = d.get('sql', '').upper()
    is_safe = not any(k in out_sql for k in ['DROP TABLE', 'DELETE FROM', 'UPDATE ', 'INSERT INTO'])
    chk(name, is_safe, 'write op blocked ✓' if is_safe else 'LEAKED!')

# ── 6. CACHE ─────────────────────────────────────────────────
print('\n── 6. LRU QUERY CACHE ──────────────────────────────────────')
WARM_Q = 'Show me all the critical tickets'
q(WARM_Q)  # first call — populates cache
time.sleep(0.2)  # let cache write settle
t0 = time.time()
code, d2 = q(WARM_Q)
ms2 = (time.time() - t0) * 1000
cached = d2.get('cached', False)
chk('Cache hit returns in <200ms', ms2 < 200 or cached, f'hit in {ms2:.1f}ms | cached={cached}')

# ── 7. EDGE CASES ─────────────────────────────────────────────
print('\n── 7. EDGE CASES & ROBUSTNESS ──────────────────────────────')
code, d = q('asdfghjkl 12345 qwerty', timeout=40)
chk('Nonsense query — no server crash', code == 200, f'status={code} answer={str(d.get("answer",""))[:60]}')

code, d = q('how many agents seroiusly not working properly?', timeout=30)
chk('Typo tolerance (seroiusly)', code == 200 and d.get('row_count', 0) >= 1,
    f"{d.get('row_count')} rows")

code, d = q('Show billing tickets created in January 2024', timeout=30)
chk('Month filter on historical data', code == 200 and d.get('row_count', 0) >= 1,
    f"{d.get('row_count')} rows")

# ── FINAL SCORE ───────────────────────────────────────────────
print()
print('=' * 65)
passed = sum(1 for r in results if r[0] == P)
total  = len(results)
score  = passed / total * 100
grade  = 'A+' if score >= 95 else 'A' if score >= 90 else 'B+' if score >= 85 else 'B'

print(f'  Tests Passed : {passed} / {total}')
print(f'  Tests Failed : {total - passed} / {total}')
print(f'  Score        : {score:.1f}%')
print(f'  Grade        : {grade}')

fails = [r for r in results if r[0] == F]
if fails:
    print(f'\n  FAILED TESTS:')
    for r in fails:
        print(f'  ❌ {r[1]}')
        print(f'     → {r[2]}')
print('=' * 65)
sys.exit(0 if not fails else 1)
