#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  Hospital Kiosk"
echo "  ──────────────────────────────────────────"
echo "  Installing dependencies..."
pip install -r requirements.txt --break-system-packages -q

echo ""
echo "  Starting server at http://localhost:8000"
echo "  Database: $SCRIPT_DIR/patients.db  (persistent)"
echo "  ──────────────────────────────────────────"
echo "  Open http://localhost:8000 in your browser"
echo ""

python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
