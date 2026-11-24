"""
Test configuration.

Environment variables are set BEFORE any `app` import so the cached settings and
the SQLAlchemy engine point at a throw-away SQLite database (deleted at the end).
Process env vars take precedence over `.env`, so local secrets are never used.

Set TEST_DATABASE_URL (e.g. postgresql+psycopg://medkiosk:pw@localhost:5432/medkiosk_test)
to run the suite against PostgreSQL instead. The database name must contain "test";
its `public` schema is DROPPED and recreated at the start of the run.
"""

import gc
import os
import shutil
import tempfile

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="medkiosk-test-")
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "").strip()


def _reset_postgres(url: str) -> None:
    from sqlalchemy import create_engine, make_url, text

    name = make_url(url).database or ""
    if "test" not in name.lower():
        raise RuntimeError(f"TEST_DATABASE_URL database {name!r} must contain 'test' (it is wiped)")
    eng = create_engine(url, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    eng.dispose()


if _TEST_DB_URL:
    _reset_postgres(_TEST_DB_URL)

os.environ.update({
    "ENV": "dev",
    "DATABASE_URL": _TEST_DB_URL or "sqlite:///" + os.path.join(_TMP_DIR, "test.db").replace("\\", "/"),
    "KIOSK_DEVICE_KEYS": "",
    "SMS_PROVIDER": "mock",
    "GROQ_API_KEY": "",          # LLM unavailable → exercises the rule-based fallback
    "SEED_DEMO_USERS": "true",
    "FACE_WARMUP": "false",      # never load TensorFlow models during unit tests
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
