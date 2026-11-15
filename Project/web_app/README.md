# AstraHealth frontend

The dashboard polls simulated measurements every three seconds while visible. Metric sparklines use the latest eight samples and take their risk color from backend rule evidence. Rule, anomaly, and wellbeing follow-up alerts appear at the upper right with a three-minute cooldown per alert type.

Local React + TypeScript console for astronaut profiles, simulated measurements and the structured wellbeing assessment service.

## Start locally

Install Node.js 22+ and Python dependencies for the three local services. From the repository root, start each API in its own terminal:

```powershell
Project/astronaut_app/.venv/Scripts/python.exe -m uvicorn Project.astronaut_app.api:create_app --factory --host 127.0.0.1 --port 8001
Project/simulated_inputs_app/.venv/Scripts/python.exe -m uvicorn Project.simulated_inputs_app.api:app --host 127.0.0.1 --port 8000
Project/chatbot_app/.venv/Scripts/python.exe -m uvicorn Project.chatbot_app.api:create_app --factory --host 127.0.0.1 --port 8002
```

Then run the frontend from `Project/web_app`:

```powershell
npm install
npm run dev
```

Open the local Vite address shown in the terminal (normally `http://127.0.0.1:5173`). Register a local profile, then sign in. The bearer token remains in memory; after a page reload, sign in again and the assessment service will reload saved sessions.

Vite proxies identity routes to port 8001, chatbot routes to 8002, and simulator routes to 8000. Production hosting needs the equivalent same-origin reverse proxy for these route prefixes. Browser clients do not call the services cross-origin.

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
- The dashboard only renders the assessment service's availability, results and follow-up status. It does not infer diagnoses, severity or risk.
- Static assistant actions are buttons backed by typed service intents. There is no free-text chatbot.
- This prototype is a screening demonstration, not a clinical diagnosis or astronaut fitness assessment.

See [`docs/design-sheet.md`](docs/design-sheet.md) for the color, type, spacing, interaction and responsive layout decisions.
