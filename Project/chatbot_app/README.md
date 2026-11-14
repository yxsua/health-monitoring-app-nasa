# Astronaut assessment chatbot — backend MVP

Independent FastAPI service on port 8002. It authenticates against `astronaut_app`, owns a separate SQLite database, and never calls the simulator. Runs offline after installing dependencies.

Implemented: versioned English PHQ-9/GAD-7 scored items, persistent sessions and answers, pause/resume/cancel, deterministic scoring, immediate follow-up flags, result history, read-only risk summaries, and static explanations. The React UI and a trained conversational model are not implemented in this increment.

## Run from the repository root

```powershell
python -m venv Project/chatbot_app/.venv
Project/chatbot_app/.venv/Scripts/python.exe -m pip install -r Project/chatbot_app/requirements-dev.txt
Project/chatbot_app/.venv/Scripts/python.exe -m uvicorn Project.chatbot_app.api:create_app --factory --host 127.0.0.1 --port 8002
```

The existing simulator virtual environment already has these dependencies and can run the same module. Start the astronaut service in another terminal on port 8001 using its README, then register/login there. Pass that bearer token with every protected chatbot request. Identity is revalidated on every request, so logout immediately removes access. Identity-service failure returns 503; it does not bypass authentication. `/health` checks local storage only and reports static-assistant mode, not identity readiness.

Configuration:

| Variable | Default |
| --- | --- |
| `CHATBOT_DB_PATH` | `Project/chatbot_app/data/chatbot.db` |
| `ASTRONAUT_SERVICE_URL` | `http://127.0.0.1:8001` |
| `CHATBOT_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |

Keep the identity URL on your trusted onboard/local service. No runtime CDN, model download, or cloud inference is used. Browser Swagger/ReDoc pages are disabled; `/openapi.json` remains available.

## API walkthrough

All paths below start with `/api/v1/chatbot`; requests carry `Authorization: Bearer <token>`.

1. `GET /assessments`: fetch fixed question text, response options, and `en-1.0.0` package version.
2. `POST /sessions`, with `Idempotency-Key: <unique-request-id>`:

   ```json
   {"assessment_code":"GAD7","assessment_version":"en-1.0.0"}
   ```

3. `PUT /sessions/{id}/responses/GAD7_Q1`:

   ```json
   {"expected_revision":0,"value":1}
   ```

   Use the returned revision for the next change. New answers must follow the backend's `current_question`; existing answers may be corrected before completion. Stale revisions return 409. On a lost answer response, reload the session before deciding whether to retry.

4. `POST /sessions/{id}/pause`, `/resume`, or `/cancel` with `{"expected_revision":n}`.
5. After every answer, `POST /sessions/{id}/complete` with `{"expected_revision":n}` and a new `Idempotency-Key`. Returns the stored result, commits score and state together, and rejects incomplete forms.
6. `GET /sessions/{id}/result`, `GET /results`, or `GET /sessions` to retrieve your result, history, or resumable sessions. Results are immutable.
7. `GET /astronauts/{your_uuid}/risk-summary` to integrate with the main dashboard. Another user's UUID returns 403.

Creation and completion retries with the same key/body replay the original response without duplicate records. A reused key with a different body returns 409. Replayed creation returns the original creation response; fetch the session to obtain its latest state. Identity checks always precede replay. Keys are scoped to astronaut and operation and stored persistently.

`POST /assistant/messages` accepts typed requests rather than unrestricted conversation:

```json
{"session_id":"<session-id>","intent":"instructions"}
```

Other intents: `question` (requires a valid `question_id`), `result` (requires a scored session), and `support`. Responses explicitly return `mode: "static"` and `model_available: false`. The endpoint has no assessment-write capability and does not accept free-form message text. This avoids presenting a nonexistent language model or text-risk classifier as working functionality. A future local adapter can expand this contract deliberately.

Errors follow the identity service envelope: `{"error":{"code":"...","message":"..."}}`. Responses use `Cache-Control: no-store`. No caller-supplied astronaut identity is accepted for session ownership.

## Risk summaries and follow-up behavior

- Latest completed result per instrument only; no individual responses or conversation content.
- Stable summary ID and persisted revision change only when a new result or follow-up flag is created. Reads do not mutate records or regenerate data.
- Before assessment, `availability` is `not_assessed`, not healthy. With no completed PHQ-9, absence of a follow-up flag is `unknown`; GAD-7 is not substituted as a safety assessment.
- A positive PHQ-9 ninth-item answer creates a flag immediately, before completion. A partial assessment never publishes a partial score.
- Flags remain visible after answer corrections, cancellation, newer low scores, or stale results. The hackathon scope has no resolution workflow; acknowledgment or zero answers must not erase flags.
- A result older than 14 days makes the summary `stale` (demo freshness policy, not a clinical schedule). Original result timestamps remain unchanged. A stale summary does not clear follow-up flags. `availability` can age without a data revision, so consumers must also inspect availability on each poll rather than deduplicating the entire display solely by revision.
- A user-scoped risk consumer forwards that user's bearer token. No unrestricted service credential is supplied in this MVP.
- Static support content does not claim that anyone has been contacted or that immediate danger was diagnosed. Do not infer safety from an absent flag.

## Content and scoring provenance

English scored items are packaged in `assessments.py`; the application bundle version is not an official instrument revision. The optional functional-impairment question is not included in this scored-item demo. No translated text or diagnostic algorithm is supplied.

PHQ-9 uses nine 0–3 responses, with interpretation boundaries 5/10/15/20; GAD-7 uses seven 0–3 responses with boundaries 5/10/15. These rules and public-domain reproduction permission are documented in the authors' [PHQ/GAD instruction manual](https://www.uab.edu/medicine/pcp-sci/images/SCIMS/PHQ-9_Instruction_Manual.pdf), pages 3, 5–8. GAD wording is from the [University of Washington AIMS form](https://aims.uw.edu/sites/default/files/GAD-7_English_0.pdf). Each new session stores its definition and rules, preserving historical interpretation across code changes. Increment the package version before changing wording or scoring.

The prototype is a screening demonstration, not a clinical diagnosis or a validated astronaut-fitness assessment. Synthetic examples live in `fixtures/scoring.json`.

## Contracts and verification

- `openapi.json`: generated from the actual FastAPI routes and models.
- `contracts/risk-summary.schema.json`: standalone JSON Schema for consumers.
- `contracts/types.ts`: generated TypeScript types.
- `contracts/client.ts`: typed browser client with no automatic write retries. Import it into the future React feature; keep the token in memory.

```powershell
Project/chatbot_app/.venv/Scripts/python.exe -m Project.chatbot_app.export_contract
Project/chatbot_app/.venv/Scripts/python.exe -m unittest Project.chatbot_app.test_api -v
```

Tests use temporary databases and the real astronaut service through an in-process HTTP transport. They cover scoring boundaries, invalid/incomplete responses, authorization and revoked tokens, concurrent writes, idempotency, restart recovery, follow-up persistence, summaries, and fallback behavior. No external network is required by the service or test cases.

Next increment: build the React chatbot panel using the exported client, including login handoff, question cards, pause/resume, result history, and dashboard summary polling. Local AI remains optional and is not required to demonstrate this backend.
