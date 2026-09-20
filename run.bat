@echo off
:: ============================================================
:: DOTMappers AI Assessment — Single-Command Windows Launcher
:: Usage: run.bat
:: ============================================================

echo.
echo  ================================================
echo   DOTMappers AI Support Analytics
echo   Starting up...
echo  ================================================
echo.

:: Check Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.11+
    exit /b 1
)

:: Create .env from example if not present
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [SETUP] Created .env from .env.example
        echo [SETUP] Please edit .env and add your API keys, then re-run.
        echo.
    )
)

:: Install dependencies if needed
echo [SETUP] Checking dependencies...
pip install -r requirements.txt -q --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)
echo [SETUP] Dependencies OK.
echo.

:: Start FastAPI in background
echo [API]   Starting FastAPI on http://localhost:8000 ...
start /B "" python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info

:: Wait for FastAPI to be ready
echo [API]   Waiting for API health check...
set RETRY=0
:HEALTH_LOOP
    timeout /t 1 /nobreak >nul
    curl -sf http://localhost:8000/health >nul 2>&1
    if not errorlevel 1 goto API_READY
    set /A RETRY+=1
    if %RETRY% GEQ 15 (
        echo [WARN]  FastAPI health check timed out after 15s.
        echo [WARN]  Streamlit will run in in-memory mode.
        goto START_UI
    )
    goto HEALTH_LOOP

:API_READY
echo [API]   FastAPI is healthy! ^(http://localhost:8000/docs^)

:START_UI
:: Start Streamlit
echo [UI]    Starting Streamlit on http://localhost:8501 ...
echo.
echo  ================================================
echo   ACCESS POINTS:
echo    API:      http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    UI:       http://localhost:8501
echo  ================================================
echo.
echo  Press CTRL+C to stop all services.
echo.

python -m streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0

:: When Streamlit exits, kill background uvicorn
echo.
echo [Shutdown] Stopping FastAPI...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do taskkill /PID %%a /F >nul 2>&1
echo [Shutdown] All services stopped.
