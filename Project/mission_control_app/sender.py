"""Deterministic, local-only simulated contact schedule and store-and-forward worker."""
import asyncio
import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class ContactConfig:
    cycle_seconds: int = 60
    window_seconds: int = 20
    capacity_bytes: int = 4096
    transfer_rate_bytes_per_second: int = 512
    poll_seconds: float = 0.5

    @classmethod
    def from_env(cls):
        config = cls(
            cycle_seconds=int(os.environ.get("MISSION_CONTROL_CYCLE_SECONDS", "60")),
            window_seconds=int(os.environ.get("MISSION_CONTROL_WINDOW_SECONDS", "20")),
            capacity_bytes=int(os.environ.get("MISSION_CONTROL_WINDOW_CAPACITY_BYTES", "4096")),
            transfer_rate_bytes_per_second=int(os.environ.get("MISSION_CONTROL_TRANSFER_RATE_BYTES_PER_SECOND", "512")),
            poll_seconds=float(os.environ.get("MISSION_CONTROL_SENDER_POLL_SECONDS", "0.5")),
        )
        if not 2 <= config.cycle_seconds <= 86400:
            raise ValueError("MISSION_CONTROL_CYCLE_SECONDS must be between 2 and 86400")
        if not 1 <= config.window_seconds < config.cycle_seconds:
            raise ValueError("MISSION_CONTROL_WINDOW_SECONDS must be positive and shorter than the cycle")
        if not 1 <= config.capacity_bytes <= 10_000_000:
            raise ValueError("MISSION_CONTROL_WINDOW_CAPACITY_BYTES must be between 1 and 10000000")
        if not 1 <= config.transfer_rate_bytes_per_second <= 1_000_000:
            raise ValueError("MISSION_CONTROL_TRANSFER_RATE_BYTES_PER_SECOND must be between 1 and 1000000")
        if not 0.1 <= config.poll_seconds <= 5:
            raise ValueError("MISSION_CONTROL_SENDER_POLL_SECONDS must be between 0.1 and 5")
        return config


def schedule_state(db, config: ContactConfig, now_epoch=None):
    now_epoch = now_epoch if now_epoch is not None else datetime.now(timezone.utc).timestamp()
    anchor = db.execute("SELECT anchor_epoch FROM simulated_contact_state WHERE singleton=1").fetchone()[0]
    elapsed = max(0.0, now_epoch - anchor)
    index = math.floor(elapsed / config.cycle_seconds)
    start = anchor + index * config.cycle_seconds
    end = start + config.window_seconds
    open_now = now_epoch < end
    if not open_now:
        start += config.cycle_seconds
        end = start + config.window_seconds
    return {
        "link_state": "open" if open_now else "closed",
        "current_window_ends_at": iso(anchor + index * config.cycle_seconds + config.window_seconds) if open_now else None,
        "next_contact_at": iso(start),
        "window_start_epoch": start,
        "window_end_epoch": end,
        "window_id": str(round(start * 1000)),
    }


def contact_windows(db, config: ContactConfig, count=5, now_epoch=None):
    current = schedule_state(db, config, now_epoch)
    open_now = current["link_state"] == "open"
    first_start = current["window_start_epoch"]
    windows = []
    for offset in range(count):
        start = first_start + offset * config.cycle_seconds
        window_id = str(round(start * 1000))
        row = db.execute("SELECT bytes_used FROM simulated_contact_windows WHERE window_id=?", (window_id,)).fetchone()
        is_open = open_now and offset == 0
        windows.append({
            "window_id": window_id,
            "starts_at": iso(start),
            "ends_at": iso(start + config.window_seconds),
            "state": "open" if is_open else "upcoming",
            "capacity_bytes": config.capacity_bytes,
            "bytes_used": row["bytes_used"] if row else 0,
        })
    return {"simulated": True, "windows": windows}


def _event(db, row, event_type, created_at, detail):
    db.execute("INSERT INTO outbox_events(message_id,astronaut_id,event_type,created_at,detail_json) VALUES (?,?,?,?,?)",
               (row["message_id"], row["astronaut_id"], event_type, created_at,
                json.dumps(detail, sort_keys=True, separators=(",", ":"))))


class SimulatedSender:
    def __init__(self, store, config: ContactConfig):
        self.store = store
        self.config = config
        self._byte_fraction = 0.0

    def recover(self):
        now = iso(datetime.now(timezone.utc).timestamp())
        with self.store.connect(write=True) as db:
            rows = db.execute("SELECT * FROM outbox_messages WHERE status='transmitting'").fetchall()
            for row in rows:
                db.execute("UPDATE outbox_messages SET status='deferred',revision=revision+1,updated_at=? WHERE message_id=?",
                           (now, row["message_id"]))
                _event(db, row, "deferred", now, {"reason": "service_restart", "bytes_sent": str(row["bytes_sent"])})

    def process_tick(self, elapsed_seconds):
        now_epoch = datetime.now(timezone.utc).timestamp()
        now = iso(now_epoch)
        with self.store.connect(write=True) as db:
            state = schedule_state(db, self.config, now_epoch)
            pending = db.execute("SELECT * FROM outbox_messages WHERE status IN ('queued','deferred','transmitting') ORDER BY created_at,message_id").fetchall()
            if state["link_state"] != "open":
                for row in pending:
                    if row["status"] in ("queued", "transmitting"):
                        db.execute("UPDATE outbox_messages SET status='deferred',revision=revision+1,updated_at=? WHERE message_id=?",
                                   (now, row["message_id"]))
                        _event(db, row, "deferred", now, {"reason": "contact_window_closed", "bytes_sent": str(row["bytes_sent"])})
                return

            window_id = state["window_id"]
            db.execute("INSERT OR IGNORE INTO simulated_contact_windows(window_id,starts_at,bytes_used) VALUES (?,?,0)",
                       (window_id, iso(state["window_start_epoch"])))
            db.execute("DELETE FROM simulated_contact_windows WHERE starts_at<?", (iso(now_epoch - 86400),))
            used = db.execute("SELECT bytes_used FROM simulated_contact_windows WHERE window_id=?", (window_id,)).fetchone()[0]
            budget = max(0, self.config.capacity_bytes - used)
            self._byte_fraction += self.config.transfer_rate_bytes_per_second * max(0, elapsed_seconds)
            allowance = min(budget, int(self._byte_fraction))
            if allowance <= 0:
                return
            self._byte_fraction -= allowance

            while allowance > 0:
                row = db.execute("""SELECT * FROM outbox_messages
                    WHERE status IN ('transmitting','queued','deferred')
                    ORDER BY CASE status WHEN 'transmitting' THEN 0 ELSE 1 END, created_at, message_id LIMIT 1""").fetchone()
                if row is None:
                    break
                if row["status"] != "transmitting":
                    event_type = "resumed" if row["bytes_sent"] > 0 else "transmission_started"
                    db.execute("""UPDATE outbox_messages SET status='transmitting',attempt_count=attempt_count+1,
                        last_attempt_at=?,revision=revision+1,updated_at=? WHERE message_id=?""",
                               (now, now, row["message_id"]))
                    _event(db, row, event_type, now, {"window_id": window_id})
                    row = db.execute("SELECT * FROM outbox_messages WHERE message_id=?", (row["message_id"],)).fetchone()

                remaining = max(0, row["payload_bytes"] - row["bytes_sent"])
                amount = min(remaining, allowance)
                if amount <= 0:
                    self._complete(db, row, now, window_id)
                    continue
                new_sent = row["bytes_sent"] + amount
                allowance -= amount
                db.execute("UPDATE simulated_contact_windows SET bytes_used=bytes_used+? WHERE window_id=?", (amount, window_id))
                db.execute("UPDATE outbox_messages SET bytes_sent=?,updated_at=? WHERE message_id=?", (new_sent, now, row["message_id"]))
                row = db.execute("SELECT * FROM outbox_messages WHERE message_id=?", (row["message_id"],)).fetchone()
                if new_sent >= row["payload_bytes"]:
                    self._complete(db, row, now, window_id)

            current = db.execute("SELECT * FROM outbox_messages WHERE status='transmitting'").fetchall()
            used_now = db.execute("SELECT bytes_used FROM simulated_contact_windows WHERE window_id=?", (window_id,)).fetchone()[0]
            if used_now >= self.config.capacity_bytes:
                for row in current:
                    db.execute("UPDATE outbox_messages SET status='deferred',revision=revision+1,updated_at=? WHERE message_id=?",
                               (now, row["message_id"]))
                    _event(db, row, "deferred", now, {"reason": "window_capacity_exhausted", "bytes_sent": str(row["bytes_sent"])})

    def _complete(self, db, row, now, window_id):
        receiver_row = db.execute("SELECT 1 FROM simulated_receiver_messages WHERE message_id=?", (row["message_id"],)).fetchone()
        if receiver_row is None:
            packet_json = json.dumps({
                "message_id": row["message_id"], "contract_version": row["contract_version"],
                "created_at": row["created_at"],
                "source_scope": row["source_scope"], "data": json.loads(row["data_json"]),
                "selected_fields": json.loads(row["selected_fields_json"]),
            }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            db.execute("INSERT INTO simulated_receiver_messages(message_id,astronaut_id,packet_json,received_at) VALUES (?,?,?,?)",
                       (row["message_id"], row["astronaut_id"], packet_json, now))
        db.execute("UPDATE outbox_messages SET status='sent',sent_at=?,earth_received_at=?,revision=revision+1,updated_at=? WHERE message_id=?",
                   (now, now, now, row["message_id"]))
        _event(db, row, "sent", now, {"window_id": window_id})
        _event(db, row, "received", now, {"receiver": "local_simulated_receiver", "window_id": window_id})

    async def run(self):
        self.recover()
        last = asyncio.get_running_loop().time()
        while True:
            await asyncio.sleep(self.config.poll_seconds)
            tick = asyncio.get_running_loop().time()
            elapsed = tick - last
            last = tick
            try:
                self.process_tick(elapsed)
            except Exception:
                logging.exception("Mission Control simulation tick failed; it will retry.")
