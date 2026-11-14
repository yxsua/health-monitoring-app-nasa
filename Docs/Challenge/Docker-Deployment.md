# Docker deployment

## Start the stack

From the repository root, build and start the four containers:

```powershell
docker compose up --build -d
docker compose ps
```

The frontend is available at <http://127.0.0.1:8080>. To use another port, set `WEB_PORT`; to bind on another host interface, set `WEB_BIND_ADDRESS`. For a public deployment, keep TLS and public ingress at an edge proxy and configure the bind address for that host.

Follow startup and health state with:

```powershell
docker compose logs -f web astronaut simulator chatbot
docker compose ps
```

Stop the services with `docker compose down`. Named data volumes remain. `docker compose down -v` removes the persisted profile and assessment databases; use it only when those local records should be deleted.

## Service layout

| Compose service | Container port | Host published | Data |
| --- | ---: | --- | --- |
| `web` | 8080 | Configurable, default 127.0.0.1:8080 | Static frontend and reverse proxy |
| `astronaut` | 8001 | No | `astronaut-data` volume at `/data` |
| `simulator` | 8000 | No | Process memory; fixture sequence resets on container restart |
| `chatbot` | 8002 | No | `chatbot-data` volume at `/data` |

Nginx serves the Vite static export and proxies `/api/v1/chatbot/`, `/api/v1/simulation/`, and remaining `/api/v1/` routes to the respective internal APIs. The APIs are not bound to host ports. The browser therefore uses same-origin paths and does not need CORS exceptions.

Compose waits for the identity API's database health check before starting the chatbot, and for identity/chatbot health before starting the web container. The simulator starts independently. This uses Compose's health-aware `depends_on` behavior; it controls initial startup, while container restart policies handle process exit.

All Python containers use one Uvicorn worker: the simulator keeps per-subject request sequence state in process memory, and each SQLite-backed service uses local SQLite storage. The SQLite data survives container recreation through named volumes. The Dockerfiles run application processes as a non-root user, and containers use read-only root filesystems with only required writable paths.

## Configuration and limits

- `WEB_PORT` defaults to `8080`.
- `WEB_BIND_ADDRESS` defaults to `127.0.0.1` so the port is local to the host until intentionally exposed.
- No cloud credentials or external services are required by the application runtime.
- Deploy behind HTTPS before using outside a trusted local environment. This stack does not configure certificates, backups, database replication, or external secret management.
- Back up the `astronaut-data` and `chatbot-data` Docker volumes before removing or replacing the Docker host.
