# Earth-side mission-control dashboard

This directory contains the static Nginx frontend served separately from the astronaut-facing AstraHealth web app. In Docker Compose it is available at `http://127.0.0.1:8081` by default. It is a receiver-side simulation, not a NASA ground system and not a real spacecraft communications link.

## What it does

- Authenticates through the astronaut profile service and displays the signed-in account's received message archive.
- Shows simulated contact-window status and delivery receipts from the mission-control API.
- Polls the registered crew roster and each crew member's simulator inputs every three seconds while the console is active.
- Presents crew-wide statistics separately from individual crew metric pages, including per-person metric history charts and configured reference baselines.
- Uses the simulator endpoint through the dashboard's same-origin Nginx proxy. The UI does not call the APIs directly from the browser across origins.
- Rotates the login background through `video.mp4`, `video-2.mp4`, and `video-3.mp4`. Keep all three media files in this folder when packaging the dashboard.

## Run with Docker Compose

Run from the repository root:

```sh
docker compose up -d --build mission-control-dashboard
docker compose ps mission-control-dashboard
```

The dashboard requires the `mission-control`, `simulator`, and `astronaut` services on the Compose network. Compose starts the dashboard after mission-control is healthy and simulator has started; identity is used by the dashboard's proxy. To start the complete demo instead, use `docker compose up -d --build` as described in the root README.

Set `MISSION_CONTROL_DASHBOARD_PORT` in the root `.env` to change the host port. The Compose port is bound to `127.0.0.1` for local use. To serve it to other computers, proxy the chosen host port through a trusted TLS reverse proxy or VPN and configure the host firewall. Do not remove the API proxy locations from `nginx.conf`: the browser expects same-origin `/api/v1/` routes.

## Local static development

The easiest local run uses the Compose container above. For UI-only work, any static HTTP server can serve this folder, but authenticated data calls require a same-origin proxy. Configure the proxy routes from `nginx.conf` to local APIs:

| Path prefix | Local upstream |
| --- | --- |
| `/api/v1/mission-control/` | `http://127.0.0.1:8003/api/v1/mission-control/` |
| `/api/v1/simulation/` | `http://127.0.0.1:8000/api/v1/simulation/` |
| Remaining `/api/v1/` | `http://127.0.0.1:8001/api/v1/` |

Start the APIs using their component guides, then serve the page at a local web origin through that proxy. Opening `index.html` as a `file://` URL will not work because the page uses fetch, session storage, and same-origin API routes.

## Files

- `index.html`: login, console navigation and overview/crew/messages page containers.
- `app.js`: login state, API requests, telemetry polling, chart rendering and message views.
- `styles.css`: responsive dashboard and login styles.
- `nginx.conf`: static file server and reverse-proxy routes used by the container.
- `Dockerfile`: packages this frontend into the Nginx image.
- `video*.mp4`: login background playlist assets.

## Data and security notes

The receiver archive is account-scoped. Crew telemetry is generated simulation data associated with the registered roster; it is not pulled from profile medical details. Session state is held in the browser session. The dashboard's HTTP origin should be protected by a trusted network or TLS proxy when used beyond a local demo. Do not treat the contact status or receipt timestamp as a real communications acknowledgment.
