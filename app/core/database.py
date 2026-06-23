from pathlib import Path
import sqlite3
from contextlib import contextmanager

# Canonical DB path: project root (parent of app/)
BASE_DIR = Path(__file__).parent.parent.parent.resolve()
DB_PATH = BASE_DIR / "patients.db"


@contextmanager
def get_db():
    """Context manager for database connections with proper cleanup."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def get_db_conn():
    """Get a raw database connection (caller must close)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id           INTEGER  PRIMARY KEY AUTOINCREMENT,
                name         TEXT     NOT NULL,
                gender       TEXT,
                age          INTEGER,
                phone        TEXT,
                blood_group  TEXT,
                city         TEXT,
                embedding    BLOB,
                consent_given BOOLEAN DEFAULT 0,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                visit_count  INTEGER  DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vitals (
                id           INTEGER  PRIMARY KEY AUTOINCREMENT,
                patient_id   INTEGER  NOT NULL
                             REFERENCES patients(id) ON DELETE CASCADE,
                height       REAL,
                weight       REAL,
                bp_sys       INTEGER,
                bp_dia       INTEGER,
                spo2         REAL,
                diabetes     BOOLEAN  DEFAULT 0,
                hypertension BOOLEAN  DEFAULT 0,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id           INTEGER  PRIMARY KEY AUTOINCREMENT,
                patient_id   INTEGER  NOT NULL
                             REFERENCES patients(id) ON DELETE CASCADE,
                token        TEXT     NOT NULL,
                dept_id      TEXT     NOT NULL,
                dept_name    TEXT     NOT NULL,
                room         TEXT,
                symptoms     TEXT,
                service      TEXT     DEFAULT 'symptoms',
                status       TEXT     DEFAULT 'waiting',
                wait_mins    INTEGER  DEFAULT 15,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # ── Face embedding gallery (multi-shot, per patient) ──────────────────
        # Stores up to MAX_EMBEDDINGS_PER_PATIENT embeddings per patient.
        # This allows matching across angles, lighting, and ageing variation.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS face_embeddings (
                id           INTEGER  PRIMARY KEY AUTOINCREMENT,
                patient_id   INTEGER  NOT NULL
                             REFERENCES patients(id) ON DELETE CASCADE,
                embedding    BLOB     NOT NULL,
                angle_hint   TEXT,      -- optional: 'frontal','left','right','low_light'
                quality      REAL,      -- cosine self-distance quality score (lower = closer to avg)
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_face_emb_patient ON face_embeddings(patient_id)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id           INTEGER  PRIMARY KEY AUTOINCREMENT,
                name         TEXT     NOT NULL,
                dept_id      TEXT     NOT NULL,
                dept_name    TEXT     NOT NULL,
                qualification TEXT,
                available    BOOLEAN  DEFAULT 1,
                room         TEXT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE appointments ADD COLUMN doctor_id INTEGER REFERENCES doctors(id)")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE appointments ADD COLUMN doctor_name TEXT")
        except Exception:
            pass
        conn.commit()
    print(f"[DB] Initialized -> {DB_PATH}")


def seed_doctors():
    """Seed default doctors if the table is empty."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
        if count > 0:
            return
        doctors = [
            ('Dr. Rajesh Kumar',    'general',   'General Medicine', 'MD, General Medicine', 1, 'OPD-1'),
            ('Dr. Priya Sharma',    'general',   'General Medicine', 'MBBS, DNB',            1, 'OPD-1'),
            ('Dr. Suresh Menon',    'cardio',    'Cardiology',       'DM Cardiology',        1, 'OPD-3'),
            ('Dr. Anitha Rao',      'cardio',    'Cardiology',       'MD, Cardiology',       1, 'OPD-3'),
            ('Dr. Vikram Singh',    'ortho',     'Orthopaedics',     'MS Ortho',             1, 'OPD-4'),
            ('Dr. Kavitha Nair',    'ortho',     'Orthopaedics',     'MCh Ortho',            1, 'OPD-4'),
            ('Dr. Meena Iyer',      'paeds',     'Paediatrics',      'MD Paediatrics',       1, 'OPD-2'),
            ('Dr. Lakshmi Devi',    'gyne',      'Gynaecology',      'MS OBG',               1, 'OPD-5'),
            ('Dr. Deepa Rajan',     'gyne',      'Gynaecology',      'DGO',                  1, 'OPD-5'),
            ('Dr. Arjun Pillai',    'derm',      'Dermatology',      'MD Dermatology',       1, 'OPD-6'),
            ('Dr. Srinivas Reddy',  'ent',       'ENT',              'MS ENT',               1, 'OPD-7'),
            ('Dr. Farida Begum',    'ent',       'ENT',              'DNB ENT',              1, 'OPD-7'),
            ('Dr. Ganesh Subramani','ophthal',   'Ophthalmology',    'MS Ophthalmology',     1, 'OPD-8'),
            ('Dr. Karthik Rajan',   'emergency', 'Emergency',        'MD Emergency Medicine',1, 'ER-1'),
            ('Dr. Revathi Kumar',   'emergency', 'Emergency',        'MD, Critical Care',    1, 'ER-1'),
        ]
        conn.executemany(
            "INSERT INTO doctors (name, dept_id, dept_name, qualification, available, room) VALUES (?,?,?,?,?,?)",
            doctors,
        )
        conn.commit()
        print(f"[DB] Seeded {len(doctors)} doctors")
