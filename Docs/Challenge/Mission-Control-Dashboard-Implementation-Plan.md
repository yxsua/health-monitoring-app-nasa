# Mission Control Dashboard: Store-and-Forward Simulation Plan

Status: implementation in progress. Increments 1–3 are implemented as an authenticated outbox, deterministic local transfer simulator, onboard composer/help-request UI, and separate Earth receiver; runtime acceptance remains pending. No Earth link or ground station is implemented by this plan.

## Goal

Add an authenticated Mission Control area where the astronaut can queue a structured health/mission update, write a text update, or request professional/additional help. Messages persist in an outbound queue and the local simulator transfers them during a simulated communications window. If no window is open, the update remains queued until the next simulated opportunity. The UI must make clear that the contact window, transmission, help request, and receiver are simulated; this feature must not make any real network connection or contact a real support provider.

Monitoring, assessments, recommendations, and access to locally stored data continue when the simulated link is unavailable. The onboard app never waits for Earth to return guidance or an acknowledgement before acting.

## Current building blocks

- `astronaut_app` owns the authenticated profile and exposes the current user's profile through `/api/v1/astronauts/me`.
- The profile now contains optional age or birthdate, gender, pronouns, blood type, allergies, medical conditions, medications, and emergency-contact details. Age is calculated when a birthdate is stored.
- `simulated_inputs_app` produces fixture telemetry and rule/anomaly/forecast output, but its subjects (`A01`, `AST-001`) are separate from account UUIDs.
- `chatbot_app` owns structured assessments and daily check-ins. Conversation text is stateless and must remain excluded from operational exports.
- The solution architecture already calls for an optional summary export worker and a persistent outbound queue; Earth communication remains outside MVP-critical monitoring.

Do not join fixture-subject metrics to an account profile by matching display name, age, mission, or any other profile value. Until an explicit, authenticated mapping exists, fixture updates must be labeled as simulated fixture data.

## Scope for the first increment

1. **Outbound simulation only.** A local service simulates contact opportunities, packet transfer, and an optional Earth-receiver receipt. There is no external transport, orbital propagation, or real telemetry link.
2. **User-initiated packets.** The user previews a typed summary and chooses **Queue for next contact**. Automatic alert forwarding is deferred until an explicit sharing policy exists.
3. **Durable queue.** Queued, deferred, sending, sent, cancelled, and failed states survive service restarts. Transfer attempts are retained as events; retries do not create duplicate Earth-side messages.
4. **Strict data allowlist.** A packet contains selected structured measurements/alerts and their source and observation times. It does not accept arbitrary serialized dashboard state.
5. **Explicit disclosure per packet.** Health-profile fields are excluded by default and require an affirmative selection in the packet preview. A user can send age instead of birthdate; exact birthdate is never an export option. Emergency-contact name, relationship, and phone are never included in the initial scope.
6. **No private transcripts.** Chatbot messages and free-text conversation are not accepted by the packet contract. Assessment answers are also excluded; only explicitly selected result summaries can be considered in a later increment.

## Data policy

### Included by default in an update

- A stable, non-secret local message ID and contract version.
- Mission label and packet creation time.
- Explicitly selected metric values with units, quality, and observation timestamps.
- Explicitly selected rule-alert identifiers, severities, and evidence references.
- Source classification (`account_profile`, `simulated_fixture`, or `user_entered`) and applicable source reference.

### Excluded by default

- Exact birthdate, gender, pronouns, blood type, allergies, medical conditions, medications, emergency contacts, assessment answers, and chat content.
- Bearer tokens, passwords, session identifiers, and simulator fixture data represented as an account holder's personal measurements.

If a later change permits selected profile health context, the UI must preview each field, obtain per-message consent, record which fields were included, and provide a clear local retention/deletion policy before enabling transmission. The local profile service remains the source of truth; mission control stores only the approved outbound snapshot and its delivery events.

## Contact-window behavior

The first demo should use an accelerated, configurable schedule, for example a short open window followed by a longer closed period. These are presentation timings only, not an orbit/DSN model. The schedule is deterministic for a run and clearly labeled **SIMULATED CONTACT WINDOW**.

Proposed packet lifecycle:

```text
user confirms preview
        |
        v
     queued ------ no open window ------> deferred (still queued)
        |                                      |
        +------------ next window ------------+
                         |
                         v
                    transmitting
                    /          \
       window closes            packet completes
             |                         |
             v                         v
          deferred              sent to receiver
                                        |
                            simulated receipt (separate state)
```

- A service-owned sender advances transfer state; the browser does not act as the transport worker.
- A configured simulated rate/capacity determines whether a packet completes in the current window. An interrupted packet resumes at the next window using the same message ID.
- `sent` means the local simulated receiver accepted the packet. It is not the same as `acknowledged`; an optional simulated receipt has its own timestamp and status.
- No open window leaves data queued. Closing or restarting the page does not delete or send it.
- A cancellation is available only before transmission starts. Acknowledging or cancelling an alert locally does not remove a packet that is already in transfer.
- Schedule controls are demo/operator configuration, not astronaut health inputs.

## Proposed service and API

Create `Project/mission_control_app` as a separate local FastAPI service with its own SQLite database and Docker Compose volume. Keep the communication simulator replaceable behind a small `ContactWindowProvider` and `Transport` interface so a future approved radio adapter can be introduced without changing the dashboard contract.

All user routes verify the bearer token with `astronaut_app` and scope outbox records to the returned astronaut UUID. The packet-creation request requires consent and a client idempotency key. Use strict Pydantic models and bounded list/text sizes; do not accept an arbitrary `payload: dict`.

Proposed routes:

| Route | Purpose |
| --- | --- |
| `GET /api/v1/mission-control/status` | Current simulated-link state, current/next window, last successful simulated send, and queue counts. |
| `GET /api/v1/mission-control/contact-windows` | Upcoming simulated windows and their configured capacity/quality. |
| `POST /api/v1/mission-control/outbox` | Validate a selected structured snapshot, store an immutable packet, and queue it for the next opportunity. Requires `Idempotency-Key` and `consent: true`. |
| `GET /api/v1/mission-control/outbox?limit=...` | List only the authenticated user's queued and recent packets with status and source labels. |
| `GET /api/v1/mission-control/receiver/messages` | Return only the authenticated astronaut's messages accepted by the simulated receiver. |
| `GET /api/v1/mission-control/outbox/{message_id}` | Preview an immutable packet, transfer attempts, and simulated receipt status. |
| `POST /api/v1/mission-control/outbox/{message_id}/cancel` | Cancel a queued packet before its first transfer attempt. |
| `GET /health` | Check the local mission-control store and sender readiness without requiring Earth connectivity. |

Version the packet schema separately from the service API. A packet has `message_id`, `schema_version`, `created_at`, `source_scope`, `selected_fields`, `data`, and explicit source timestamps. Its response includes `status`, `bytes_total`, `bytes_sent`, `attempt_count`, `last_attempt_at`, `sent_at`, and a separate optional `receipt` object. A persistent event log records queued, deferred, transmission-started, resumed, sent, received, cancelled, and failed transitions.

## Dashboard experience

Place the astronaut's **Mission Control** message composer and help requests inside the authenticated AstraHealth web app at `/mission-control`. Keep the **Earth receiving console** as its own service at port 8081 (configurable), with the API separately exposed at port 8003 (configurable). The receiver authenticates through the astronaut identity service and displays only that astronaut account's received records. It does not route through, load, or depend on the main AstraHealth web app. Reuse the AstraHealth type, palette, field styles, and visible simulation provenance.

The page should show:

- **Link card:** simulated link unavailable/open, next contact countdown, window duration/capacity, and “simulated” badge.
- **Compose update:** select a source and allowed fields; show a readable preview and data-classification labels before the user queues it.
- **Text and help requests:** let the crew write an update or request medical, mental-health, technical, or additional support. These are user-entered packets; do not pull chatbot text automatically.
- **Outbox:** queued/deferred/transmitting/sent/cancelled/failed rows, progress, attempt count, next opportunity, and retry explanation.
- **Receipt history:** distinguish local transmission from simulated Earth receipt; show both timestamps and mark any status as illustrative.
- **Profile context:** show whether optional profile details exist, but never preselect them for sharing. The initial composer should not offer emergency-contact details or exact birthdate.

Poll status at a modest interval only while Mission Control is the active route. The app's existing three-second monitoring reads continue independently. No communication alert should cover or block critical health alerts; if a contact status notice is needed, use a separate, dismissible status region.

## Ordered implementation plan

| Increment | Deliverable | Completion gate |
| --- | --- | --- |
| 1. Contract and local service | **Implemented:** Pydantic contract v1.0.0, SQLite schema version 2 at completion, bearer ownership, idempotent packet creation, owner-scoped status/outbox reads, and queued-packet cancellation. | Runtime acceptance walkthrough remains pending: verify per-user isolation, idempotent replay/conflict, malformed fields, profile selection validation, and cancellation through the deployed stack. |
| 2. Deterministic contact simulator | **Implemented:** configurable fixed windows and transfer limits, persistent sender worker, local deduplicating receiver, event history, and restart recovery. | Runtime walkthrough remains pending: closed window queues; open window sends; capacity/close defers and resumes; one receiver record per message ID. |
| 3. Mission Control UI | **Implemented across two surfaces:** the astronaut's text/help composer, contact status, and outbox are in the main authenticated web app; port 8081 is an independent Earth receiver showing only delivered packets. | Responsive browser walkthrough remains pending; confirm keyboard use and that the main app functions with Mission Control stopped. |
| 4. Profile-aware disclosure | Per-packet field selection, preview, consent capture, field allowlist, retention/deletion controls. | Sensitive profile data remains off by default; exact DOB, emergency contact, and conversation text cannot be exported. |
| 5. Policy-based auto-queue (optional) | User-configurable rules for selected alert summaries; no automatic inclusion of profile data. | Repeated alerts update/deduplicate a queued item; user can disable policy; existing onboard alerts stay authoritative if sender is offline. |
| 6. Real transport adapter (future, separate approval) | Interface implementation for an approved local relay and a remote receiver. | Security, encryption, identity, mission-network authorization, retry, and target-hardware reviews are complete. Never substitute real network activity into the simulator phase. |

## Acceptance walkthrough

1. Register/sign in and open Mission Control; profile health data is not present in any packet.
2. With the simulated contact closed, preview and queue a metric/alert update; it shows as deferred/queued and survives navigation and service restart.
3. Advance to an open simulated window; show transfer progress, then a sent state and distinct simulated receipt timestamp.
4. Interrupt a transfer before completion; verify it resumes at a later window without a duplicate receiver message.
5. Repeat packet creation with the same idempotency key; verify one message and one receiver record.
6. Try to request another user's outbox; deny access. Try a free-text transcript, exact DOB, emergency contact, or an unallowlisted field; reject the packet.
7. Stop `mission_control_app`; verify health readings, alerts, assessments, and locally stored history continue normally.
8. Verify mobile layout, keyboard flow, screen-reader labels, visible simulated status, and the distinction between observed, sent, and received times.

## Decisions to keep visible during implementation

- The first milestone is an **onboard outbox and simulated receiver**, not a live Earth control portal.
- The accelerated contact schedule is a UI/demo device; do not describe it as NASA/DSN availability or an orbital calculation.
- Health-profile details are local sensitive data. Do not make “profile complete” or profile disclosure a prerequisite to using the dashboard.
- `A01` and `AST-001` are not account identities. Until a reviewed mapping exists, their outputs stay tagged as simulated fixtures.
- The outbound queue is additive and non-blocking. It must never change local risk severity, clear alerts, postpone local recommendations, or make the UI appear connected to real mission control.
