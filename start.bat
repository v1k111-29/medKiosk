@echo off
echo.
echo   Hospital Kiosk - Windows Startup
echo   ----------------------------------
echo   Installing / verifying dependencies...
pip install -r requirements.txt -q
echo.
echo   Starting server at http://localhost:8000
echo   (First run downloads ArcFace model - 1-2 min)
echo   Open http://localhost:8000 in your browser
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
