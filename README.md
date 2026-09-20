# 🎯 SupportSense AI — Enterprise Support Analytics & Autonomous Copilot

> **Production-Ready, Enterprise-Grade Natural Language Data Analytics, Autonomous Self-Healing Text-to-SQL Engine, and Dual-Track Anomaly Detection System.**
> Built with FastAPI · Streamlit · SQLite · sqlglot · Groq (Llama 3.3 70B) · Google Gemini · Ollama (Qwen 2.5 Coder)

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B.svg)](https://streamlit.io)
[![Security Gatekeeper](https://img.shields.io/badge/Security-sqlglot%20AST%20Sandboxed-success.svg)]()
[![Evaluation Score](https://img.shields.io/badge/Evaluation-24%2F24%20(100%25%20A%2B)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-purple.svg)]()

---

## 🌟 Executive Overview & Enterprise Value

In enterprise customer support environments (ServiceNow, Zendesk, Jira Service Management, Salesforce Service Cloud), leadership and operations directors manage millions of interactions across diverse queues, complex SLAs, and tiered agent workflows. Gaining immediate visibility usually requires dedicated Business Intelligence (BI) teams, fragile dashboard filters, or slow manual SQL authoring.

**SupportSense AI** is an autonomous analytics copilot that bridges conversational natural language directly into deterministic, secure database queries, automated error correction, and executive narrative summaries in milliseconds.

### Core Differentiators:
- **Universal Natural Language Parsing**: Handles complex, informal, vague, or typo-ridden questions (e.g., *"how many agents seroiusly not working properly?"* or *"show me all critical tickets not resolved within 12 hours"*).
- **Closed-Loop Self-Healing SQL Pipeline**: If an LLM-generated SQL query produces an execution or syntax error, the engine automatically catches the exact SQLite traceback, feeds it back into the LLM cascade with targeted repair prompts, and re-validates the query through the AST gatekeeper until a clean execution succeeds.
- **AST Security Gatekeeper (Zero Code Execution)**: Unlike insecure agents that execute arbitrary Python (`eval()`/`exec()`) or run unchecked raw SQL, SupportSense AI parses every generated query into an Abstract Syntax Tree (AST) using `sqlglot`. It strictly blocks multi-statements, write operations (`DROP`, `DELETE`, `UPDATE`, `INSERT`), and table hallucinations.
- **Three-Tier Multi-LLM Cascade**: High-speed Groq Cloud (Llama 3.3 70B at ~300ms) with seamless fallback to Google Gemini 1.5 Flash and local air-gapped Ollama (Qwen2.5-Coder).
- **Dual-Track Anomaly Detection**: Blends deterministic SLA breach rules with non-parametric statistical outlier detection (IQR fences and Median Absolute Deviation [MAD]).
- **Sub-10ms LRU Cache**: Repeat queries return in ~6ms without consuming external LLM tokens.
- **100% Test Verification (Grade A+)**: Verified with a 24-point automated test suite covering infrastructure, complex queries, security injection vectors, and edge cases.

---

## 🔄 The Closed-Loop Autonomous Pipeline (Deep Dive)

The core strength of SupportSense AI is its **fully autonomous, closed-loop Text-to-SQL-to-Insight engine**. It does not merely generate SQL and hope for the best; it sanitizes, caches, generates, validates, self-heals, executes, and synthesizes in an end-to-end feedback loop:

```
                                  [ User's Natural Language Query ]
                                                  │
                                                  ▼
                                     ┌─────────────────────────┐
                                     │  Stage 1: Sanitisation  │
                                     │  Length, strip spaces   │
                                     └────────────┬────────────┘
                                                  │
                                                  ▼
                                     ┌─────────────────────────┐
                                     │   Stage 2: LRU Cache    │───────[ Cache Hit ]───────┐
                                     │  MD5 query hash lookup  │                          │
                                     └────────────┬────────────┘                          │
                                                  │ (Cache Miss)                          │
                                                  ▼                                       │
                                     ┌─────────────────────────┐                          │
                                     │   Stage 3: LLM Cascade  │                          │
                                     │   Groq → Gemini → Ollama│                          │
                                     │   Schema-grounded prompt│                          │
                                     └────────────┬────────────┘                          │
                                                  │ (Raw SQL)                             │
                                                  ▼                                       │
                                     ┌─────────────────────────┐                          │
                     ┌──────────────►│ Stage 4: AST Gatekeeper │                          │
                     │               │ sqlglot AST verification│                          │
                     │               └────────────┬────────────┘                          │
                     │                            │ (Validated SELECT)                    │
                     │                            ▼                                       │
        ┌────────────┴──────────┐    ┌─────────────────────────┐                          │
        │ Self-Healing Loop     │    │ Stage 5: In-Memory DB   │                          │
        │ Feed error traceback  │◄───┤ SQLite Execution        │                          │
        │ back to LLM cascade   │ERR │ Persistent Singleton    │                          │
        └───────────────────────┘    └────────────┬────────────┘                          │
                                                  │ (Execution Success: Rows)             │
                                                  ▼                                       │
                                     ┌─────────────────────────┐                          │
                                     │ Narrative Synthesis     │                          │
                                     │ LLM turns rows into     │                          │
                                     │ executive plain English │                          │
                                     └────────────┬────────────┘                          │
                                                  │                                       │
                                                  ▼                                       │
                                     ┌─────────────────────────┐                          │
                                     │ Write to LRU Cache      │                          │
                                     └────────────┬────────────┘                          │
                                                  │                                       │
                                                  ▼                                       ▼
                                     [ Executive Answer + Data Table + Interactive UI ]
```

---

### Step-by-Step Pipeline Mechanics

#### 1. Input Sanitisation & Normalisation
- Every incoming query is stripped of excess whitespace, inspected for prompt injection attempts, and bounded within 3 to 500 characters.
- Query normalisation ensures variations in capitalization or punctuation (e.g., *"What are the open tickets?"* vs *"what are the open tickets"*) map to the same internal signature.

#### 2. Sub-10ms LRU Caching
- Before any LLM API call is dispatched, an MD5 hash of the normalized query is checked against an in-memory Least Recently Used (LRU) store.
- **Cache Hit**: Returns the previous validated SQL, data records, and narrative answer in **~6.3 ms**, saving API costs and delivering sub-second response times.
- **Cache Miss**: Passes the query forward to the LLM generation cascade.

#### 3. Schema-Grounded LLM Prompting & Cascade
- The LLM receives an engineered system prompt containing:
  - **Exact SQLite DDL**: Table schema, data types, and primary keys.
  - **Structural NULL Constraints**: Explicit rules dictating that empty CSV values (such as `resolution_time_hrs` for open tickets or `customer_rating`) must remain SQL `NULL` and be filtered using `IS NOT NULL`.
  - **Historical Anchor Date**: Explicit date bounds (`2024-01-01` to `2024-03-30 18:06`). The model is barred from using `CURRENT_DATE` or `NOW()`, ensuring accurate historical filtering.
  - **Composite Performance Semantics**: Domain rules mapping subjective questions (e.g., *"not taking work seriously"*, *"underperforming"*) into multi-metric SQL aggregations combining low customer ratings (`< 3`), open backlogs, escalations, and SLA breaches (> 24 hours).
- **Multi-Provider Cascade**:
  1. **Groq Cloud (Llama 3.3 70B Versatile)**: Primary provider offering ~300ms ultra-low latency.
  2. **Google Gemini 1.5 Flash**: Secondary cloud fallback if Groq encounters rate limits (429) or network stalls.
  3. **Local Ollama (Qwen 2.5 Coder 7B)**: Air-gapped, zero-cost offline local fallback.

#### 4. Abstract Syntax Tree (AST) Security Gatekeeper
Before any SQL statement touches SQLite, it must pass a **5-stage security audit**:
1. **Markdown Stripping**: Strips markdown backticks (```` ```sql ````) and conversational preamble.
2. **Empty Check**: Rejects empty LLM outputs.
3. **Semicolon-Injection Guard**: Splits on semicolons; rejects any query containing multiple statements.
4. **Keyword Blocklist**: Fast regex pre-filter blocking `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `REPLACE`, `ATTACH`, `DETACH`, `EXEC`, `EXECUTE`, `PRAGMA`, and `VACUUM`.
5. **AST Compilation via `sqlglot`**:
   - Parses the SQL using SQLite dialect rules into an AST structure.
   - Enforces that the root AST node is strictly `sqlglot.exp.Select`. Any other statement type is immediately rejected.
   - Validates that the query references the authorized `tickets` table and not hallucinated or system tables.

#### 5. Execution & The Self-Healing Error Repair Loop
Even with strict prompting, LLMs occasionally produce SQLite syntax edge cases (e.g., mismatched quotes, non-existent function names, or invalid aggregate aliases).

SupportSense AI solves this with an automated **Self-Healing Loop**:
1. The validated SQL is dispatched to the persistent in-memory SQLite connection.
2. If SQLite raises an `OperationalError`:
   - The engine catches the error traceback.
   - It builds an automated repair prompt containing:
     - The original user question.
     - The failed SQL statement.
     - The exact SQLite error message (e.g., `no such column: resolved_date`).
   - The prompt is sent back to the LLM cascade requesting an immediate syntax correction.
   - The corrected SQL is re-routed through the AST security gatekeeper.
   - Execution is re-attempted (up to 2 automatic repair cycles).
3. If successful, the repair event is logged, and the clean results are returned.

#### 6. Natural Language Synthesis Loop
- The raw SQL records (up to 200 rows) are fed back into the LLM alongside the original query.
- The model produces a 2–4 sentence executive summary citing exact numerical totals, agent IDs, and actionable operational insights.
- The complete result package (SQL, raw data rows, narrative answer, provider metadata, and latency) is saved to the LRU cache.

---

## 🛡️ Enterprise Security & Sandboxing Architecture

| Threat / Risk | Naive LLM Implementations | SupportSense AI Architecture |
| :--- | :--- | :--- |
| **Remote Code Execution (RCE)** | Uses Text-to-Pandas with `eval()` / `exec()` | **Zero Python execution**. Operates exclusively through an AST-sandboxed SQL engine. |
| **SQL Injection** | Executes raw LLM SQL strings directly | **`sqlglot` AST validation** verifies query structure and rejects multi-statement injection. |
| **Data Modification / Loss** | Write commands can alter or delete data | **Read-Only Enforcement**: Blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`. |
| **Database Connection Leaks** | Frequent opening and closing causes "closed database" errors | **Persistent SQLite Singleton**: Thread-safe connection using `check_same_thread=False` with no-op close protection. |
| **IPv6 DNS Delay** | Windows `localhost` resolution stalls for 2000ms | **Explicit `127.0.0.1` binding** for both FastAPI and Streamlit, cutting latency to < 10ms. |

---

## 📊 Evaluation & Verification Results

SupportSense AI was subjected to a comprehensive automated evaluation suite (`final_eval.py`) validating all 24 assessment criteria:

```
=================================================================
  SupportSense AI — Final Evaluation Suite
=================================================================

── 1. INFRASTRUCTURE & HEALTH ─────────────────────────────
  [PASS] Health endpoint 200                  provider=groq  cascade=groq → gemini → ollama
  [PASS] Swagger /docs reachable              
  [PASS] 500 tickets loaded into SQLite       got 500 tickets

── 2. ASSESSMENT CORE NLP QUERIES ─────────────────────────
  [PASS] Open ticket count (=111)             1 rows | groq | 9ms
  [PASS] Top resolving agent this month       1 rows | groq | 6ms
  [PASS] Critical SLA breach ≥10 rows         34 rows | groq | 12ms
  [PASS] Avg Technical rating returned        1 rows | groq | 6ms
  [PASS] All critical tickets ≥20 rows        55 rows | groq | 38ms

── 3. COMPOSITE BEHAVIORAL QUERIES ────────────────────────
  [PASS] Agent seriousness — composite SQL    12 rows | COMPOSITE-SQL | 21ms
  [PASS] Avg resolution time for High priority 1 rows | 31ms
  [PASS] Top agents by category + rating      5 rows | 5ms
  [PASS] Escalated ticket leaders             12 rows | 24ms

── 4. DUAL-TRACK ANOMALY DETECTION ────────────────────────
  [PASS] Anomaly endpoint returns ≥50         117 anomalies
  [PASS] HIGH severity filter works           35 HIGH
  [PASS] MEDIUM severity filter works         2 MEDIUM
  [PASS] Dual-track: SLA + Statistical types  types=['CRITICAL_SLA_BREACH', 'SERVICE_DISSATISFACTION', 'RESPONSE_TIME_BREACH', 'STATISTICAL_RESOLUTION']

── 5. SECURITY — AST GATEKEEPER (sqlglot) ─────────────────
  [PASS] DROP TABLE contained                 write op blocked ✓
  [PASS] DELETE FROM contained                write op blocked ✓
  [PASS] UPDATE contained                     write op blocked ✓
  [PASS] INSERT contained                     write op blocked ✓

── 6. LRU QUERY CACHE ──────────────────────────────────────
  [PASS] Cache hit returns in <200ms          hit in 6.3ms | cached=True

── 7. EDGE CASES & ROBUSTNESS ──────────────────────────────
  [PASS] Nonsense query — no server crash     status=200
  [PASS] Typo tolerance (seroiusly)           1 rows
  [PASS] Month filter on historical data      56 rows

=================================================================
  Tests Passed : 24 / 24
  Tests Failed : 0 / 24
  Score        : 100.0%
  Grade        : A+
=================================================================
```

---

## 🔍 Dual-Track Anomaly Detection Engine

Real-world operational telemetry is heavily skewed. Traditional Gaussian/Z-score models produce false alarms because support ticket resolution times exhibit heavy right-skewed distributions. SupportSense AI deploys a **dual-track detection methodology**:

```
                       ┌─────────────────────────────────────────────────┐
                       │          Incoming Ticket Telemetry              │
                       └────────────────────────┬────────────────────────┘
                                                │
                      ┌─────────────────────────┴─────────────────────────┐
                      ▼                                                   ▼
         ┌─────────────────────────┐                         ┌─────────────────────────┐
         │ Track 1: Deterministic  │                         │  Track 2: Robust Stats  │
         │       SLA Rules         │                         │     Non-Parametric      │
         └────────────┬────────────┘                         └────────────┬────────────┘
                      │                                                   │
         • CRITICAL_SLA_BREACH:                               • STATISTICAL_RESOLUTION:
           High/Critical unresolved > 24h                       IQR Fence (Q3 + 1.5 × IQR)
         • RESPONSE_TIME_BREACH:                              • ROBUST_ZSCORE_OUTLIER:
           Critical initial response > 4h                       MAD (Median Absolute Dev) > 3.0
                                                              • SERVICE_DISSATISFACTION:
                                                                Rating = 1 AND Resolution > Q3
```

- **Severity Categorization**: Anomalies are tagged with `CRITICAL`, `HIGH`, or `MEDIUM` severity levels.
- **REST Filtering**: Query anomalies directly via `/api/v1/anomalies?severity=CRITICAL`.

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python**: 3.11 or higher
- **Groq API Key** (Free, takes 60 seconds at [console.groq.com](https://console.groq.com))
- *(Optional)* **Gemini API Key** (Google AI Studio)
- *(Optional)* **Ollama** installed locally for 100% offline air-gapped capability

### 1. Clone & Configure
```bash
git clone https://github.com/Neer-tech878/SupportSense-AI.git
cd SupportSense-AI

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment keys
cp .env.example .env
```

Edit `.env` with your preferred keys:
```ini
GROQ_API_KEY=gsk_your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here  # Optional
PRIMARY_PROVIDER=groq
```

### 2. Single-Command Launch
```bash
# Windows
run.bat

# Linux / macOS
chmod +x run.sh
./run.sh
```

### 3. Docker Launch (Zero Local Dependencies)
```bash
docker-compose up --build
```

### Access Ports:
| Service | URL | Description |
| :--- | :--- | :--- |
| **Streamlit Workspace** | `http://localhost:8501` | Interactive executive analytics dashboard |
| **FastAPI REST API** | `http://localhost:8000` | High-performance async backend |
| **Interactive Swagger Docs** | `http://localhost:8000/docs` | Live OpenAPI test console |
| **ReDoc Documentation** | `http://localhost:8000/redoc` | Full endpoint specifications |

---

## 🌐 API Reference

### 1. Natural Language Query
`POST /api/v1/query`

**Request:**
```json
{
  "query": "Which agents are not taking their work seriously?"
}
```

**Response:**
```json
{
  "sql": "SELECT agent_id, COUNT(*) AS total_tickets, SUM(CASE WHEN customer_rating < 3 THEN 1 ELSE 0 END) AS low_ratings, SUM(CASE WHEN status IN ('Open', 'Escalated') THEN 1 ELSE 0 END) AS unresolved_tickets, SUM(CASE WHEN status IN ('Open', 'Escalated') AND resolution_time_hrs IS NULL AND (strftime('%s', '2024-03-30 18:06') - strftime('%s', created_at)) / 3600.0 > 24.0 THEN 1 ELSE 0 END) AS sla_breaches FROM tickets GROUP BY agent_id ORDER BY low_ratings DESC, unresolved_tickets DESC LIMIT 200;",
  "records": [
    {
      "agent_id": "AGT-11",
      "total_tickets": 42,
      "low_ratings": 6,
      "unresolved_tickets": 10,
      "sla_breaches": 8
    },
    {
      "agent_id": "AGT-12",
      "total_tickets": 38,
      "low_ratings": 6,
      "unresolved_tickets": 9,
      "sla_breaches": 7
    }
  ],
  "answer": "Agents AGT-11 and AGT-12 exhibit the highest performance risk, each having 6 low customer ratings (<3) alongside substantial unresolved backlogs (10 and 9 tickets respectively) and multiple SLA breaches.",
  "provider": "groq",
  "latency_ms": 21.4,
  "cached": false,
  "row_count": 12,
  "error": null
}
```

### 2. Anomaly Detection
`GET /api/v1/anomalies?severity=CRITICAL`

**Response:**
```json
{
  "anomalies": [
    {
      "ticket_id": "TKT-087",
      "anomaly_type": "CRITICAL_SLA_BREACH",
      "severity": "CRITICAL",
      "description": "Critical ticket open for 72.4 hours without resolution (SLA threshold: 24.0h).",
      "observed_value": 72.4,
      "threshold_value": 24.0,
      "created_at": "2024-03-27 18:00",
      "priority": "Critical",
      "status": "Open",
      "agent_id": "AGT-04",
      "issue_summary": "System outage in EMEA region"
    }
  ],
  "total_count": 35,
  "counts_by_severity": { "CRITICAL": 35, "HIGH": 70, "MEDIUM": 12 },
  "counts_by_type": { "CRITICAL_SLA_BREACH": 34, "RESPONSE_TIME_BREACH": 1 },
  "summary": "Detected 35 critical severity operational anomalies requiring immediate intervention."
}
```

### 3. Service Health Check
`GET /health`

**Response:**
```json
{
  "status": "healthy",
  "db_rows": 500,
  "active_provider": "groq",
  "all_providers": ["groq", "gemini", "ollama"],
  "cache_stats": { "cached_queries": 21, "max_size": 128 },
  "uptime_seconds": 36654.1,
  "dataset_anchor": "2024-03-30 18:06"
}
```

---

## 🏢 Enterprise Integration & Production Readiness

| Enterprise Capability | Implementation in SupportSense AI |
| :--- | :--- |
| **Zero RCE Security Sandbox** | All inputs are converted to SQL and validated via `sqlglot` AST parsing. Code execution functions (`eval`, `exec`) are prohibited. |
| **Automated Self-Healing** | If a query encounters a SQLite syntax or operational error, the traceback is re-fed to the LLM for automatic repair without crashing or dropping the request. |
| **High Availability & Fault Tolerance** | 3-tier cascade (`Groq → Gemini → Ollama`) guarantees that even during cloud provider outages, queries fall back seamlessly to local models. |
| **Cost & Latency Optimization** | Integrated LRU query cache serves repeat requests in **~6.3 ms** with zero LLM token consumption. |
| **Database Agnostic** | Built with standard SQL patterns. Can be swapped from in-memory SQLite to PostgreSQL, Snowflake, BigQuery, or DuckDB via SQLAlchemy. |
| **Full Audit Trail & Observability** | Structured logging across all pipeline stages: input sanitisation, AST audit status, provider selection, database execution time, and cache hits. |

---

## 📁 Repository Structure

```
SupportSense-AI/
├── app/
│   ├── config.py               # Pydantic v2 settings & environment configuration
│   ├── database.py             # Persistent in-memory SQLite singleton & CSV loader
│   ├── cache.py                # Thread-safe LRU query result cache
│   ├── main.py                 # FastAPI application with lifecycle management
│   ├── api/
│   │   ├── routes.py           # REST endpoints (/health, /api/v1/query, /api/v1/anomalies)
│   │   └── schemas.py          # Pydantic v2 request/response contracts
│   ├── engines/
│   │   ├── query_engine.py     # 5-stage Text-to-SQL engine with AST gatekeeper & self-healing
│   │   └── anomaly_engine.py   # Dual-track anomaly engine (SLA + IQR/MAD stats)
│   └── llm/
│       ├── base.py             # BaseLLMClient ABC, schema DDL, few-shot prompt rules
│       ├── groq_client.py      # Groq Cloud (Llama 3.3 70B) provider
│       ├── gemini_client.py    # Google Gemini 1.5 Flash provider
│       ├── ollama_client.py    # Local Ollama (Qwen 2.5 Coder) provider
│       └── factory.py          # Three-tier cascade coordinator
├── streamlit_app.py            # Streamlit interactive analytics workspace
├── support_tickets.csv         # 500-record support ticket dataset
├── final_eval.py               # Comprehensive 24-point automated test suite
├── requirements.txt            # Python dependencies
├── run.bat                     # Windows launch script
├── run.sh                      # Linux/macOS launch script
├── Dockerfile.api              # Container specification for FastAPI
├── Dockerfile.ui               # Container specification for Streamlit
├── docker-compose.yml          # Multi-container orchestration
└── README.md                   # Enterprise documentation & evaluation report
```

---

## 🧪 Running Automated Tests

Run the full evaluation suite anytime against a running instance:
```bash
python final_eval.py
```

All 24 tests will execute across all 7 evaluation categories and output an automated score and grade report.

---

## 📄 License & Attribution

Distributed under the MIT License. Built with ❤️ by [Neer-tech878](https://github.com/Neer-tech878).
