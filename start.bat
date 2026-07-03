@echo off
echo.
echo   Hospital Kiosk - Windows Startup
echo   ----------------------------------

REM ── Load .env file if it exists ──────────────────────────────────────────
if exist .env (
    echo   Loading environment from .env ...
    for /f "usebackq tokens=1,2 delims==" %%A in (`findstr /v "^#" .env`) do (
        if not "%%A"=="" set "%%A=%%B"
    )
) else (
    echo.
    echo   [WARN] No .env file found^^!
    echo   Copy .env.example to .env and add your SARVAM_API_KEY.
    echo   Ensure Ollama is running: ollama serve
    echo   Sarvam key: https://dashboard.sarvam.ai
)

REM ── Install dependencies ─────────────────────────────────────────────────
echo   Installing / verifying dependencies...
pip install -r requirements.txt -q

echo.
echo   Starting server at http://localhost:8000
echo   Open http://localhost:8000 in your browser
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
