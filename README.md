# AstraHealth

AstraHealth is a local-first astronaut health-monitoring demonstration. It combines an astronaut account and profile service, a simulated telemetry service with rule and optional ML analysis, a structured wellbeing assessment/chatbot service, an onboard mission-control outbox, and two browser dashboards. The Earth-side console simulates contact windows and message receipt; it does not send data to NASA or a real Earth endpoint.

This guide is the starting point for installing the project on another development computer or a demo host. Detailed component contracts and local run commands are linked in [Service and app guides](#service-and-app-guides).

## 1. Architecture

| Component | Compose service | Host address by default | Role |
| --- | --- | --- | --- |
| Main AstraHealth web app | `web` | `http://127.0.0.1:8080` | React/TypeScript dashboard, login, wellbeing, recommendations and mission-control screens; Nginx reverse proxy for APIs. |
| Astronaut identity | `astronaut` | Internal port `8001` | Registration, login, profiles and bearer sessions; SQLite data persists in `astronaut-data`. |
| Simulated inputs | `simulator` | Internal port `8000` | Scenario-driven telemetry, rule alerts, anomaly detection and next-step forecast; analysis history persists in `simulator-data`. |
| Assessment and conversational support | `chatbot` | Internal port `8002` | Structured assessments, check-ins, risk summaries and recommendation evaluation; SQLite data persists in `chatbot-data`. |
| Mission-control API | `mission-control` | `http://127.0.0.1:8003` | Authenticated outbox, contact-window simulator and local receiver; SQLite data persists in `mission-control-data`. |
| Earth-side dashboard | `mission-control-dashboard` | `http://127.0.0.1:8081` | Separate receiver login, inbound messages, crew-wide statistics and individual crew telemetry. |
| Optional local language model | `ollama` (profile `local-model`) | Internal port `11434` | Optional local chatbot conversation adapter. Disabled by default; it requires model download and suitable host resources. |

Compose places services on a private network. The main web container proxies browser API requests to the internal APIs. The Earth-side dashboard proxies its API requests to the mission-control, identity and simulator services. The account/profile, assessment and mission-control databases are separate; the simulator and Earth dashboard use synthetic readings.

## 2. Requirements for another machine

- Git (if cloning) and access to this repository.
- Docker Desktop with the Compose v2 plugin on Windows/macOS, or Docker Engine plus the Compose v2 plugin on Linux.
- Internet access for the first image build. Runtime does not require a third-party cloud service.
- For local source development: Python 3.12 and Node.js 22 or newer.
- Optional local chatbot conversation: extra RAM/storage for Ollama and the selected model; see [Local model profile](#optional-local-chatbot-model).

Use a recent 64-bit machine. The optional TensorFlow-backed simulator image is significantly larger than the rules-only configuration.

## 3. Run the full stack with Docker Compose

Copy or clone the complete repository to the target machine. Keep the repository directory structure intact: Docker build contexts and `COPY` instructions refer to paths under `Project/` and `Docs/`.

Open a terminal in the repository root, then create a local environment file from the committed template.

### Windows PowerShell

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

### macOS or Linux

```sh
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Wait until the services show `healthy` or `running`. Then open:

- Main astronaut dashboard: <http://127.0.0.1:8080>
- Earth-side mission-control dashboard: <http://127.0.0.1:8081>
- Mission-control API health: <http://127.0.0.1:8003/health>

Register an account in the main app and sign in. The Earth-side dashboard uses the same astronaut account for its receiver/message archive and reads the registered crew roster for simulated telemetry. The dashboard is deliberately on a different port and container from the main web app.

### Configure ports and behavior

Edit `.env` before starting Compose. All values are optional; the template lists the main settings and Compose defaults are shown here.

| Variable | Default | Purpose |
| --- | --- | --- |
| `WEB_BIND_ADDRESS` | `127.0.0.1` | Host interface for the main app. Keep loopback for a private local demo. |
| `WEB_PORT` | `8080` | Main app host port. |
| `MISSION_CONTROL_API_PORT` | `8003` | Mission-control API host port. |
| `MISSION_CONTROL_DASHBOARD_PORT` | `8081` | Earth-side dashboard host port. |
| `MISSION_CONTROL_CYCLE_SECONDS` | `60` | Simulated contact cycle. |
| `MISSION_CONTROL_WINDOW_SECONDS` | `20` | Simulated open-window duration. |
| `MISSION_CONTROL_WINDOW_CAPACITY_BYTES` | `4096` | Simulated capacity per window. |
| `MISSION_CONTROL_TRANSFER_RATE_BYTES_PER_SECOND` | `512` | Simulated transfer rate. |
| `MISSION_CONTROL_RETENTION_DAYS` | `30` | Retention for terminal outbox records. |
| `INSTALL_ML_RUNTIME` | `true` | Include simulator inference packages in its image; use `false` for a smaller rules-only image. |
| `CHATBOT_CONVERSATION_ENABLED` | `false` | Explicitly enable the optional local conversation adapter. |
| `CHATBOT_LOCAL_MODEL_URL` | `http://ollama:11434` | Ollama URL from inside the Compose network. |
| `CHATBOT_LOCAL_MODEL_NAME` | `llama3.2:3b` | Model tag used by the optional Ollama profile. |
| `CHATBOT_CONVERSATION_LANGUAGE` | `en` | Adapter response language (`en` or `es`). |

`MISSION_CONTROL_API_PORT` and `MISSION_CONTROL_DASHBOARD_PORT` are published on host loopback by the Compose file. `WEB_BIND_ADDRESS=0.0.0.0` only changes the main web binding. For access from other computers, put the web and Earth dashboard behind a trusted VPN or TLS reverse proxy, route the dashboard to the host's configured dashboard port, and configure firewall rules. Do not publish the internal identity, chatbot or simulator ports directly. This demo stack does not provide certificates, external secrets, backups, or production hardening.

### Optional local chatbot model

The conversation adapter is off by default. To start Ollama and download the configured model, enable the Compose profile and explicitly enable the adapter in `.env`:

```dotenv
CHATBOT_CONVERSATION_ENABLED=true
CHATBOT_LOCAL_MODEL_URL=http://ollama:11434
CHATBOT_LOCAL_MODEL_NAME=llama3.2:3b
```

Then run:

```sh
docker compose --profile local-model up -d --build
```

The one-time `ollama-model-init` container pulls the model into the persistent `ollama-models` volume. Model download size and inference speed depend on the model and host. The adapter is stateless and does not store conversation transcripts. Keep it disabled until the selected model has been reviewed and benchmarked on the target host.

## 4. Operate the stack

Run these commands from the repository root:

```sh
docker compose ps
docker compose logs -f web astronaut simulator chatbot mission-control mission-control-dashboard
docker compose restart web
docker compose down
```

`docker compose down` stops and removes containers while preserving named data volumes. To remove all demo accounts, assessments, outbox state, simulator history, and downloaded model data as well, run `docker compose down -v`. That permanently deletes those local volumes.

The simulator's active scenario and per-subject generation sequence are process-local and reset when its container restarts. Profiles, assessment/check-in data, mission-control records, and analysis history use persistent volumes. Generated ML model files are mounted read-only from `Project/simulated_inputs_app/model_artifacts/`; model artifacts are not distributed with this repository.

## 5. Run services directly for development

Docker Compose is the recommended way to run the integrated system. For source development, first create environments and install component dependencies. The following PowerShell commands assume the repo root is the current directory:

```powershell
python -m venv Project/astronaut_app/.venv
Project/astronaut_app/.venv/Scripts/python.exe -m pip install -r Project/astronaut_app/requirements-dev.txt

python -m venv Project/simulated_inputs_app/.venv
Project/simulated_inputs_app/.venv/Scripts/python.exe -m pip install -r Project/simulated_inputs_app/requirements-dev.txt

python -m venv Project/chatbot_app/.venv
Project/chatbot_app/.venv/Scripts/python.exe -m pip install -r Project/chatbot_app/requirements-dev.txt

python -m venv Project/mission_control_app/.venv
Project/mission_control_app/.venv/Scripts/python.exe -m pip install -r Project/mission_control_app/requirements.txt
```

Start each API in a separate terminal from the repository root:

```powershell
Project/astronaut_app/.venv/Scripts/python.exe -m uvicorn Project.astronaut_app.api:create_app --factory --host 127.0.0.1 --port 8001
Project/simulated_inputs_app/.venv/Scripts/python.exe -m uvicorn Project.simulated_inputs_app.api:app --host 127.0.0.1 --port 8000
Project/chatbot_app/.venv/Scripts/python.exe -m uvicorn Project.chatbot_app.api:create_app --factory --host 127.0.0.1 --port 8002
Project/mission_control_app/.venv/Scripts/python.exe -m uvicorn Project.mission_control_app.api:create_app --factory --host 127.0.0.1 --port 8003
```

In a fifth terminal, run the main frontend:

```powershell
Set-Location Project/web_app
npm ci
npm run dev
```

Open the Vite URL (normally <http://127.0.0.1:5173>). The frontend development proxy forwards identity, simulator, chatbot and mission-control calls to the local API ports. The Earth dashboard is a static Nginx app with a Compose-network API proxy; run it through Compose, or configure a local Nginx with the routes in `Project/mission_control_ui/nginx.conf` pointing to the local API ports.

On macOS/Linux, use `python3 -m venv <path>`, `<path>/bin/python -m pip ...`, and `<path>/bin/python -m uvicorn ...` in place of Windows `.venv/Scripts/python.exe` paths. In each app folder, use `npm ci` and `npm run dev` for the web app.

## 6. Service and app guides

- [Astronaut profiles and authentication](Project/astronaut_app/README.md)
- [Simulated inputs and ML analysis](Project/simulated_inputs_app/README.md)
- [Assessment and conversational support](Project/chatbot_app/README.md)
- [Mission-control outbox and receiver API](Project/mission_control_app/README.md)
- [Earth-side mission-control dashboard](Project/mission_control_ui/README.md)
- [Main web app](Project/web_app/README.md)
- [Recommendation engine library](Project/recommendations_app/README.md) — imported by the chatbot; it is not a separate container.
- [Legacy maintenance-rule prototype](Project/recomendations_app/README.md) — separate experimental code; it is not part of the deployed recommendation service.
- [Docker deployment notes](Docs/Challenge/Docker-Deployment.md)

## 7. Demo limitations

Telemetry, contact timing, message delivery, anomaly outputs and forecasts are simulated. The ML artifacts are optional and must be trained, reviewed and mounted before model output becomes available. Recommendations are informational and derive only from the sources explicitly provided to their evaluator. The assessments and check-ins are demonstrations and do not diagnose conditions, determine fitness, notify professionals, or replace onboard procedures.
