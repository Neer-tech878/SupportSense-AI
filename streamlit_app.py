"""
streamlit_app.py — Streamlit Dashboard with Hybrid Routing.

HYBRID ROUTING STRATEGY
────────────────────────
  LOCAL MODE (FastAPI running on localhost:8000):
    → All requests are HTTP calls to the FastAPI REST API.
    → Provides true service separation and allows testing both interfaces.

  CLOUD MODE (Deployed standalone on Streamlit Community Cloud):
    → FastAPI is unreachable. Instead, modules are imported in-memory.
    → database.py and query_engine.py are called directly.
    → API keys come from st.secrets (Streamlit Cloud secret store).
    → No code changes needed — auto-detected at runtime.

Detection:
  On startup, the app attempts GET http://localhost:8000/health with a
  2-second timeout. Success → LOCAL MODE. Failure → CLOUD MODE.

DASHBOARD STRUCTURE
────────────────────
  Tab 1 — Executive Dashboard   : KPI cards + charts
  Tab 2 — NL Query Console      : Text input + SQL audit + result table
  Tab 3 — Anomaly Triage Grid   : Severity-filtered table + CSV export
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ── Page Config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="DOTMappers AI Support Analytics",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000"
HEALTH_TIMEOUT = 2  # seconds
QUERY_TIMEOUT = 30  # seconds

SAMPLE_QUERIES = [
    "How many tickets are currently open?",
    "Which agent resolved the most tickets this month?",
    "Show me all Critical tickets not resolved within 12 hours.",
    "What is the average customer rating for Technical category tickets?",
    "Which agent has the lowest average customer rating?",
    "How many tickets are in each priority category?",
    "Show me all escalated tickets with their agent and summary.",
]

SEVERITY_COLORS = {
    "CRITICAL": "#FF4B4B",
    "HIGH": "#FF8C00",
    "MEDIUM": "#FFD700",
}

ANOMALY_TYPE_LABELS = {
    "CRITICAL_SLA_BREACH": "🚨 SLA Breach",
    "RESPONSE_TIME_BREACH": "⚡ Response Breach",
    "STATISTICAL_RESOLUTION": "📊 Statistical Outlier",
    "ROBUST_ZSCORE_OUTLIER": "📈 MAD Outlier",
    "SERVICE_DISSATISFACTION": "😞 Service Failure",
}


# ── Hybrid Routing Detection ──────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def _detect_api_mode() -> bool:
    """
    Returns True if FastAPI backend is reachable (LOCAL mode).
    Returns False if running standalone (CLOUD mode).
    Result is cached for 30 seconds.
    """
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=HEALTH_TIMEOUT)
        return resp.status_code == 200
    except Exception:
        return False


def is_local_mode() -> bool:
    return _detect_api_mode()


# ── Cloud Mode: In-Memory Imports & Secret Injection ─────────────────────────

def _inject_cloud_secrets() -> None:
    """
    When running on Streamlit Community Cloud, inject API keys from
    st.secrets into the environment and app.config.settings.
    """
    secret_keys = ["GROQ_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL", "OLLAMA_MODEL", "LLM_PROVIDER", "PRIMARY_PROVIDER"]
    injected = {}
    for key in secret_keys:
        try:
            val = st.secrets.get(key, "")
            if not val and hasattr(st.secrets, key):
                val = getattr(st.secrets, key, "")
            if val:
                os.environ[key] = str(val).strip()
                injected[key] = str(val).strip()
        except Exception:
            pass

    # Update app.config.settings if it's already imported
    if injected:
        try:
            from app.config import settings
            if "GROQ_API_KEY" in injected:
                settings.GROQ_API_KEY = injected["GROQ_API_KEY"]
            if "GEMINI_API_KEY" in injected:
                settings.GEMINI_API_KEY = injected["GEMINI_API_KEY"]
            if "OLLAMA_BASE_URL" in injected:
                settings.OLLAMA_BASE_URL = injected["OLLAMA_BASE_URL"]
            if "OLLAMA_MODEL" in injected:
                settings.OLLAMA_MODEL = injected["OLLAMA_MODEL"]
            if "LLM_PROVIDER" in injected or "PRIMARY_PROVIDER" in injected:
                settings.LLM_PROVIDER = injected.get("PRIMARY_PROVIDER") or injected.get("LLM_PROVIDER")
        except Exception:
            pass

# Run immediately on app load
_inject_cloud_secrets()


def _ensure_db_initialised() -> None:
    """Initialise the in-memory SQLite DB once per session (cloud mode)."""
    _inject_cloud_secrets()
    if st.session_state.get("_db_ready"):
        return
    # Add project root to path so imports work
    project_root = str(Path(__file__).parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from app.database import initialise_database
    initialise_database()
    st.session_state["_db_ready"] = True


# ── API Call Helpers (LOCAL mode) ─────────────────────────────────────────────

def api_health() -> dict[str, Any]:
    resp = requests.get(f"{API_BASE}/health", timeout=5)
    resp.raise_for_status()
    return resp.json()


def api_query(query: str) -> dict[str, Any]:
    resp = requests.post(
        f"{API_BASE}/api/v1/query",
        json={"query": query},
        timeout=QUERY_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def api_anomalies(severity: str | None = None) -> dict[str, Any]:
    params = {"severity": severity} if severity and severity != "ALL" else {}
    resp = requests.get(f"{API_BASE}/api/v1/anomalies", params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Direct Engine Calls (CLOUD mode) ─────────────────────────────────────────

def direct_query(query: str) -> dict[str, Any]:
    _ensure_db_initialised()
    from app.engines.query_engine import run_nl_query
    return run_nl_query(query)


def direct_anomalies(severity: str | None = None) -> dict[str, Any]:
    _ensure_db_initialised()
    from app.engines.anomaly_engine import detect_anomalies
    return detect_anomalies(severity_filter=severity if severity != "ALL" else None)


def direct_health() -> dict[str, Any]:
    _ensure_db_initialised()
    from app.database import get_stats
    from app.llm.factory import get_cascade
    from app.cache import cache_stats
    from app.config import settings
    stats = get_stats()
    cascade = get_cascade()
    return {
        "status": "healthy",
        "db_rows": stats.get("total_tickets", 0),
        "active_provider": cascade.active_provider,
        "all_providers": cascade.all_providers,
        "cache_stats": cache_stats(),
        "uptime_seconds": 0,
        "dataset_anchor": settings.DATASET_ANCHOR_DATE,
    }


# ── Unified Dispatcher ────────────────────────────────────────────────────────

def get_health() -> dict[str, Any]:
    return api_health() if is_local_mode() else direct_health()


def run_query(query: str) -> dict[str, Any]:
    return api_query(query) if is_local_mode() else direct_query(query)


def get_anomalies(severity: str | None = None) -> dict[str, Any]:
    return api_anomalies(severity) if is_local_mode() else direct_anomalies(severity)


# ── CSS Styling ───────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
    <style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #0e1117; }

    /* ── KPI Cards ── */
    .kpi-card {
        background: linear-gradient(135deg, #1a1f2e 0%, #232840 100%);
        border: 1px solid #2d3561;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.2);
    }
    .kpi-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #818cf8;
        line-height: 1.1;
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #94a3b8;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .kpi-card.critical .kpi-value { color: #f87171; }
    .kpi-card.warning .kpi-value  { color: #fb923c; }
    .kpi-card.success .kpi-value  { color: #34d399; }
    .kpi-card.info .kpi-value     { color: #60a5fa; }

    /* ── Section Headers ── */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #e2e8f0;
        padding: 8px 0 4px 0;
        border-bottom: 2px solid #2d3561;
        margin-bottom: 16px;
    }

    /* ── SQL Audit Box ── */
    .sql-box {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px 16px;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #79c0ff;
        white-space: pre-wrap;
        word-break: break-all;
    }

    /* ── Provider Badge ── */
    .provider-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .provider-groq    { background: #1a2744; color: #60a5fa; border: 1px solid #3b82f6; }
    .provider-gemini  { background: #1a2f1a; color: #34d399; border: 1px solid #10b981; }
    .provider-ollama  { background: #2f1a1a; color: #f87171; border: 1px solid #ef4444; }
    .provider-none    { background: #2a2a2a; color: #94a3b8; border: 1px solid #6b7280; }

    /* ── Anomaly Severity ── */
    .severity-CRITICAL { color: #f87171; font-weight: 700; }
    .severity-HIGH     { color: #fb923c; font-weight: 600; }
    .severity-MEDIUM   { color: #fbbf24; font-weight: 500; }

    /* ── Mode Indicator ── */
    .mode-local { color: #34d399; }
    .mode-cloud { color: #f59e0b; }

    /* ── Answer Box & Narrative Card ── */
    .answer-box {
        background: linear-gradient(135deg, #1e2337 0%, #252d45 100%);
        border-left: 4px solid #818cf8;
        border-radius: 0 8px 8px 0;
        padding: 16px 20px;
        color: #e2e8f0;
        font-size: 1rem;
        line-height: 1.6;
        margin: 8px 0 16px 0;
    }

    /* ── Query Status Bar & Pills ── */
    .query-status-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 14px;
        flex-wrap: wrap;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        background: #1e293b;
        color: #94a3b8;
        border: 1px solid #334155;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .status-pill.pill-cached {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border-color: rgba(16, 185, 129, 0.4);
    }

    /* ── Narrative Summary Card ── */
    .narrative-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
        border: 1px solid rgba(99, 102, 241, 0.35);
        border-left: 5px solid #6366f1;
        border-radius: 12px;
        padding: 18px 22px;
        margin: 12px 0 20px 0;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
    }
    .narrative-header {
        display: flex;
        align-items: center;
        margin-bottom: 10px;
    }
    .narrative-badge {
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #818cf8;
        text-transform: uppercase;
        background: rgba(99, 102, 241, 0.15);
        padding: 3px 8px;
        border-radius: 6px;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    .narrative-body {
        font-size: 1.02rem;
        color: #f1f5f9;
        line-height: 1.65;
    }

    /* ── Quick Query Buttons ── */
    div[data-testid="stHorizontalBlock"] .stButton > button {
        border-radius: 8px;
        font-size: 0.82rem;
        font-weight: 500;
        text-align: left;
        padding: 8px 12px;
        transition: all 0.2s ease;
        border: 1px solid #334155;
        background-color: #1e293b;
        color: #e2e8f0;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        border-color: #6366f1;
        background-color: #2e3856;
        color: #ffffff;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
    }
    </style>
    """, unsafe_allow_html=True)


# ── KPI Card Helper ───────────────────────────────────────────────────────────

def kpi_card(value: str | int | float, label: str, variant: str = "") -> str:
    css_class = f"kpi-card {variant}" if variant else "kpi-card"
    return f"""
    <div class="{css_class}">
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>
    """


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(local_mode: bool, health: dict | None) -> None:
    with st.sidebar:
        st.markdown("## 🎯 DOTMappers AI Analytics")
        st.markdown("---")

        # Mode indicator
        if local_mode:
            st.markdown('<span class="mode-local">🟢 Local API Mode</span>', unsafe_allow_html=True)
            st.caption("Connected to FastAPI on :8000")
        else:
            st.markdown('<span class="mode-cloud">🟡 Cloud In-Memory Mode</span>', unsafe_allow_html=True)
            st.caption("Running engines directly (no FastAPI)")

        st.markdown("---")

        if health:
            provider = health.get("active_provider", "unknown")
            all_prov = health.get("all_providers", [])
            st.markdown(f"**LLM Cascade:**")
            for i, p in enumerate(all_prov):
                icon = "🥇" if i == 0 else ("🥈" if i == 1 else "🥉")
                st.markdown(f"{icon} `{p}`")

            st.markdown(f"**Database:** `{health.get('db_rows', 0)} tickets`")
            cache = health.get("cache_stats", {})
            st.markdown(f"**Cache:** `{cache.get('cached_queries', 0)} queries`")

        st.markdown("---")
        st.markdown("**Quick Links:**")
        if local_mode:
            st.markdown("• [Swagger UI](http://localhost:8000/docs)")
            st.markdown("• [ReDoc](http://localhost:8000/redoc)")
        st.markdown("---")
        st.caption("DOTMappers AI Engineer Assessment\nBuilt with FastAPI + Streamlit + SQLite")


# ── Tab 1: Executive Dashboard ────────────────────────────────────────────────

def render_dashboard_tab() -> None:
    st.markdown('<div class="section-header">📊 Operational KPI Overview</div>', unsafe_allow_html=True)

    # Load data for charts
    @st.cache_data(ttl=60, show_spinner=False)
    def _load_chart_data():
        _ensure_db_initialised()
        from app.database import get_connection
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM tickets", conn)
        return df

    try:
        df = _load_chart_data()
    except Exception as e:
        st.error(f"Could not load data for dashboard: {e}")
        return

    total = len(df)
    open_t = len(df[df["status"] == "Open"])
    critical = len(df[df["priority"] == "Critical"])
    avg_rating = round(df["customer_rating"].dropna().mean(), 2)
    resolved = len(df[df["status"] == "Resolved"])
    escalated = len(df[df["status"] == "Escalated"])

    # KPI Row 1
    cols = st.columns(3)
    cols[0].markdown(kpi_card(total, "Total Tickets", "info"), unsafe_allow_html=True)
    cols[1].markdown(kpi_card(open_t, "Open Tickets", "warning"), unsafe_allow_html=True)
    cols[2].markdown(kpi_card(critical, "Critical Priority", "critical"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # KPI Row 2
    cols2 = st.columns(3)
    cols2[0].markdown(kpi_card(resolved, "Resolved", "success"), unsafe_allow_html=True)
    cols2[1].markdown(kpi_card(escalated, "Escalated", "warning"), unsafe_allow_html=True)
    cols2[2].markdown(kpi_card(f"⭐ {avg_rating}", "Avg Rating", "info"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts row
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="section-header">Tickets by Category & Priority</div>', unsafe_allow_html=True)
        cat_pri = df.groupby(["category", "priority"]).size().reset_index(name="count")
        fig1 = px.bar(
            cat_pri,
            x="category",
            y="count",
            color="priority",
            color_discrete_map={
                "Critical": "#f87171",
                "High": "#fb923c",
                "Medium": "#fbbf24",
                "Low": "#34d399",
            },
            template="plotly_dark",
            barmode="stack",
            title="",
        )
        fig1.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#1a1f2e",
            font_color="#e2e8f0",
            margin=dict(t=10, b=10, l=10, r=10),
            legend_title_text="Priority",
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-header">Status Distribution</div>', unsafe_allow_html=True)
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        fig2 = px.pie(
            status_counts,
            names="status",
            values="count",
            color="status",
            color_discrete_map={
                "Resolved": "#34d399",
                "Open": "#fb923c",
                "Escalated": "#f87171",
            },
            template="plotly_dark",
            hole=0.45,
        )
        fig2.update_layout(
            paper_bgcolor="#0e1117",
            font_color="#e2e8f0",
            margin=dict(t=10, b=10, l=10, r=10),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Volume over time
    st.markdown('<div class="section-header">Ticket Volume Over Time</div>', unsafe_allow_html=True)
    df["created_month"] = pd.to_datetime(df["created_at"]).dt.to_period("W").astype(str)
    vol = df.groupby("created_month").size().reset_index(name="tickets")
    fig3 = px.line(
        vol,
        x="created_month",
        y="tickets",
        markers=True,
        template="plotly_dark",
        color_discrete_sequence=["#818cf8"],
    )
    fig3.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#1a1f2e",
        font_color="#e2e8f0",
        margin=dict(t=10, b=10, l=10, r=10),
        xaxis_title="Week",
        yaxis_title="Tickets",
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Agent performance table
    st.markdown('<div class="section-header">Agent Performance Summary</div>', unsafe_allow_html=True)
    agent_df = df.groupby("agent_id").agg(
        total=("ticket_id", "count"),
        resolved=("status", lambda x: (x == "Resolved").sum()),
        avg_rating=("customer_rating", lambda x: round(x.dropna().mean(), 2) if x.dropna().any() else None),
        avg_resolution=("resolution_time_hrs", lambda x: round(x.dropna().mean(), 1) if x.dropna().any() else None),
    ).reset_index()
    agent_df.columns = ["Agent", "Total", "Resolved", "Avg Rating", "Avg Resol. (hrs)"]
    agent_df = agent_df.sort_values("Total", ascending=False)
    st.dataframe(agent_df, use_container_width=True, hide_index=True)


# ── Tab 2: NL Query Console ───────────────────────────────────────────────────

def render_query_tab() -> None:
    st.markdown('<div class="section-header">💬 Natural Language Query Console</div>', unsafe_allow_html=True)
    st.caption("Ask any question about the support ticket dataset in plain English.")

    # 1. State initialization
    if "user_query" not in st.session_state:
        st.session_state["user_query"] = ""
    if "last_query_result" not in st.session_state:
        st.session_state["last_query_result"] = None
    if "trigger_search" not in st.session_state:
        st.session_state["trigger_search"] = False

    # Callback when a quick query chip is clicked: automatically pastes into box and triggers run
    def _on_chip_click(selected_query: str) -> None:
        st.session_state["user_query"] = selected_query
        st.session_state["trigger_search"] = True

    # Callback when clear button is clicked
    def _on_clear_click() -> None:
        st.session_state["user_query"] = ""
        st.session_state["last_query_result"] = None
        st.session_state["query_result"] = None
        st.session_state["current_query"] = ""
        st.session_state["trigger_search"] = False

    # 2. Quick Query Chips (auto-pastes into box and runs immediately on click)
    st.markdown("**💡 Quick Query Starters:**")
    btn_cols = st.columns(4)
    for i, sample in enumerate(SAMPLE_QUERIES):
        col = btn_cols[i % 4]
        col.button(
            f"🔍 {sample}",
            key=f"sample_{i}",
            on_click=_on_chip_click,
            args=(sample,),
            use_container_width=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Search Bar and Action Buttons
    col_input, col_run, col_clear = st.columns([5, 1.2, 0.8])
    with col_input:
        # Bound directly to key="user_query" — immediately reflects the pasted query
        st.text_input(
            label="Your question:",
            key="user_query",
            placeholder="e.g. Show me all the critical tickets?",
            label_visibility="collapsed",
        )
    with col_run:
        run_clicked = st.button("🚀 Run Query", type="primary", use_container_width=True)
    with col_clear:
        st.button("🗑 Clear", on_click=_on_clear_click, use_container_width=True)

    # 4. Trigger execution if Run Query clicked or Quick Query chip clicked
    should_run = (run_clicked or st.session_state.get("trigger_search", False)) and bool(
        st.session_state.get("user_query", "").strip()
    )

    if should_run:
        # Reset trigger flag immediately
        st.session_state["trigger_search"] = False
        query_to_run = st.session_state["user_query"].strip()

        with st.spinner(f"⚙️ Running query: '{query_to_run}'…"):
            try:
                res = run_query(query_to_run)
                st.session_state["last_query_result"] = res
                st.session_state["query_result"] = res
                st.session_state["current_query"] = query_to_run
            except Exception as exc:
                st.error(f"❌ Query execution failed: {exc}")

    # 4. Render directly below buttons whenever last_query_result exists in state
    result = st.session_state.get("last_query_result")
    if result:
        st.markdown("---")

        provider = result.get("provider", "unknown")
        latency = result.get("latency_ms", 0)
        cached = result.get("cached", False)
        records = result.get("records", [])
        row_count = result.get("row_count", len(records))

        # Status & Metric Pill Row
        badge_class = f"provider-{provider}"
        cache_badge = '<span class="status-pill pill-cached">⚡ Cached</span>' if cached else ""
        st.markdown(
            f"""
            <div class="query-status-bar">
                <span class="provider-badge {badge_class}">⚡ {provider.upper()}</span>
                <span class="status-pill">⏱️ {latency}ms</span>
                <span class="status-pill">📋 {row_count} row{'s' if row_count != 1 else ''}</span>
                {cache_badge}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Narrative Summary Card
        answer = result.get("answer", "")
        if answer:
            st.markdown(
                f"""
                <div class="narrative-card">
                    <div class="narrative-header">
                        <span class="narrative-badge">✨ AI Executive Synthesis</span>
                    </div>
                    <div class="narrative-body">
                        {answer}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # SQL Audit Tray (Expandable)
        sql = result.get("sql", "")
        with st.expander("🔍 SQL Audit Tray & AST Gatekeeper", expanded=False):
            if sql:
                st.code(sql, language="sql")
                st.caption(
                    "🛡️ **Security Guard**: Passed 5-stage AST gatekeeper (sqlglot) — Read-only verification, sandboxed SQLite execution."
                )
            else:
                st.warning("No SQL was generated for this query.")

        # Data Table
        if records:
            st.markdown(f'<div class="section-header">📋 Query Records ({row_count} row{"s" if row_count != 1 else ""})</div>', unsafe_allow_html=True)
            df_result = pd.DataFrame(records)
            st.dataframe(df_result, use_container_width=True, hide_index=True)

            # CSV export
            csv = df_result.to_csv(index=False)
            st.download_button(
                label="📥 Export Results as CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
                key="export_csv_btn",
            )
        elif result.get("error"):
            st.error(f"❌ Error during query processing: {result['error']}")
        else:
            st.info("ℹ️ No records matched your query criteria.")


# ── Tab 3: Anomaly Triage Grid ────────────────────────────────────────────────

def render_anomaly_tab() -> None:
    st.markdown('<div class="section-header">🔍 Anomaly Triage Grid</div>', unsafe_allow_html=True)
    st.caption("Dual-track detection: SLA business rules + IQR/MAD non-parametric statistics.")

    col_sev, col_run = st.columns([2, 1])
    severity_filter = col_sev.selectbox(
        "Filter by Severity:",
        options=["ALL", "CRITICAL", "HIGH", "MEDIUM"],
        index=0,
    )
    run_scan = col_run.button("🔍 Run Anomaly Scan", type="primary", use_container_width=True)

    if "anomaly_result" not in st.session_state:
        st.session_state["anomaly_result"] = None

    if run_scan or st.session_state.get("anomaly_result") is None:
        with st.spinner("⚙️ Running dual-track anomaly detection…"):
            try:
                sev = None if severity_filter == "ALL" else severity_filter
                result = get_anomalies(sev)
                st.session_state["anomaly_result"] = result
            except Exception as exc:
                st.error(f"Anomaly scan failed: {exc}")
                return

    result = st.session_state.get("anomaly_result")
    if not result:
        return

    # Summary
    summary = result.get("summary", "")
    if summary:
        st.markdown(f'<div class="answer-box">{summary}</div>', unsafe_allow_html=True)

    # Severity count cards
    counts = result.get("counts_by_severity", {})
    kpi_cols = st.columns(3)
    kpi_cols[0].markdown(
        kpi_card(counts.get("CRITICAL", 0), "Critical Breaches", "critical"),
        unsafe_allow_html=True,
    )
    kpi_cols[1].markdown(
        kpi_card(counts.get("HIGH", 0), "High Severity", "warning"),
        unsafe_allow_html=True,
    )
    kpi_cols[2].markdown(
        kpi_card(counts.get("MEDIUM", 0), "Medium Flags", ""),
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Type breakdown chart
    counts_by_type = result.get("counts_by_type", {})
    if counts_by_type:
        st.markdown('<div class="section-header">Anomalies by Type</div>', unsafe_allow_html=True)
        type_df = pd.DataFrame(
            [(ANOMALY_TYPE_LABELS.get(k, k), v) for k, v in counts_by_type.items()],
            columns=["Type", "Count"],
        )
        fig = px.bar(
            type_df,
            x="Count",
            y="Type",
            orientation="h",
            template="plotly_dark",
            color="Count",
            color_continuous_scale=["#fbbf24", "#f87171"],
        )
        fig.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#1a1f2e",
            font_color="#e2e8f0",
            margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Anomaly records table
    anomalies = result.get("anomalies", [])
    total = result.get("total_count", 0)

    if anomalies:
        st.markdown(f'<div class="section-header">Anomaly Records ({total} total)</div>', unsafe_allow_html=True)

        df_anom = pd.DataFrame(anomalies)
        # Add readable type labels
        df_anom["anomaly_type"] = df_anom["anomaly_type"].map(
            lambda t: ANOMALY_TYPE_LABELS.get(t, t)
        )

        # Reorder columns for readability
        display_cols = [
            "ticket_id", "severity", "anomaly_type",
            "observed_value", "threshold_value",
            "priority", "status", "agent_id",
            "created_at", "description", "issue_summary",
        ]
        display_cols = [c for c in display_cols if c in df_anom.columns]

        st.dataframe(
            df_anom[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "severity": st.column_config.TextColumn("Severity", width="small"),
                "ticket_id": st.column_config.TextColumn("Ticket ID", width="small"),
                "description": st.column_config.TextColumn("Description", width="large"),
            },
        )

        # CSV export
        csv = df_anom.to_csv(index=False)
        st.download_button(
            label="📥 Export Anomalies as CSV",
            data=csv,
            file_name="anomaly_report.csv",
            mime="text/csv",
        )
    else:
        st.success("✅ No anomalies found matching the selected filter.")


# ── Main App ──────────────────────────────────────────────────────────────────

def main() -> None:
    inject_css()

    # Determine mode + load health
    local_mode = is_local_mode()
    try:
        health = get_health()
    except Exception:
        health = None

    # Sidebar
    render_sidebar(local_mode, health)

    # Header
    st.markdown(
        """
        <div style="text-align:center; padding: 24px 0 8px 0;">
            <h1 style="font-size:2.2rem; font-weight:700; color:#e2e8f0; margin:0;">
                🎯 DOTMappers AI Support Analytics
            </h1>
            <p style="color:#94a3b8; font-size:1rem; margin-top:6px;">
                AI-powered ticket analysis · Natural language queries · Anomaly detection
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "📊 Executive Dashboard",
        "💬 NL Query Console",
        "🚨 Anomaly Triage",
    ])

    with tab1:
        render_dashboard_tab()

    with tab2:
        render_query_tab()

    with tab3:
        render_anomaly_tab()


if __name__ == "__main__":
    main()
