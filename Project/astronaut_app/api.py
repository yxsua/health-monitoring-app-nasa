"""Astronaut profiles and local bearer-session authentication."""
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PREFIX = "/api/v1"
ITERATIONS = 600_000
SESSION_HOURS = 24
bearer = HTTPBearer(auto_error=False)


def now():
    return datetime.now(timezone.utc)


def timestamp(value):
    return value.isoformat().replace("+00:00", "Z")


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class Credentials(Input):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        return value.lower()


class PersonalDetails(Input):
    age_years: int | None = Field(default=None, ge=0, le=120)
    birthdate: date | None = None
    gender: str | None = Field(default=None, max_length=80)
    pronouns: str | None = Field(default=None, max_length=80)
    blood_type: str | None = Field(default=None, pattern=r"^(A|B|AB|O)[+-]$")
    allergies: str | None = Field(default=None, max_length=2000)
    medical_conditions: str | None = Field(default=None, max_length=2000)
    medications: str | None = Field(default=None, max_length=2000)
    emergency_contact_name: str | None = Field(default=None, max_length=100)
    emergency_contact_relationship: str | None = Field(default=None, max_length=80)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)

    @field_validator("gender", "pronouns", "allergies", "medical_conditions", "medications",
                     "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone")
    @classmethod
    def clean_optional_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("birthdate")
    @classmethod
    def valid_birthdate(cls, value):
        if value is not None and value >= now().date():
            raise ValueError("Birthdate must be in the past")
        if value is not None and (now().date() - value).days > 120 * 366:
            raise ValueError("Birthdate is outside the supported range")
        return value

    @model_validator(mode="after")
    def one_age_representation(self):
        if self.age_years is not None and self.birthdate is not None:
            raise ValueError("Provide age or birthdate, not both")
        return self


class Registration(Credentials, PersonalDetails):
    display_name: str = Field(min_length=1, max_length=100)
    mission: str | None = Field(default=None, max_length=100)

    @field_validator("display_name", "mission")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value


class ProfileUpdate(PersonalDetails):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    mission: str | None = Field(default=None, max_length=100)

    @field_validator("display_name", "mission")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Must not be blank")
        return value


class Profile(BaseModel):
    astronaut_id: str
    username: str
    display_name: str
    mission: str | None
    age_years: int | None
    birthdate: date | None
    gender: str | None
    pronouns: str | None
    blood_type: str | None
    allergies: str | None
    medical_conditions: str | None
    medications: str | None
    emergency_contact_name: str | None
    emergency_contact_relationship: str | None
    emergency_contact_phone: str | None
    created_at: str
    updated_at: str


class LoginResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    astronaut: Profile


class SessionIdentity(BaseModel):
    astronaut_id: str
    username: str
    expires_at: str


class CrewRosterMember(BaseModel):
    astronaut_id: str
    display_name: str
    mission: str | None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def fail(status, code, message):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def profile(row):
    result = {key: row[key] for key in Profile.model_fields}
    if result["birthdate"]:
        born = date.fromisoformat(result["birthdate"])
        today = now().date()
        result["age_years"] = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return result


def create_app(db_path=None):
    path = Path(db_path or os.environ.get("ASTRONAUT_DB_PATH", Path(__file__).parent / "data" / "astronauts.db"))
    path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def database():
        connection = sqlite3.connect(path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            with connection:
                yield connection
        finally:
            connection.close()

    with database() as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version > 2:
            raise RuntimeError("Unsupported astronaut database version")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS astronauts (
                astronaut_id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                mission TEXT,
                age_years INTEGER CHECK(age_years BETWEEN 0 AND 120),
                birthdate TEXT,
                gender TEXT,
                pronouns TEXT,
                blood_type TEXT,
                allergies TEXT,
                medical_conditions TEXT,
                medications TEXT,
                emergency_contact_name TEXT,
                emergency_contact_relationship TEXT,
                emergency_contact_phone TEXT,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                astronaut_id TEXT NOT NULL REFERENCES astronauts(astronaut_id),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_astronaut ON sessions(astronaut_id);
        """)
        existing = {row[1] for row in db.execute("PRAGMA table_info(astronauts)")}
        migrations = {
            "age_years": "INTEGER CHECK(age_years BETWEEN 0 AND 120)",
            "birthdate": "TEXT", "gender": "TEXT", "pronouns": "TEXT", "blood_type": "TEXT",
            "allergies": "TEXT", "medical_conditions": "TEXT", "medications": "TEXT",
            "emergency_contact_name": "TEXT", "emergency_contact_relationship": "TEXT",
            "emergency_contact_phone": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in existing:
                db.execute(f"ALTER TABLE astronauts ADD COLUMN {column} {definition}")
        db.execute("PRAGMA user_version=2")

    app = FastAPI(title="Astronaut Profiles and Authentication", version="1.1.0",
                  docs_url=None, redoc_url=None,
                  description="Local hackathon identity service with optional user-owned profile and health details. Register, log in, and use the returned bearer token to access your profile. Other local services can validate that token with GET /api/v1/auth/session. No cloud dependency.")
    app.state.db_path = path
    origins = [s.strip() for s in os.environ.get("ASTRONAUT_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if s.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "PATCH"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": "http_error", "message": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo submitted passwords in validation responses.
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": "Invalid request fields."}})

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        return JSONResponse(status_code=503, content={"error": {"code": "storage_unavailable", "message": "Local identity storage is unavailable."}})

    def authenticated(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None or credentials.scheme.lower() != "bearer":
            fail(401, "unauthorized", "A valid bearer session is required.")
        digest = token_hash(credentials.credentials)
        with database() as db:
            row = db.execute("SELECT a.*, s.expires_at FROM sessions s JOIN astronauts a USING (astronaut_id) WHERE s.token_hash=?", (digest,)).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) <= now():
            fail(401, "unauthorized", "Session is invalid or expired.")
        return row, digest

    common = {422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}
    protected = {**common, 401: {"model": ErrorResponse}}

    @app.post(PREFIX + "/auth/register", status_code=201, response_model=Profile,
              responses={**common, 409: {"model": ErrorResponse}}, tags=["Authentication"])
    def register(body: Registration):
        salt = secrets.token_hex(16)
        hashed = password_hash(body.password, salt)
        identity, created = str(uuid4()), timestamp(now())
        try:
            with database() as db:
                db.execute("""INSERT INTO astronauts (
                    astronaut_id,username,display_name,mission,age_years,birthdate,gender,pronouns,blood_type,
                    allergies,medical_conditions,medications,emergency_contact_name,emergency_contact_relationship,
                    emergency_contact_phone,password_salt,password_hash,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (identity, body.username, body.display_name, body.mission, body.age_years,
                            body.birthdate.isoformat() if body.birthdate else None, body.gender, body.pronouns,
                            body.blood_type, body.allergies, body.medical_conditions, body.medications,
                            body.emergency_contact_name, body.emergency_contact_relationship,
                            body.emergency_contact_phone, salt, hashed, created, created))
                row = db.execute("SELECT * FROM astronauts WHERE astronaut_id=?", (identity,)).fetchone()
        except sqlite3.IntegrityError:
            fail(409, "username_taken", "Username is already registered.")
        return profile(row)

    @app.post(PREFIX + "/auth/login", response_model=LoginResult,
              responses=protected, tags=["Authentication"])
    def login(body: Credentials):
        with database() as db:
            row = db.execute("SELECT * FROM astronauts WHERE username=?", (body.username,)).fetchone()
        # Always perform the password derivation, including unknown usernames.
        calculated = password_hash(body.password, row["password_salt"] if row else "00" * 16)
        if row is None or not hmac.compare_digest(calculated, row["password_hash"]):
            fail(401, "invalid_credentials", "Invalid username or password.")
        token = secrets.token_urlsafe(32)
        created = now()
        expires = timestamp(created + timedelta(hours=SESSION_HOURS))
        with database() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?,?)", (token_hash(token), row["astronaut_id"], timestamp(created), expires))
        return {"access_token": token, "token_type": "bearer", "expires_at": expires, "astronaut": profile(row)}

    @app.get(PREFIX + "/auth/session", response_model=SessionIdentity, responses=protected, tags=["Authentication"])
    def session(auth=Depends(authenticated)):
        row, _ = auth
        return {"astronaut_id": row["astronaut_id"], "username": row["username"], "expires_at": row["expires_at"]}

    @app.post(PREFIX + "/auth/logout", status_code=204, responses=protected, tags=["Authentication"])
    def logout(auth=Depends(authenticated)):
        with database() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (auth[1],))

    @app.get(PREFIX + "/astronauts/me", response_model=Profile, responses=protected, tags=["Profiles"])
    def me(auth=Depends(authenticated)):
        return profile(auth[0])

    @app.patch(PREFIX + "/astronauts/me", response_model=Profile, responses=protected, tags=["Profiles"])
    def update(body: ProfileUpdate, auth=Depends(authenticated)):
        changes = body.model_dump(exclude_unset=True)
        if not changes or ("display_name" in changes and changes["display_name"] is None):
            fail(422, "invalid_request", "Supply at least one profile field; display name cannot be null.")
        if changes.get("birthdate") is not None:
            changes["birthdate"] = changes["birthdate"].isoformat()
            changes["age_years"] = None
        elif changes.get("age_years") is not None:
            changes["birthdate"] = None
        changes["updated_at"] = timestamp(now())
        with database() as db:
            columns = ", ".join(f"{field}=?" for field in changes)  # Pydantic allowlist only
            db.execute(f"UPDATE astronauts SET {columns} WHERE astronaut_id=?", (*changes.values(), auth[0]["astronaut_id"]))
            row = db.execute("SELECT * FROM astronauts WHERE astronaut_id=?", (auth[0]["astronaut_id"],)).fetchone()
        return profile(row)

    @app.get(PREFIX + "/astronauts/crew", response_model=list[CrewRosterMember], responses=protected, tags=["Profiles"])
    def crew_roster(_auth=Depends(authenticated)):
        # The Earth-side simulated board needs only an identifier and display labels to
        # request synthetic telemetry. Never include private health or emergency fields.
        with database() as db:
            rows = db.execute("SELECT astronaut_id,display_name,mission FROM astronauts ORDER BY created_at,display_name").fetchall()
        return [dict(row) for row in rows]

    @app.get("/health", tags=["Operations"])
    def health():
        with database() as db:
            db.execute("SELECT 1 FROM astronauts LIMIT 1")
        return {"status": "ok"}

    return app


# Use uvicorn's --factory flag: importing this module does not create a database.
