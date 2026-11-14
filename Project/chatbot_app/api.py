"""Run: uvicorn Project.chatbot_app.api:create_app --factory --port 8002."""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .assessments import VERSION, RULE_VERSION, SUPPORT, definition, score
from .auth import IdentityClient, unauthorized
from .models import (Start, Revision, Answer, Message, Definition, Session, Result,
                     RiskSummary, AssistantReply, ErrorResponse)
from .storage import Store

PREFIX = "/api/v1/chatbot"
bearer = HTTPBearer(auto_error=False)


def timestamp():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fail(status, code, message):
    raise HTTPException(status, detail={"code": code, "message": message})


def follow_up(triggered=False, evaluated=False):
    return {"status": "follow_up_requested" if triggered else "not_triggered" if evaluated else "unknown",
            "guidance": SUPPORT if triggered else None}


def owned(db, session_id, astronaut_id):
    row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if row is None:
        fail(404, "session_not_found", "Unknown assessment session.")
    if row["astronaut_id"] != astronaut_id:
        fail(403, "forbidden", "This session belongs to another astronaut.")
    return row


def view(db, row):
    bundle = json.loads(row["definition"])
    answers = {a["question_id"]: a["value"] for a in db.execute("SELECT * FROM answers WHERE session_id=?", (row["id"],))}
    triggered = db.execute("SELECT 1 FROM flags WHERE session_id=?", (row["id"],)).fetchone() is not None
    current = next((q for q in bundle["questions"] if q["id"] not in answers), None) if row["status"] == "in_progress" else None
    return {"session_id": row["id"], "astronaut_id": row["astronaut_id"], "assessment": bundle,
            "status": row["status"], "revision": row["revision"], "responses": answers,
            "current_question": current, "follow_up": follow_up(triggered, bundle["follow_up_question_id"] in answers),
            "created_at": row["created_at"], "updated_at": row["updated_at"]}


def bump_summary(db, astronaut_id, time):
    db.execute("""INSERT INTO summaries VALUES (?,1,?) ON CONFLICT(astronaut_id)
                  DO UPDATE SET revision=revision+1, updated_at=excluded.updated_at""", (astronaut_id, time))


def fingerprint(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def replay(db, astronaut, operation, key, body):
    row = db.execute("SELECT * FROM idempotency WHERE astronaut_id=? AND operation=? AND key=?", (astronaut, operation, key)).fetchone()
    if row:
        if row["fingerprint"] != fingerprint(body):
            fail(409, "idempotency_conflict", "This idempotency key was used with a different request.")
        return json.loads(row["response"])


def remember(db, astronaut, operation, key, body, response):
    db.execute("INSERT INTO idempotency VALUES (?,?,?,?,?)", (astronaut, operation, key, fingerprint(body), json.dumps(response)))


def check_revision(row, expected):
    if row["revision"] != expected:
        fail(409, "revision_conflict", "Session changed. Reload its current state before retrying.")


def create_app(db_path=None, identity_resolver=None):
    store = Store(db_path or os.environ.get("CHATBOT_DB_PATH", Path(__file__).parent / "data" / "chatbot.db"))
    resolver = identity_resolver or IdentityClient(os.environ.get("ASTRONAUT_SERVICE_URL", "http://127.0.0.1:8001"))
    app = FastAPI(title="Astronaut Assessment Chatbot", version="1.0.0", docs_url=None, redoc_url=None,
                  description="Local structured screening demo with static explanations. No model, simulator, or external network dependency. Bearer tokens are verified with astronaut_app on every protected request.")
    app.state.store = store
    origins = [s.strip() for s in os.environ.get("CHATBOT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if s.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

    @app.middleware("http")
    async def no_cache(request, call_next):
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
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Invalid request fields or missing Idempotency-Key."}})

    @app.exception_handler(sqlite3.Error)
    async def bad_storage(request, exc):
        return JSONResponse(status_code=503, content={"error": {"code": "storage_unavailable", "message": "Local chatbot storage is unavailable."}})

    def identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or credentials.scheme.lower() != "bearer":
            unauthorized()
        return resolver(credentials.credentials)["astronaut_id"]

    errors = {n: {"model": ErrorResponse} for n in (401, 403, 404, 409, 422, 503)}

    @app.get(PREFIX + "/assessments", response_model=list[Definition], responses=errors)
    def assessments(user=Depends(identity)):
        return [definition(code) for code in ("PHQ9", "GAD7")]

    @app.post(PREFIX + "/sessions", response_model=Session, status_code=201, responses=errors)
    def start(body: Start, user=Depends(identity), idempotency_key: str = Header(min_length=1, max_length=128)):
        payload = body.model_dump()
        with store.connect(write=True) as db:
            old = replay(db, user, "create", idempotency_key, payload)
            if old is not None:
                return old
            if body.assessment_version != VERSION:
                fail(422, "unsupported_version", "Select a published assessment version.")
            bundle = definition(body.assessment_code)
            session_id, time = str(uuid4()), timestamp()
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)", (session_id, user, body.assessment_code,
                       VERSION, json.dumps(bundle), "in_progress", 0, time, time))
            response = view(db, owned(db, session_id, user))
            remember(db, user, "create", idempotency_key, payload, response)
            return response

    @app.get(PREFIX + "/sessions", response_model=list[Session], responses=errors)
    def sessions(user=Depends(identity)):
        with store.connect() as db:
            return [view(db, row) for row in db.execute("SELECT * FROM sessions WHERE astronaut_id=? ORDER BY created_at DESC, id", (user,)).fetchall()]

    @app.get(PREFIX + "/sessions/{session_id}", response_model=Session, responses=errors)
    def session(session_id: str, user=Depends(identity)):
        with store.connect() as db:
            return view(db, owned(db, session_id, user))

    @app.put(PREFIX + "/sessions/{session_id}/responses/{question_id}", response_model=Session, responses=errors)
    def answer(session_id: str, question_id: str, body: Answer, user=Depends(identity)):
        with store.connect(write=True) as db:
            row = owned(db, session_id, user)
            check_revision(row, body.expected_revision)
            if row["status"] != "in_progress":
                fail(409, "invalid_state", "Only an in-progress assessment accepts answers.")
            current = view(db, row)
            bundle = current["assessment"]
            if question_id not in {q["id"] for q in bundle["questions"]}:
                fail(422, "invalid_question", "Question is not part of this assessment version.")
            if question_id not in current["responses"] and (current["current_question"] or {}).get("id") != question_id:
                fail(409, "question_order", "Answer the current question first.")
            db.execute("INSERT INTO answers VALUES (?,?,?) ON CONFLICT(session_id,question_id) DO UPDATE SET value=excluded.value",
                       (session_id, question_id, body.value))
            time = timestamp()
            if question_id == bundle["follow_up_question_id"] and body.value > 0:
                inserted = db.execute("INSERT OR IGNORE INTO flags VALUES (?,?)", (session_id, time)).rowcount
                if inserted:
                    bump_summary(db, user, time)
            db.execute("UPDATE sessions SET revision=revision+1, updated_at=? WHERE id=?", (time, session_id))
            return view(db, owned(db, session_id, user))

    def transition(session_id, action, body, user):
        allowed = {"pause": ({"in_progress"}, "paused"), "resume": ({"paused"}, "in_progress"),
                   "cancel": ({"in_progress", "paused"}, "cancelled")}
        sources, target = allowed[action]
        with store.connect(write=True) as db:
            row = owned(db, session_id, user)
            check_revision(row, body.expected_revision)
            if row["status"] not in sources:
                fail(409, "invalid_state", "This transition is not allowed.")
            db.execute("UPDATE sessions SET status=?, revision=revision+1, updated_at=? WHERE id=?", (target, timestamp(), session_id))
            return view(db, owned(db, session_id, user))

    @app.post(PREFIX + "/sessions/{session_id}/pause", response_model=Session, responses=errors)
    def pause(session_id: str, body: Revision, user=Depends(identity)):
        return transition(session_id, "pause", body, user)

    @app.post(PREFIX + "/sessions/{session_id}/resume", response_model=Session, responses=errors)
    def resume(session_id: str, body: Revision, user=Depends(identity)):
        return transition(session_id, "resume", body, user)

    @app.post(PREFIX + "/sessions/{session_id}/cancel", response_model=Session, responses=errors)
    def cancel(session_id: str, body: Revision, user=Depends(identity)):
        return transition(session_id, "cancel", body, user)

    @app.post(PREFIX + "/sessions/{session_id}/complete", response_model=Result, responses=errors)
    def complete(session_id: str, body: Revision, user=Depends(identity), idempotency_key: str = Header(min_length=1, max_length=128)):
        operation = "complete:" + session_id
        with store.connect(write=True) as db:
            row = owned(db, session_id, user)
            old = replay(db, user, operation, idempotency_key, body.model_dump())
            if old is not None:
                return old
            check_revision(row, body.expected_revision)
            if row["status"] != "in_progress":
                fail(409, "invalid_state", "Only in-progress assessments may be completed.")
            state = view(db, row)
            bundle = state["assessment"]
            try:
                scoring = score(bundle, state["responses"])
            except ValueError:
                fail(422, "incomplete_assessment", "All questions require valid answers before scoring.")
            time = timestamp()
            result = {"result_id": str(uuid4()), "session_id": session_id, "assessment_code": row["code"],
                      "assessment_version": row["version"], **scoring, "completed_at": time,
                      "notice": "This screening score is not a diagnosis or an immediate-risk determination."}
            db.execute("INSERT INTO results VALUES (?,?)", (session_id, json.dumps(result)))
            db.execute("UPDATE sessions SET status='scored', revision=revision+1, updated_at=? WHERE id=?", (time, session_id))
            bump_summary(db, user, time)
            remember(db, user, operation, idempotency_key, body.model_dump(), result)
            return result

    @app.get(PREFIX + "/sessions/{session_id}/result", response_model=Result, responses=errors)
    def result(session_id: str, user=Depends(identity)):
        with store.connect() as db:
            owned(db, session_id, user)
            row = db.execute("SELECT payload FROM results WHERE session_id=?", (session_id,)).fetchone()
            if row is None:
                fail(409, "not_scored", "No completed score exists for this session.")
            return json.loads(row["payload"])

    def results_for(db, user):
        return [json.loads(r[0]) for r in db.execute("SELECT r.payload FROM results r JOIN sessions s ON r.session_id=s.id WHERE s.astronaut_id=? ORDER BY s.updated_at DESC,s.id", (user,)).fetchall()]

    @app.get(PREFIX + "/results", response_model=list[Result], responses=errors)
    def results(user=Depends(identity)):
        with store.connect() as db:
            return results_for(db, user)

    @app.get(PREFIX + "/astronauts/{astronaut_id}/risk-summary", response_model=RiskSummary, responses=errors)
    def summary(astronaut_id: str, user=Depends(identity)):
        if astronaut_id != user:
            fail(403, "forbidden", "Only your own summary is accessible.")
        with store.connect() as db:
            state = db.execute("SELECT * FROM summaries WHERE astronaut_id=?", (user,)).fetchone()
            # One latest result per instrument, not a growing transcript/history export.
            latest = {}
            for r in results_for(db, user):
                latest.setdefault(r["assessment_code"], r)
            records = list(latest.values())
            flag = db.execute("SELECT MAX(f.created_at) FROM flags f JOIN sessions s ON f.session_id=s.id WHERE s.astronaut_id=?", (user,)).fetchone()[0]
            observed = max([r["completed_at"] for r in records] + ([flag] if flag else []), default=None)
            cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            stale = any(datetime.fromisoformat(r["completed_at"].replace("Z", "+00:00")) < cutoff for r in records)
            availability = "not_assessed" if not records else "stale" if stale else "available"
            return {"schema_version": "1.0.0", "summary_id": "wellbeing:" + user,
                    "revision": state["revision"] if state else 0, "astronaut_id": user,
                    "availability": availability, "observed_at": observed,
                    "updated_at": state["updated_at"] if state else None,
                    "assessment_summaries": records,
                    "follow_up": follow_up(bool(flag), "PHQ9" in latest), "rule_version": RULE_VERSION}

    @app.post(PREFIX + "/assistant/messages", response_model=AssistantReply, responses=errors)
    def assistant(body: Message, user=Depends(identity)):
        # Typed intents only: no unrestricted free-text chat or invented text-risk classifier.
        with store.connect() as db:
            state = view(db, owned(db, body.session_id, user))
            if body.intent == "support":
                text = SUPPORT
            elif body.intent == "instructions":
                text = "Use your experience over the last two weeks. Select the fixed option that best matches it. You may pause and return later."
            elif body.intent == "question":
                if body.question_id not in {q["id"] for q in state["assessment"]["questions"]}:
                    fail(422, "invalid_question", "Select a question from this session.")
                text = "Read the question as written and consider the last two weeks. Choose your own response; this assistant cannot select an answer for you."
            else:
                row = db.execute("SELECT payload FROM results WHERE session_id=?", (body.session_id,)).fetchone()
                if row is None:
                    fail(409, "not_scored", "Complete the assessment before requesting a result explanation.")
                r = json.loads(row["payload"])
                text = f"Your recorded score is {r['total_score']} of {r['maximum_score']} ({r['interpretation'].replace('_', ' ')}). This is a screening result, not a diagnosis. Discuss concerns with a qualified support person."
            return {"mode": "static", "model_available": False, "text": text, "follow_up": state["follow_up"]}

    @app.get("/health")
    def health():
        with store.connect() as db:
            db.execute("SELECT 1 FROM sessions LIMIT 1")
        return {"status": "ok", "storage": "available", "assistant_mode": "static", "model_available": False,
                "identity": "checked_on_each_authenticated_request"}

    return app
