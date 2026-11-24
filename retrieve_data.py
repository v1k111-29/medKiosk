"""
Dump every table of the configured database (DATABASE_URL, default SQLite
patients.db) to the console. Long values such as face embeddings are truncated.

    python retrieve_data.py            # all tables
    python retrieve_data.py patients   # selected tables
"""

import sys

from sqlalchemy import MetaData, select

from app.core.config import settings
from app.core.database import engine

MAX_CELL = 30


def _cell(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<{len(value)} bytes>"
    text = str(value)
    return text[:MAX_CELL] + "..." if len(text) > MAX_CELL + 3 else text


def _print_table(name: str, columns: list[str], rows: list[tuple]) -> None:
    print(f"\n--- Table: {name} ({len(rows)} rows) ---")
    if not rows:
        print("Table is empty.")
        return
    cells = [[_cell(v) for v in row] for row in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(columns)]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    for r in cells:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))


def main(selected: list[str]) -> None:
    print("=" * 60)
    print(f"DATABASE: {engine.url.render_as_string(hide_password=True)}  (ENV={settings.ENV})")
    print("=" * 60)
    meta = MetaData()
    meta.reflect(bind=engine)
    tables = [t for name, t in sorted(meta.tables.items()) if not selected or name in selected]
    if not tables:
        print("No matching tables found.")
        return
    with engine.connect() as conn:
        for table in tables:
            rows = [tuple(r) for r in conn.execute(select(table))]
            _print_table(table.name, [c.name for c in table.columns], rows)


if __name__ == "__main__":
    main(sys.argv[1:])
