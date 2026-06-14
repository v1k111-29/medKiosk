from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = BASE_DIR / "patients.db"
MED_DB_PATH = BASE_DIR / "medical.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def get_med_db():
    conn = sqlite3.connect(str(MED_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id          INTEGER  PRIMARY KEY AUTOINCREMENT,
            name        TEXT     NOT NULL,
            gender      TEXT,
            age         INTEGER,
            phone       TEXT,
            blood_group TEXT,
            city        TEXT,
            embedding   BLOB,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            visit_count INTEGER  DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

    conn_med = get_med_db()
    conn_med.execute("""
        CREATE TABLE IF NOT EXISTS vitals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER NOT NULL,
            height       INTEGER,
            weight       INTEGER,
            bp_sys       INTEGER,
            bp_dia       INTEGER,
            spo2         INTEGER,
            diabetes     BOOLEAN,
            hypertension BOOLEAN,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn_med.commit()
    conn_med.close()
