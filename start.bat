@echo off
setlocal
cd /d "%~dp0"

echo.
echo   medKiosk - one-click start (Windows, dev / single PC)
echo   ----------------------------------------------------
echo   Backend  http://localhost:8000
echo   Kiosk    http://localhost:5173
echo   Staff    http://localhost:5174   (queue: /queue, display board: /display)
echo.

REM --- Settings ---
REM .env is read by the app itself (app/core/config.py).
if not exist .env (
    echo   [WARN] No .env file found - copying .env.example.
    echo          Add your GROQ_API_KEY to .env, then run start.bat again.
    copy /y .env.example .env >nul
    notepad .env
    goto :end
)

REM --- Tools ---
where python >nul 2>&1 || (echo   [ERROR] Python 3.11 not found. Install it from python.org. & goto :error)
where npm    >nul 2>&1 || (echo   [ERROR] Node.js not found. Install Node 20+ from nodejs.org. & goto :error)

REM --- Python virtualenv + dependencies (first run only) ---
if not exist .venv\Scripts\python.exe (
    echo   Creating Python virtualenv .venv ...
    python -m venv .venv || goto :error
)
set PY=.venv\Scripts\python.exe

if not exist .venv\.deps-ok (
    echo   Installing Python dependencies (first run, can take several minutes^)...
    "%PY%" -m pip install -q --upgrade pip
    "%PY%" -m pip install -q -r requirements.txt
    if errorlevel 1 (
        echo   [WARN] Full install failed ^(face recognition / TensorFlow^).
        echo          Installing base dependencies only - face ID will be disabled,
        echo          phone check-in still works. Re-run later to retry.
        "%PY%" -m pip install -q -r requirements-base.txt || goto :error
    ) else (
        echo ok> .venv\.deps-ok
    )
)

REM --- Node dependencies (first run only) ---
if not exist frontend\node_modules (
    echo   Installing kiosk app dependencies...
    call npm --prefix frontend install --no-audit --no-fund || goto :error
)
if not exist staff\node_modules (
    echo   Installing staff app dependencies...
    call npm --prefix staff install --no-audit --no-fund || goto :error
)

REM --- Database ---
echo   Applying database migrations...
"%PY%" -m alembic upgrade head || goto :error

REM --- Start the three servers, each in its own window ---
echo   Starting servers...
start "medKiosk backend" cmd /k ""%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
start "medKiosk kiosk"   cmd /k "npm --prefix frontend run dev"
start "medKiosk staff"   cmd /k "npm --prefix staff run dev"

REM Wait for the backend to answer /health (max ~60 s), then open browsers.
echo   Waiting for backend...
for /l %%i in (1,1,30) do (
    "%PY%" -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" >nul 2>&1 && goto :ready
    timeout /t 2 /nobreak >nul
)
echo   [WARN] Backend did not answer yet - check the "medKiosk backend" window.

:ready
start "" http://localhost:5173
start "" http://localhost:5174/queue
echo.
echo   Running. Close the three server windows to stop.
echo   Demo staff login (dev only): nurse1 / Nurse@123, admin / Admin@123
goto :end

:error
echo.
echo   [ERROR] Startup failed - see messages above.
pause
exit /b 1

:end
endlocal
