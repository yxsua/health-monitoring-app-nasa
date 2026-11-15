import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise RuntimeError("Unsupported chatbot database version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, astronaut_id TEXT NOT NULL,
                    code TEXT NOT NULL, version TEXT NOT NULL, definition TEXT NOT NULL,
                    status TEXT NOT NULL, revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS session_owner ON sessions(astronaut_id);
                CREATE TABLE IF NOT EXISTS answers (
                    session_id TEXT NOT NULL REFERENCES sessions(id), question_id TEXT NOT NULL,
                    value INTEGER NOT NULL CHECK(value BETWEEN 0 AND 3),
                    PRIMARY KEY(session_id, question_id)
                );
                CREATE TABLE IF NOT EXISTS results (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id), payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS flags (
                    session_id TEXT PRIMARY KEY REFERENCES sessions(id), created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS summaries (
                    astronaut_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS check_ins (
                    astronaut_id TEXT NOT NULL, check_in_date TEXT NOT NULL,
                    mood_score INTEGER NOT NULL CHECK(mood_score BETWEEN 1 AND 5),
                    sleep_duration_hours REAL NOT NULL CHECK(sleep_duration_hours BETWEEN 0 AND 24),
                    revision INTEGER NOT NULL CHECK(revision > 0),
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    PRIMARY KEY(astronaut_id, check_in_date)
                );
                CREATE INDEX IF NOT EXISTS check_in_owner_date ON check_ins(astronaut_id, check_in_date DESC);
                CREATE TABLE IF NOT EXISTS idempotency (
                    astronaut_id TEXT NOT NULL, operation TEXT NOT NULL, key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, response TEXT NOT NULL,
                    PRIMARY KEY(astronaut_id, operation, key)
                );
                PRAGMA user_version=2;
            """)

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            # Serialize revision checks and changes in the same transaction.
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
