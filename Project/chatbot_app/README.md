# Astronaut assessment chatbot — backend MVP

Independent FastAPI service on port 8002. It authenticates against `astronaut_app`, owns a separate SQLite database, and never calls the simulator. Runs offline after installing dependencies.

Implemented: versioned English PHQ-9/GAD-7 scored items, persistent sessions and answers, pause/resume/cancel, deterministic scoring, immediate follow-up flags, result history, private daily mood/sleep check-ins, personal trend prompts, read-only risk summaries, static explanations, and an optional stateless Ollama conversation adapter.

## Run from the repository root

```powershell
python -m venv Project/chatbot_app/.venv
Project/chatbot_app/.venv/Scripts/python.exe -m pip install -r Project/chatbot_app/requirements-dev.txt
Project/chatbot_app/.venv/Scripts/python.exe -m uvicorn Project.chatbot_app.api:create_app --factory --host 127.0.0.1 --port 8002
```

The existing simulator virtual environment already has these dependencies and can run the same module. Start the astronaut service in another terminal on port 8001 using its README, then register/login there. Pass that bearer token with every protected chatbot request. Identity is revalidated on every request, so logout immediately removes access. Identity-service failure returns 503; it does not bypass authentication. `/health` checks local storage and configured assistant mode, not model readiness or identity readiness.

Configuration:

| Variable | Default |
| --- | --- |
| `CHATBOT_DB_PATH` | `Project/chatbot_app/data/chatbot.db` |
| `ASTRONAUT_SERVICE_URL` | `http://127.0.0.1:8001` |
| `CHATBOT_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` |
| `CHATBOT_LOCAL_MODEL_URL` | unset (local conversation disabled) |
| `CHATBOT_LOCAL_MODEL_NAME` | unset (local conversation disabled) |
| `CHATBOT_CONVERSATION_ENABLED` | `false` (explicit operator enablement required) |
| `CHATBOT_CONVERSATION_LANGUAGE` | `en` (`en` or `es`) |

Keep the identity and model URLs on trusted onboard/local services. No runtime CDN, model download, or cloud inference is used; an operator must provision a local model. Browser Swagger/ReDoc pages are disabled; `/openapi.json` remains available.

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
8. `GET /check-ins/today` to retrieve today's UTC check-in (or `check_in: null` before submission); `PUT /check-ins/today` to save or correct the daily values; `GET /check-ins?limit=7` to review recent entries; `GET /check-ins/trend` for a transparent, self-relative prompt state.
9. `POST /recommendations/evaluate` to combine the caller's latest structured assessment/check-in state with optional dashboard analysis and explicitly shared conversation topics. The request accepts no transcript and the endpoint persists no recommendation history. `source_scope` identifies profile, simulated-fixture, and user-confirmed-context recommendations independently; fixture readings are never joined to the signed-in astronaut's profile.

The daily self-check-in stores a 1–5 mood rating and sleep duration in hours for the last main sleep period. The first write uses `expected_revision: 0`; corrections use the returned revision. Only one entry is stored per astronaut per UTC date; same-day corrections increment its revision. Entries are kept separately from scored assessments and risk summaries. The values are descriptive self-reports, not a diagnosis or safety determination.

The trend prompt policy (`self-check-in-trend-1.0.0`) requires one entry on each of the latest 10 consecutive UTC days. It compares the first seven days with the most recent three and returns `check_in_suggested` only when both recent mean mood is at least 1 point lower and recent mean sleep is at least 1 hour lower than the personal baseline. A missing day returns `insufficient_data`; other complete windows return `no_pattern`. This transparent demo heuristic is not a validated or clinical threshold. It only suggests an optional conversation with a qualified support person. It does not create a risk flag, contact anyone, infer a condition, or establish safety. The API returns window means and policy version so the UI can explain the prompt.

Creation and completion retries with the same key/body replay the original response without duplicate records. A reused key with a different body returns 409. Replayed creation returns the original creation response; fetch the session to obtain its latest state. Identity checks always precede replay. Keys are scoped to astronaut and operation and stored persistently.

`POST /assistant/messages` accepts typed requests rather than unrestricted conversation:

```json
{"session_id":"<session-id>","intent":"instructions"}
```

Other intents: `question` (requires a valid `question_id`), `result` (requires a scored session), and `support`. Responses explicitly return `mode: "static"` and `model_available: false`. The endpoint has no assessment-write capability and does not accept free-form message text.

The separate optional conversation uses `GET /assistant/status` and `POST /assistant/conversation`. The latter requires `{"consent":true,"messages":[{"role":"user","content":"..."}]}` with at most 12 alternating turns, 1,200 characters per turn, and a user message last. It requires all three operator settings: `CHATBOT_CONVERSATION_ENABLED=true`, `CHATBOT_LOCAL_MODEL_URL`, and `CHATBOT_LOCAL_MODEL_NAME`; otherwise the API returns 503. The adapter calls the configured Ollama `/api/chat` endpoint with a 45-second hard timeout and allows one inference in flight per chatbot process. The pilot language is configured as English (`en`) by default, with Spanish (`es`) also supported. The UI shows which language is set.

Conversation-derived recommendation context is a separate opt-in. The UI lets the astronaut choose broad topics to share; it stores only those tags in per-profile browser session storage and submits them with explicit consent. Chat messages are not retained for, or forwarded to, the recommendation evaluator. The deterministic policy (`recommendations-demo-v1`) preserves rule severity, treats anomaly and forecast outputs as advisory, and labels simulated fixture recommendations distinctly. Its suggestions are informational and are not a diagnosis or treatment protocol. The existing `Project/recomendations_app` directory is a legacy standalone prototype and is not called by this integration because its action catalog and thresholds require domain review.

For a hardware-light CPU benchmark candidate, the root Compose file includes an opt-in `local-model` profile using Ollama and `llama3.2:3b`. Ollama lists this quantized model at approximately 2 GB and documents English and Spanish support; it carries Meta's Llama Community License, which the operator must review before use ([Ollama model card](https://ollama.com/library/llama3.2:3b)). The runtime image is approximately 3 GB, so budget about 5 GB for the initial image and weights, plus Docker overhead. Copy `.env.example` to `.env`, then run `docker compose --profile local-model up -d`; this pulls the Ollama runtime and model weights into the `ollama-models` volume. The profile is not enabled by default. After the model pull completes, collect latency with `docker compose exec chatbot python -m Project.chatbot_app.benchmark_local_model`. The harness warms the model, then runs 30 synthetic prompts in the selected language and prints timing only, never raw prompts or replies. Repeat with `CHATBOT_CONVERSATION_LANGUAGE=es` and `en` to measure both languages. The candidate is for local engineering evaluation only; the repo does not assert its conversational quality or mission approval.

The UI has a separate opt-in; conversation text stays in browser memory and is sent to the chatbot API with the user's bearer token. The chatbot service forwards only the conversation to the configured model endpoint; it does not persist transcripts, forward the bearer token to the model, send text to an external provider, attach check-ins or assessment results, or include text in summaries. Reloading or ending the conversation clears browser-held messages. Review the model host's own logging and retention settings before enabling it. An unavailable model returns 503 while check-ins remain available. The model is instructed not to diagnose, score, classify risk, prescribe treatment, or claim to contact anyone; human support guidance remains visible, and generated text is not used as a safety decision.

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

Deployment recommendation: use the existing single-node Docker Compose stack on an x86-64 Linux host for the prototype and a small, access-controlled pilot; keep it CPU-only and inside the mission network. The stack already provides persistent volumes and service health checks, and the UI currently binds to localhost by default. For remote pilot access, put it behind the mission's TLS reverse proxy/VPN and back up the persistent volumes. Agree on check-in retention and access policy before expanding beyond the pilot. Continue using UTC days until the mission's canonical time zone is specified. Before selecting a local conversational model or setting hardware limits, benchmark the complete service stack and agree on RAM, storage, language, and response-time targets.

Operational pilot gate: keep authenticated astronaut-only API access and the one-inference limit; keep transcript persistence off and verify the Ollama host does not retain prompts in its logs; configure only `en` or `es`; and benchmark on the target machine. The initial performance target is p95 reply latency at or below 20 seconds, with a 45-second request timeout. Review representative replies manually for language quality, unsafe advice, diagnosis claims, and false claims of escalation. Keep `CHATBOT_CONVERSATION_ENABLED=false` until model/license review and the on-target language, latency, and response review are complete. No hardware benchmark was run in this development workspace.
