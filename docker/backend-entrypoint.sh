#!/bin/sh
# Apply migrations, then start a SINGLE uvicorn worker: the realtime WebSocket hub
# (app/services/realtime.py) is in-process, so more workers would split the clients.
set -e
python -m alembic upgrade head
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips="*" \
  "$@"
