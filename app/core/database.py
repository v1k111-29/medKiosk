"""
Database engine, sessions and migrations (SQLAlchemy 2.0, sync).

- SQLite (dev default) and PostgreSQL (psycopg v3) are both supported.
- Schema is managed only by Alembic (`alembic/`). `run_migrations()` is called on
  startup and upgrades to head.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import BASE_DIR, settings

logger = logging.getLogger("kiosk.db")

BASELINE_REVISION = "0001_baseline"
_LEGACY_TABLES = {"patients", "vitals", "appointments", "face_embeddings", "doctors"}


def _make_engine() -> Engine:
    url = settings.database_url
    if url.startswith("sqlite"):
        eng = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
            pool_pre_ping=True,
        )

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - driver hook
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")
            cur.execute("PRAGMA journal_mode = WAL")
            cur.execute("PRAGMA busy_timeout = 30000")
            cur.close()

        return eng
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine: Engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Session for non-request code (startup, websockets, background work)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _alembic_config():
    from alembic.config import Config

    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    # Do not let alembic's fileConfig() replace the app's logging setup.
    cfg.attributes["configure_logger"] = False
    return cfg


def run_migrations() -> None:
    """Upgrade the database to the latest Alembic revision.

    A pre-Alembic database (tables created by the old raw-sqlite3 init_db) is
    adopted by stamping it at the baseline revision first, then upgraded.
    """
    from alembic import command

    cfg = _alembic_config()
    tables = set(inspect(engine).get_table_names())
    if "alembic_version" not in tables and tables & _LEGACY_TABLES:
        missing = _LEGACY_TABLES - tables
        appt_cols = {c["name"] for c in inspect(engine).get_columns("appointments")} if "appointments" in tables else set()
        if missing or not {"doctor_id", "doctor_name"} <= appt_cols:
            raise RuntimeError(
                "Found an old database that does not match the v2 schema "
                f"(missing tables: {sorted(missing)}). Back it up and remove it, or migrate it manually."
            )
        logger.warning("[DB] Legacy database detected — stamping baseline %s before upgrade", BASELINE_REVISION)
        command.stamp(cfg, BASELINE_REVISION)
    command.upgrade(cfg, "head")
    logger.info("[DB] Migrations at head (%s)", engine.url.render_as_string(hide_password=True))
