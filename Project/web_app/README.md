# AstraHealth frontend

The dashboard polls simulated measurements every three seconds while visible. Metric sparklines use the latest eight samples and take their risk color from backend rule evidence. Rule, anomaly, and wellbeing follow-up alerts appear at the upper right with a three-minute cooldown per alert type.

Local React + TypeScript console for astronaut profiles, simulated measurements and the structured wellbeing assessment service.

## Start locally

Install Node.js 22+ and the Python dependencies for the local APIs. From the repository root, start each API in its own terminal (the astronaut service must be available before chatbot and mission-control requests):

```powershell
Project/astronaut_app/.venv/Scripts/python.exe -m uvicorn Project.astronaut_app.api:create_app --factory --host 127.0.0.1 --port 8001
Project/simulated_inputs_app/.venv/Scripts/python.exe -m uvicorn Project.simulated_inputs_app.api:app --host 127.0.0.1 --port 8000
Project/chatbot_app/.venv/Scripts/python.exe -m uvicorn Project.chatbot_app.api:create_app --factory --host 127.0.0.1 --port 8002
Project/mission_control_app/.venv/Scripts/python.exe -m uvicorn Project.mission_control_app.api:create_app --factory --host 127.0.0.1 --port 8003
```

Then run the frontend from `Project/web_app`:

```powershell
npm ci
npm run dev
```

Open the local Vite address shown in the terminal (normally `http://127.0.0.1:5173`). Register a local profile, then sign in. The bearer token remains in memory; after a page reload, sign in again and the assessment service will reload saved sessions.

Vite proxies identity routes to port 8001, chatbot routes to 8002, simulator routes to 8000, and mission-control routes to 8003. Production hosting needs the equivalent same-origin reverse proxy for these route prefixes. Browser clients do not call the services cross-origin.

The `/mission-control` page is part of this app and lets the signed-in astronaut compose text updates or professional/additional-help requests for the simulated outbox. The Earth-side receiver is a separate static app/container at port 8081; see [its README](../mission_control_ui/README.md). A queued packet transfers only during the simulated contact window. No real person or emergency service is contacted.

## Contract updates

Chatbot TypeScript types and client are copied from `Project/chatbot_app/contracts/` into `src/generated/`. After the backend contract changes, run:

```powershell
npm run sync:chatbot-contracts
```

The sync task preserves the frontend's 401 session-expiration event handling. Do not edit generated files by hand.

## Data boundaries

- Simulator subjects `A01` and `AST-001` are fixture identities and are selected separately from the signed-in profile. The dashboard requests a new observation every three seconds while active and the browser tab is visible. Polling can be paused or resumed; requests do not overlap, and the recent trend keeps up to eight returned samples in browser memory.
- The dashboard can select the simulator run's active scenario (`normal`, `solar_event`, `high_co2`, or `prolonged_isolation`). The selected scenario is returned with each sample and analysis result.
- Each observation is submitted to the simulator analysis endpoint by `record_id`. The response keeps deterministic rule alerts, Isolation Forest status, and LSTM forecast status distinct. The simulator and analysis service run as one container; the SQLite analysis history persists in the `simulator-data` volume. Model artifacts are optional and are not included in the repository; enable the optional ML runtime and add reviewed artifacts under `Project/simulated_inputs_app/model_artifacts` to load them.
- Null or missing simulator values display as unavailable, not zero.
- The dashboard renders the assessment service's availability, results, follow-up status, and opt-in local conversation feature. Conversation is disabled unless an operator configures and enables a local model. It does not read assessment answers or check-in history; only explicitly selected topics may be sent to recommendation evaluation.
- Recommendations are produced by the deterministic library in `Project/recommendations_app` through the chatbot API. They can use structured assessment/check-in state, explicit dashboard analysis, and only the conversation topics a user explicitly chose to share. Transcripts are not accepted or stored by recommendation evaluation.
- This prototype is a screening demonstration, not a clinical diagnosis or astronaut fitness assessment.

See [`docs/design-sheet.md`](docs/design-sheet.md) for the color, type, spacing, interaction and responsive layout decisions. For the full Compose topology and run-on-another-machine steps, see the [repository README](../../README.md).
