"""Authenticated Mission Control outbox with a local-only simulated sender and receiver."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import IdentityClient, unauthorized
from .models import (CancelPacket, CreatePacket, ErrorResponse,
                     ContactWindowList, EarthReceivedMessage, MissionControlStatus,
                     OutboxDetail, OutboxPacket, PacketEvent)
from .sender import ContactConfig, SimulatedSender, contact_windows, schedule_state
from .storage import Store

PREFIX = "/api/v1/mission-control"
CONTRACT_VERSION = "1.1.0"
bearer = HTTPBearer(auto_error=False)


def timestamp(value=None):
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fail(status, code, message):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def fingerprint(body):
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def selected_fields(body):
    selected = ["metric:" + item.field for item in body.data.metrics]
    selected += ["alert:" + item.alert_id for item in body.data.alerts]
    if body.data.profile_context:
        selected += ["profile:" + key for key, value in body.data.profile_context.model_dump().items() if value is not None]
    if body.data.message:
        selected.append("message:" + body.data.message.kind)
    if body.data.mission:
        selected.append("mission")
    return selected


def message_view(row):
    return {
        "message_id": row["message_id"], "contract_version": row["contract_version"],
        "source_scope": row["source_scope"], "provenance_status": "user_declared", "data": json.loads(row["data_json"]),
        "selected_fields": json.loads(row["selected_fields_json"]), "status": row["status"],
        "revision": row["revision"], "payload_bytes": row["payload_bytes"],
        "bytes_sent": row["bytes_sent"], "attempt_count": row["attempt_count"],
        "last_attempt_at": row["last_attempt_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "sent_at": row["sent_at"], "earth_received_at": row["earth_received_at"],
    }


def event_view(row):
    return {"event_id": row["event_id"], "event_type": row["event_type"],
            "created_at": row["created_at"], "detail": json.loads(row["detail_json"])}


def create_app(db_path=None, identity_resolver=None, retention_days=None):
    store = Store(db_path or os.environ.get("MISSION_CONTROL_DB_PATH", Path(__file__).parent / "data" / "mission_control.db"))
    resolver = identity_resolver or IdentityClient(os.environ.get("ASTRONAUT_SERVICE_URL", "http://127.0.0.1:8001"))
    contact_config = ContactConfig.from_env()
    sender = SimulatedSender(store, contact_config)
    if retention_days is None:
        retention_days = os.environ.get("MISSION_CONTROL_RETENTION_DAYS", "30")
    retention_days = int(retention_days)
    if not 1 <= retention_days <= 365:
        raise ValueError("MISSION_CONTROL_RETENTION_DAYS must be between 1 and 365")
    @asynccontextmanager
    async def lifespan(app):
        sender_task = asyncio.create_task(sender.run(), name="mission-control-simulated-sender")
        app.state.sender_task = sender_task
        try:
            yield
        finally:
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="Mission Control Outbox", version="1.0.0", docs_url=None, redoc_url=None,
        description="Authenticated local outbox with a deterministic, local-only simulated contact schedule, sender, and receiver.",
        lifespan=lifespan,
    )
    app.state.store = store
    app.state.retention_days = retention_days
    app.state.sender = sender
    origins = [item.strip() for item in os.environ.get("MISSION_CONTROL_CORS_ORIGINS", "http://localhost:8081,http://127.0.0.1:8081").split(",") if item.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def api_error(request, exc):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail},
                            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None)

    @app.exception_handler(RequestValidationError)
    async def bad_input(request, exc):
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Invalid request fields."}})

    @app.exception_handler(sqlite3.Error)
    async def bad_storage(request, exc):
        return JSONResponse(status_code=503, content={"error": {"code": "storage_unavailable", "message": "Local Mission Control storage is unavailable."}})

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or credentials.scheme.lower() != "bearer":
            unauthorized()
        return resolver(credentials.credentials)["astronaut_id"], credentials.credentials

    def validate_profile_selection(body, astronaut_id, token):
        profile_context = body.data.profile_context
        if body.source_scope != "account_profile":
            return
        if profile_context is None and body.data.mission is None:
            fail(422, "profile_selection_required", "Account profile scope requires selected account profile fields.")
        profile = resolver.profile(token)
        if profile.get("astronaut_id") != astronaut_id:
            fail(503, "identity_unavailable", "The authenticated profile could not be confirmed.")
        selected = profile_context.model_dump(exclude_unset=False) if profile_context else {}
        selected = {key: value for key, value in selected.items() if value is not None}
        if body.data.mission is not None:
            selected["mission"] = body.data.mission
        if any(profile.get(key) != value for key, value in selected.items()):
            fail(409, "profile_changed", "Selected profile data changed. Reload the profile and review the update again.")

    errors = {code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 503)}

    def purge():
        store.purge_expired_terminal(retention_days, datetime.now(timezone.utc))

    @app.get(PREFIX + "/status", response_model=MissionControlStatus, responses=errors)
    def status(user=Depends(identity)):
        user, _token = user
        purge()
        with store.connect() as db:
            schedule = schedule_state(db, contact_config)
            counts = {row["status"]: row["count"] for row in db.execute(
                "SELECT status,COUNT(*) AS count FROM outbox_messages WHERE astronaut_id=? GROUP BY status", (user,)
            ).fetchall()}
            last_sent = db.execute("SELECT MAX(sent_at) FROM outbox_messages WHERE astronaut_id=? AND status='sent'", (user,)).fetchone()[0]
        return {"contract_version": CONTRACT_VERSION, "service_state": "ready", "transport_state": "simulated",
                "link_state": schedule["link_state"],
                "current_window_ends_at": schedule["current_window_ends_at"],
                "next_contact_at": schedule["next_contact_at"],
                "window_duration_seconds": contact_config.window_seconds,
                "window_capacity_bytes": contact_config.capacity_bytes,
                "transfer_rate_bytes_per_second": contact_config.transfer_rate_bytes_per_second,
                "queued_count": counts.get("queued", 0),
                "deferred_count": counts.get("deferred", 0),
                "transmitting_count": counts.get("transmitting", 0), "sent_count": counts.get("sent", 0),
                "cancelled_count": counts.get("cancelled", 0), "failed_count": counts.get("failed", 0),
                "retention_days": retention_days,
                "last_sent_at": last_sent}

    @app.get(PREFIX + "/contact-windows", response_model=ContactWindowList, responses=errors)
    def windows(user=Depends(identity), limit: int = Query(default=5, ge=1, le=24)):
        _user, _token = user
        with store.connect() as db:
            result = contact_windows(db, contact_config, limit)
        return result

    @app.post(PREFIX + "/outbox", response_model=OutboxPacket, status_code=201, responses=errors)
    def create_packet(body: CreatePacket, auth=Depends(identity),
                      idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128)):
        user, token = auth
        idempotency_key = idempotency_key.strip()
        if not idempotency_key or len(idempotency_key) > 128:
            fail(422, "invalid_idempotency_key", "Idempotency-Key must contain 1 to 128 non-space characters.")
        validate_profile_selection(body, user, token)
        payload = body.model_dump(mode="json")
        digest = fingerprint(payload)
        created = timestamp()
        message_id = str(uuid4())
        data_json = json.dumps(body.data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        fields_json = json.dumps(selected_fields(body), sort_keys=False, separators=(",", ":"), ensure_ascii=False)
        packet_json = json.dumps({
            "message_id": message_id,
            "contract_version": body.contract_version,
            "created_at": created,
            "source_scope": body.source_scope,
            "selected_fields": json.loads(fields_json),
            "data": json.loads(data_json),
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload_bytes = len(packet_json.encode("utf-8"))
        try:
            with store.connect(write=True) as db:
                previous = db.execute("SELECT fingerprint,response_json FROM idempotency WHERE astronaut_id=? AND operation='create_outbox' AND key=?",
                                      (user, idempotency_key)).fetchone()
                if previous:
                    if previous["fingerprint"] != digest:
                        fail(409, "idempotency_conflict", "This idempotency key was used with a different request.")
                    message_id = json.loads(previous["response_json"])["message_id"]
                    row = db.execute("SELECT * FROM outbox_messages WHERE message_id=? AND astronaut_id=?", (message_id, user)).fetchone()
                    if row is None:
                        fail(409, "idempotency_expired", "This request has expired from the outbox retention period.")
                    return message_view(row)
                db.execute("""INSERT INTO outbox_messages (
                    message_id,astronaut_id,contract_version,source_scope,data_json,selected_fields_json,status,
                    revision,payload_bytes,bytes_sent,attempt_count,created_at,updated_at,sent_at,earth_received_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (message_id, user, body.contract_version, body.source_scope, data_json, fields_json, "queued",
                            1, payload_bytes, 0, 0, created, created, None, None))
                db.execute("INSERT INTO outbox_events (message_id,astronaut_id,event_type,created_at,detail_json) VALUES (?,?,?,?,?)",
                           (message_id, user, "queued", created, json.dumps({"transport": "simulated"})))
                Store.remember_create(db, user, idempotency_key, digest, {"message_id": message_id}, created)
                row = db.execute("SELECT * FROM outbox_messages WHERE message_id=?", (message_id,)).fetchone()
                return message_view(row)
        except sqlite3.IntegrityError:
            fail(409, "idempotency_conflict", "This request could not be queued because its identifier already exists.")

    @app.get(PREFIX + "/outbox", response_model=list[OutboxPacket], responses=errors)
    def outbox(user=Depends(identity), limit: int = Query(default=20, ge=1, le=100)):
        user, _token = user
        purge()
        with store.connect() as db:
            rows = db.execute("SELECT * FROM outbox_messages WHERE astronaut_id=? ORDER BY created_at DESC LIMIT ?",
                              (user, limit)).fetchall()
            return [message_view(row) for row in rows]

    @app.get(PREFIX + "/receiver/messages", response_model=list[EarthReceivedMessage], responses=errors)
    def receiver_messages(user=Depends(identity), limit: int = Query(default=50, ge=1, le=200)):
        user, _token = user
        purge()
        with store.connect() as db:
            rows = db.execute("""SELECT m.*,r.received_at FROM simulated_receiver_messages r
                JOIN outbox_messages m ON m.message_id=r.message_id
                WHERE r.astronaut_id=? AND m.astronaut_id=?
                ORDER BY r.received_at DESC LIMIT ?""", (user, user, limit)).fetchall()
            return [{"message": message_view(row), "received_at": row["received_at"]} for row in rows]

    @app.get(PREFIX + "/outbox/{message_id}", response_model=OutboxDetail, responses=errors)
    def packet_detail(message_id: str, user=Depends(identity)):
        user, _token = user
        purge()
        with store.connect() as db:
            row = db.execute("SELECT * FROM outbox_messages WHERE message_id=? AND astronaut_id=?", (message_id, user)).fetchone()
            if row is None:
                fail(404, "outbox_message_not_found", "Outbox message not found.")
            events = db.execute("SELECT * FROM outbox_events WHERE message_id=? AND astronaut_id=? ORDER BY event_id",
                                (message_id, user)).fetchall()
            return {"message": message_view(row), "events": [event_view(event) for event in events]}

    @app.post(PREFIX + "/outbox/{message_id}/cancel", response_model=OutboxPacket, responses=errors)
    def cancel_packet(message_id: str, body: CancelPacket, auth=Depends(identity)):
        user, _token = auth
        purge()
        now = timestamp()
        with store.connect(write=True) as db:
            row = db.execute("SELECT * FROM outbox_messages WHERE message_id=? AND astronaut_id=?", (message_id, user)).fetchone()
            if row is None:
                fail(404, "outbox_message_not_found", "Outbox message not found.")
            if row["status"] == "cancelled":
                return message_view(row)
            if row["status"] not in ("queued", "deferred") or row["attempt_count"] > 0:
                fail(409, "invalid_outbox_state", "Only messages with no transmission attempt can be cancelled.")
            if row["revision"] != body.expected_revision:
                fail(409, "revision_conflict", "Outbox message changed. Reload its current state before retrying.")
            db.execute("UPDATE outbox_messages SET status='cancelled',revision=revision+1,updated_at=? WHERE message_id=?",
                       (now, message_id))
            db.execute("INSERT INTO outbox_events (message_id,astronaut_id,event_type,created_at,detail_json) VALUES (?,?,?,?,?)",
                       (message_id, user, "cancelled", now, json.dumps({"actor": "astronaut"})))
            row = db.execute("SELECT * FROM outbox_messages WHERE message_id=?", (message_id,)).fetchone()
            return message_view(row)

    @app.get("/health")
    def health():
        with store.connect() as db:
            db.execute("SELECT 1 FROM outbox_messages LIMIT 1")
            schedule = schedule_state(db, contact_config)
            receiver_count = db.execute("SELECT COUNT(*) FROM simulated_receiver_messages").fetchone()[0]
        sender_ready = hasattr(app.state, "sender_task") and not app.state.sender_task.done()
        return {"status": "ok", "storage": "available", "transport": "simulated",
                "link_state": schedule["link_state"], "receiver_messages": receiver_count,
                "sender_ready": sender_ready}

    return app
