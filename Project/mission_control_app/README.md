# Mission Control outbox

Mission Control combines an authenticated, durable outbox with a deterministic local contact-window simulator and receiver. All transfer and receipt activity stays inside this application. No external network is used to send data to Earth.

## Contract

The versioned packet contract is `1.1.0` (existing `1.0.0` packets remain readable). FastAPI serves its OpenAPI document at `/openapi.json`; interactive docs are disabled. All `/api/v1/mission-control/*` routes require the astronaut service's bearer token. Ownership is derived from the validated session UUID, and every read or mutation is scoped to that UUID.

`POST /api/v1/mission-control/outbox` accepts an explicit, bounded allowlist rather than arbitrary dashboard state. It requires `consent: true` and an `Idempotency-Key` header (1–128 non-space characters).

```json
{
  "contract_version": "1.1.0",
  "consent": true,
  "source_scope": "simulated_fixture",
  "data": {
    "mission": "Expedition 74",
    "metrics": [
      {
        "field": "heart_rate",
        "value": 68,
        "unit": "bpm",
        "quality": "valid",
        "observed_at": "2026-11-15T12:00:00Z",
        "source_ref": "fixture-A01"
      }
    ],
    "alerts": []
  }
}
```

The onboard dashboard can also queue an explicitly approved, user-written message:

```json
{
  "contract_version": "1.1.0",
  "consent": true,
  "source_scope": "user_entered",
  "data": {
    "message": {
      "kind": "professional_help",
      "help_type": "medical",
      "text": "Please arrange a medical professional follow-up at the next available contact."
    }
  }
}
```

Message kinds are `text_update`, `professional_help`, and `additional_help`. Professional requests must select `medical`, `mental_health`, `technical`, or `other`; message text is limited to 2,000 characters. The application never copies chatbot conversation or assessment answers into a packet. A help request is only stored and simulated; it does not contact a real professional or emergency service.

Allowed metric fields and alert evidence are typed in `models.py`; timestamps must include a timezone, duplicate metric fields and alert IDs are rejected, and each list has a fixed maximum size. `source_scope` is `account_profile`, `simulated_fixture`, or `user_entered`. Fixture data cannot be combined with account-profile context. Profile context is opt-in on each packet, limited to age, gender, pronouns, blood type, allergies, medical conditions, and medications; the submitted values are checked against the authenticated profile before the packet is stored. Exact birthdate, emergency contacts, assessment answers, and conversation text are not accepted by the contract.

Responses label `provenance_status` as `user_declared`: the service records the declared source and does not cryptographically verify sensor origin. `payload_bytes` is the UTF-8 byte length of the compact serialized packet envelope, including its ID, creation time, version, source, selected fields, and data. `bytes_sent` records local simulated progress; `attempt_count` increments when the sender starts or resumes in a contact window.

## Routes

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/api/v1/mission-control/status` | Owner-scoped queue counts plus the current/next simulated contact state and configured transfer rate/capacity. |
| `GET` | `/api/v1/mission-control/contact-windows?limit=5` | Current and upcoming deterministic windows (limit 1–24), clearly marked simulated. |
| `POST` | `/api/v1/mission-control/outbox` | Validate consent and packet, then create or idempotently replay a queued packet. Reusing a key with a different body returns `409`. |
| `GET` | `/api/v1/mission-control/outbox?limit=20` | List the authenticated user's packets, newest first (limit 1–100). |
| `GET` | `/api/v1/mission-control/receiver/messages?limit=50` | List only this authenticated astronaut's messages accepted by the simulated receiver. |
| `GET` | `/api/v1/mission-control/outbox/{message_id}` | Read one owner's packet and its append-only transfer event history; other users receive `404`. |
| `POST` | `/api/v1/mission-control/outbox/{message_id}/cancel` | Cancel queued/deferred packets with no transfer attempts, using their current `expected_revision`. |
| `GET` | `/health` | Check SQLite and sender readiness without any Earth/link dependency. |

Errors use `{ "error": { "code": "...", "message": "..." } }`. Responses include `Cache-Control: no-store`. Packet state changes are immutable snapshots plus append-only queued, deferred, transmission-started, resumed, sent, received, and cancelled events.

## Persistence and deployment

The service uses its own SQLite database (`MISSION_CONTROL_DB_PATH`) and schema version (`PRAGMA user_version=3`); versions 1 and 2 migrate in place. Compose mounts it at `/data/mission_control.db` in the `mission-control-data` volume. Terminal `sent`, `cancelled`, and `failed` packets and their idempotency records are purged after `MISSION_CONTROL_RETENTION_DAYS` (default 30, allowed range 1–365); active packets and their idempotency keys are retained. Transfer progress, contact-window capacity, and one receiver record per message ID survive process restarts.

The repeating schedule is anchored at the first database initialization. Defaults are a 20-second window every 60 seconds, 512 bytes/second, and 4096 bytes of transfer capacity per window. Configure `MISSION_CONTROL_CYCLE_SECONDS`, `MISSION_CONTROL_WINDOW_SECONDS`, `MISSION_CONTROL_TRANSFER_RATE_BYTES_PER_SECOND`, and `MISSION_CONTROL_WINDOW_CAPACITY_BYTES` in Compose to speed up or slow down a demo. These timings are illustrative and are not an orbit, DSN, or NASA schedule.

The API is exposed locally at `http://localhost:8003` by default (`MISSION_CONTROL_API_PORT`). The astronaut's compose/help-request UI is integrated into the main AstraHealth site at `http://localhost:8080/mission-control`. The Earth-side dashboard remains separate at `http://localhost:8081` (`MISSION_CONTROL_DASHBOARD_PORT`): its message archive is scoped to the signed-in account, while its live telemetry section polls the same simulator for every registered profile. Only UUID, display name, and mission label are retrieved for roster display; readings are generated simulation data, not profile health records. It is a separate container and does not load or depend on the main web app.

From the repository root, start the service with the rest of the app:

```powershell
docker compose up -d --build mission-control mission-control-dashboard
```

`sent` means the local simulated receiver accepted the packet. Its receipt timestamp is illustrative and does not represent Earth receipt or acknowledgment.
