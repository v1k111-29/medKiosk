"""
Test configuration.

Environment variables are set BEFORE any `app` import so the cached settings and
the SQLAlchemy engine point at a throw-away SQLite database (deleted at the end).
Process env vars take precedence over `.env`, so local secrets are never used.
"""

import gc
import os
import shutil
import tempfile

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="medkiosk-test-")
os.environ.update({
    "ENV": "dev",
    "DATABASE_URL": "sqlite:///" + os.path.join(_TMP_DIR, "test.db").replace("\\", "/"),
    "KIOSK_DEVICE_KEYS": "",
    "SMS_PROVIDER": "mock",
    "GROQ_API_KEY": "",          # LLM unavailable → exercises the rule-based fallback
    "SEED_DEMO_USERS": "true",
    "JWT_SECRET": "test-secret-for-pytest-only-0123456789abcdef",
})


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post("/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def pytest_sessionfinish(session, exitstatus):
    try:
        from app.core.database import engine

        engine.dispose()
    except Exception:
        pass
    gc.collect()
    shutil.rmtree(_TMP_DIR, ignore_errors=True)
