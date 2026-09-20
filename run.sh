#!/bin/bash
# ============================================================
# DOTMappers AI Assessment — Single-Command Linux/Mac Launcher
# Usage: chmod +x run.sh && ./run.sh
# ============================================================

set -e

echo ""
echo "  ================================================"
echo "   DOTMappers AI Support Analytics"
echo "   Starting up..."
echo "  ================================================"
echo ""

# Create .env from example if not present
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp ".env.example" ".env"
    echo "[SETUP] Created .env from .env.example"
    echo "[SETUP] Edit .env to add your API keys, then re-run."
    echo ""
fi

# Install dependencies
echo "[SETUP] Checking dependencies..."
pip install -r requirements.txt -q --disable-pip-version-check
echo "[SETUP] Dependencies OK."
echo ""

# Trap SIGINT/SIGTERM to clean up background processes
cleanup() {
    echo ""
    echo "[Shutdown] Stopping all services..."
    [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null
    [ -n "$UI_PID" ] && kill "$UI_PID" 2>/dev/null
    echo "[Shutdown] Done."
    exit 0
}
trap cleanup INT TERM

# Start FastAPI
echo "[API]   Starting FastAPI on http://localhost:8000 ..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info &
API_PID=$!

# Wait for health check
echo "[API]   Waiting for API health check..."
RETRY=0
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    sleep 1
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge 15 ]; then
        echo "[WARN]  API health check timed out — Streamlit will use in-memory mode."
        break
    fi
done

echo "[API]   FastAPI ready at http://localhost:8000/docs"

echo ""
echo "  ================================================"
echo "   ACCESS POINTS:"
echo "    API:      http://localhost:8000"
echo "    API Docs: http://localhost:8000/docs"
echo "    UI:       http://localhost:8501"
echo "  ================================================"
echo ""
echo "  Press CTRL+C to stop all services."
echo ""

# Start Streamlit (foreground)
python -m streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true &
UI_PID=$!

# Wait for both processes
wait $UI_PID $API_PID
