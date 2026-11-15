import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect(write=True) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise RuntimeError("Unsupported Mission Control database version")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS outbox_messages (
                    message_id TEXT PRIMARY KEY,
                    astronaut_id TEXT NOT NULL,
                    contract_version TEXT NOT NULL,
                    source_scope TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    selected_fields_json TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued','deferred','transmitting','sent','cancelled','failed')),
                    revision INTEGER NOT NULL CHECK(revision > 0),
                    payload_bytes INTEGER NOT NULL CHECK(payload_bytes >= 0),
                    bytes_sent INTEGER NOT NULL DEFAULT 0 CHECK(bytes_sent >= 0),
                    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
                    last_attempt_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sent_at TEXT,
                    earth_received_at TEXT
                );
                CREATE INDEX IF NOT EXISTS outbox_owner_created
                    ON outbox_messages(astronaut_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS outbox_status_updated
                    ON outbox_messages(status, updated_at);
                CREATE TABLE IF NOT EXISTS outbox_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL REFERENCES outbox_messages(message_id) ON DELETE CASCADE,
                    astronaut_id TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type IN ('queued','deferred','transmission_started','resumed','sent','received','cancelled','failed')),
                    created_at TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS outbox_events_owner_message
                    ON outbox_events(astronaut_id, message_id, event_id);
                CREATE TABLE IF NOT EXISTS idempotency (
                    astronaut_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    key TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(astronaut_id, operation, key)
                );
                CREATE TABLE IF NOT EXISTS simulated_contact_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    anchor_epoch REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS simulated_contact_windows (
                    window_id TEXT PRIMARY KEY,
                    starts_at TEXT NOT NULL,
                    bytes_used INTEGER NOT NULL DEFAULT 0 CHECK(bytes_used >= 0)
                );
                CREATE TABLE IF NOT EXISTS simulated_receiver_messages (
                    message_id TEXT PRIMARY KEY,
                    astronaut_id TEXT NOT NULL,
                    packet_json TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );
            """)
            if "message_id" not in {row["name"] for row in db.execute("PRAGMA table_info(idempotency)").fetchall()}:
                # v1 already stored the response ID in JSON; make the relation queryable
                # so active queue keys do not expire while their packets remain queued.
                db.execute("ALTER TABLE idempotency ADD COLUMN message_id TEXT")
                rows = db.execute("SELECT astronaut_id,operation,key,response_json FROM idempotency").fetchall()
                for row in rows:
                    message_id = json.loads(row["response_json"]).get("message_id")
                    if message_id:
                        db.execute("UPDATE idempotency SET message_id=? WHERE astronaut_id=? AND operation=? AND key=?",
                                   (message_id, row["astronaut_id"], row["operation"], row["key"]))
            columns = {row["name"] for row in db.execute("PRAGMA table_info(outbox_messages)").fetchall()}
            if "last_attempt_at" not in columns:
                db.execute("ALTER TABLE outbox_messages ADD COLUMN last_attempt_at TEXT")
            if version < 3:
                db.execute("ALTER TABLE outbox_events RENAME TO outbox_events_v2")
                db.execute("DROP INDEX IF EXISTS outbox_events_owner_message")
                db.execute("""CREATE TABLE outbox_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL REFERENCES outbox_messages(message_id) ON DELETE CASCADE,
                    astronaut_id TEXT NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type IN ('queued','deferred','transmission_started','resumed','sent','received','cancelled','failed')),
                    created_at TEXT NOT NULL,
                    detail_json TEXT NOT NULL
                )""")
                db.execute("INSERT INTO outbox_events SELECT * FROM outbox_events_v2")
                db.execute("DROP TABLE outbox_events_v2")
                db.execute("CREATE INDEX IF NOT EXISTS outbox_events_owner_message ON outbox_events(astronaut_id,message_id,event_id)")
            db.execute("INSERT OR IGNORE INTO simulated_contact_state(singleton,anchor_epoch) VALUES (1,?)", (datetime.now(timezone.utc).timestamp(),))
            db.execute("PRAGMA user_version=3")

    @contextmanager
    def connect(self, write=False):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def remember_create(db, astronaut_id, key, fingerprint, response, created_at):
        db.execute("INSERT INTO idempotency (astronaut_id,operation,key,fingerprint,response_json,message_id,created_at) VALUES (?,?,?,?,?,?,?)",
                   (astronaut_id, "create_outbox", key, fingerprint, json.dumps(response, sort_keys=True),
                    response["message_id"], created_at))

    def purge_expired_terminal(self, retention_days, now):
        cutoff = (now - timedelta(days=retention_days)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        with self.connect(write=True) as db:
            db.execute("""DELETE FROM simulated_receiver_messages WHERE message_id IN (
                SELECT message_id FROM outbox_messages
                WHERE status IN ('sent','cancelled','failed') AND updated_at<?
            )""", (cutoff,))
            db.execute("""DELETE FROM idempotency WHERE message_id IN (
                SELECT message_id FROM outbox_messages
                WHERE status IN ('sent','cancelled','failed') AND updated_at<?
            )""", (cutoff,))
            db.execute("DELETE FROM outbox_messages WHERE status IN ('sent','cancelled','failed') AND updated_at<?", (cutoff,))
