# Docker deployment and operations

The repository root [README](../../README.md) is the full installation guide for another host. This document summarizes the Compose deployment layout and operational details.

## Start and stop

From the repository root, copy `.env.example` to `.env`, then build and start the required services:

```sh
docker compose up -d --build
docker compose ps
```

The default browser addresses are `http://127.0.0.1:8080` for the astronaut-facing AstraHealth app and `http://127.0.0.1:8081` for the separate Earth-side dashboard. The mission-control API is published on `http://127.0.0.1:8003` for local development. Change host ports through the variables in `.env`.

```sh
docker compose logs -f web astronaut simulator chatbot mission-control mission-control-dashboard
docker compose down
```

`docker compose down` preserves named data volumes. `docker compose down -v` removes the persisted profiles, assessment/check-in records, simulator history, outbox/receiver state, and optional Ollama model cache.

## Services

| Compose service | Container port | Host published | Persistence |
| --- | ---: | --- | --- |
| `web` | 8080 | `${WEB_BIND_ADDRESS:-127.0.0.1}:${WEB_PORT:-8080}` | Static React build; no database. |
| `astronaut` | 8001 | Internal network only | `astronaut-data` at `/data`. |
| `simulator` | 8000 | Internal network only | `simulator-data` at `/data`; generation sequence/scenario are in memory. Model files are mounted from `Project/simulated_inputs_app/model_artifacts/`. |
| `chatbot` | 8002 | Internal network only | `chatbot-data` at `/data`. |
| `mission-control` | 8003 | `127.0.0.1:${MISSION_CONTROL_API_PORT:-8003}` | `mission-control-data` at `/data`. |
| `mission-control-dashboard` | 8080 | `127.0.0.1:${MISSION_CONTROL_DASHBOARD_PORT:-8081}` | Static Nginx content; no database. |
| `ollama` | 11434 | Internal network only, optional profile | `ollama-models` when the `local-model` profile is enabled. |

`web` proxies `/api/v1/chatbot/` to the chatbot, `/api/v1/simulation/` to the simulator, `/api/v1/mission-control/` to mission-control, and remaining `/api/v1/` requests to astronaut identity. The Earth dashboard has its own Nginx config and proxies mission-control, simulator, and identity requests over the Compose network. The browser uses same-origin requests.

Python services run one Uvicorn worker. The simulator relies on in-process scenario and sequence state; SQLite-backed services each have their own database and named volume. Images run as non-root users and use read-only root filesystems with temporary writable mounts.

## Configuration and remote access

Compose defaults bind the main app, mission-control API, and Earth dashboard to host loopback. This is suitable for a local demo. For other users, use a trusted VPN or put the web and dashboard ports behind a TLS reverse proxy with firewall controls. The Compose file does not configure public ingress, TLS certificates, backup schedules, external secret storage, or a production database. Avoid publishing internal API ports directly.

The main settings are documented in root `.env.example` and the root README: host ports, simulated contact cadence/capacity, mission-control retention, whether to install the ML runtime, and optional Ollama settings. The local conversational adapter is off by default. To use it, enable `CHATBOT_CONVERSATION_ENABLED`, set the model name and internal Ollama URL, then start with `docker compose --profile local-model up -d --build`. The model-init container downloads the model to the Ollama volume.

`INSTALL_ML_RUNTIME=false` makes a smaller rules-only simulator image. The Isolation Forest and LSTM outputs require compatible reviewed artifacts and manifest files mounted in `Project/simulated_inputs_app/model_artifacts/`; training instructions are in the simulator README. Training artifacts are not included in the repository.
