@echo off
setlocal
cd /d "%~dp0"

echo.
echo   medKiosk - Windows Startup
echo   ----------------------------------

REM Settings (.env) are read by the app itself (app/core/config.py).
if not exist .env (
    echo.
    echo   [WARN] No .env file found - using dev defaults.
    echo   Copy .env.example to .env and add your GROQ_API_KEY.
    echo.
)

REM Use the project virtualenv if present
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat

echo   Installing / verifying dependencies...
python -m pip install -r requirements.txt -q || goto :error

echo   Applying database migrations...
python -m alembic upgrade head || goto :error

echo.
echo   Starting server at http://localhost:8000  (single worker)
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
goto :eof

:error
echo.
echo   [ERROR] Startup failed - see messages above.
pause
exit /b 1
