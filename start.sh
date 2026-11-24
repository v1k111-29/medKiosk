#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "  medKiosk"
echo "  ──────────────────────────────────────────"

# Settings (.env) are read by the app itself (app/core/config.py).
if [ ! -f .env ]; then
  echo "  [WARN] No .env file found — using dev defaults. Copy .env.example to .env."
fi

# Use the project virtualenv if present
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -f .venv/Scripts/activate ]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
fi

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python

echo "  Installing dependencies..."
"$PY" -m pip install -r requirements.txt -q

echo "  Applying database migrations..."
"$PY" -m alembic upgrade head

echo ""
echo "  Starting server at http://localhost:8000  (single worker)"
echo "  ──────────────────────────────────────────"
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
