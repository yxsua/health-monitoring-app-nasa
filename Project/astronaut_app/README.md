# Astronaut profiles and authentication

Independent local FastAPI service for the hackathon. Stores profiles and sessions in SQLite. Other services use its stable `astronaut_id`; they do not share its database. Profile medical and emergency details are optional and returned only to the authenticated profile owner.

## Start

From the repository root with Python 3.10+:

```powershell
python -m venv Project/astronaut_app/.venv
Project/astronaut_app/.venv/Scripts/python.exe -m pip install -r Project/astronaut_app/requirements-dev.txt
Project/astronaut_app/.venv/Scripts/python.exe -m uvicorn Project.astronaut_app.api:create_app --factory --host 127.0.0.1 --port 8001
```

The existing simulator virtual environment also has the required dependencies and can run the same command during the hackathon. Runtime works without internet. `/openapi.json` serves the API contract; hosted documentation assets are disabled. The default SQLite file is `Project/astronaut_app/data/astronauts.db`. Set `ASTRONAUT_DB_PATH` to use another local path. Schema initialization is idempotent and upgrades version 1 databases to version 2 without changing existing account credentials or IDs.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | Create a profile; returns 201 and a server-generated UUID. |
| POST | `/api/v1/auth/login` | Return a 24-hour opaque bearer token and profile. |
| GET | `/api/v1/auth/session` | Validate a bearer token and return identity plus expiry. |
| POST | `/api/v1/auth/logout` | Revoke the current token; returns 204. |
| GET | `/api/v1/astronauts/me` | Read the authenticated astronaut's profile. |
| GET | `/api/v1/astronauts/crew` | Return the authenticated demo crew roster with astronaut ID, display name, and mission only. |
| PATCH | `/api/v1/astronauts/me` | Change display name and/or mission. |
| GET | `/health` | Check local database availability. |

Registration body:

```json
{
  "username": "astronaut.one",
  "password": "DemoPassword123!",
  "display_name": "Astronaut One",
  "mission": "Mars Demo"
}
```

Login uses only `username` and `password`. Usernames are case-insensitive, 3–40 ASCII letters, numbers, dots, hyphens or underscores. Passwords are 8–128 characters. Profile updates cannot change the UUID, username, or password. `mission: null` clears the mission; omitted fields remain unchanged. Registration and profile updates accept optional age or birthdate, gender, pronouns, blood type, allergies, medical conditions, medications, and emergency contact details. Age and birthdate are mutually exclusive: when a birthdate is provided, the API calculates the current age; users may provide age instead to avoid sharing an exact birthdate. All health and emergency fields can be left blank or cleared.

These optional fields are sensitive profile data. Share only information appropriate for this local demo. The API does not use them to make diagnoses or medical recommendations, and an emergency contact is not notified by the service. Configure appropriate database access, backups, and retention before using real medical data.

Authenticated requests send `Authorization: Bearer <access_token>`. Responses never expose password hashes. Passwords use salted PBKDF2-HMAC-SHA256; only SHA-256 digests of random session tokens are stored. Sessions and profiles survive restarts. Logout invalidates one session; other independently issued sessions remain valid. Expired sessions return 401.

The crew roster requires a valid session and returns only the fields used to label synthetic mission telemetry. It does not return profile health details or emergency contacts.

Errors use `{"error":{"code":"...","message":"..."}}`: 401 invalid credentials/session, 409 duplicate username, 422 invalid input, 503 unavailable storage. Validation errors do not echo submitted passwords. Responses use `Cache-Control: no-store`.

## Frontend and chatbot integration

1. Register once, then log in. Keep the returned token in frontend memory for the demo.
2. Use the token to retrieve `/api/v1/astronauts/me` and show the profile.
3. Send the same bearer token with chatbot requests. The chatbot validates it by calling this service's `/api/v1/auth/session` and uses the returned UUID for session ownership. Never trust a client-supplied astronaut ID alone.
4. On 401, clear the frontend token and show login. If the identity service is unavailable, the chatbot should return a retryable unavailable error rather than accepting an unverified identity.
5. Logout calls `/api/v1/auth/logout` and clears frontend state. Chatbot authorization must revalidate tokens so revocation is respected.

Default CORS origins are `http://localhost:5173` and `http://127.0.0.1:5173`. Override with the comma-separated `ASTRONAUT_CORS_ORIGINS` variable. CORS is not authorization.

The simulator's `A01` and `AST-001` are fixture IDs, not registered profiles. Mapping them to new UUIDs is a later integration task; registration does not modify simulator runs. No chatbot or frontend implementation is included here.

## Hackathon scope

Open local registration, profile ownership, login/logout, persistent sessions, and minimal profile fields are implemented. Consent workflows, retention rules, disclosure policies, hardware budgeting, and model provisioning are not prerequisites. No seeded credentials, professional roles, password recovery, refresh tokens, or account administration are included. Use loopback for the demo; rate limiting and deployment transport configuration remain future work.

## Tests

```powershell
Project/astronaut_app/.venv/Scripts/python.exe -m unittest Project.astronaut_app.test_api -v
```

Tests use temporary databases and cover identity ownership, token revocation/expiry, restart persistence, hashed storage, input errors, CORS, and the generated OpenAPI contract.
