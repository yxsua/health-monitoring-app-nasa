Kind: software — local astronaut health application.

# Frontend Development: Next Steps

Status: proposed hackathon roadmap. Target: `Project/web_app`. This document defines the next implementation work; it does not create the frontend.

## 1. Current State and Goal

The frontend directory is empty. Three local services are available:

| Service | Default port | Available functionality |
| --- | --- | --- |
| Simulated inputs | 8000 | A fresh simulated observation on every successful endpoint call. |
| Astronaut profiles | 8001 | Registration, login/logout, profile updates, bearer-session validation. |
| Assessment chatbot | 8002 | Persistent PHQ-9/GAD-7 sessions, scoring, follow-up flags, history, risk summaries, static explanations. |

Build a React + TypeScript application that lets an astronaut sign in, inspect simulated health and cabin measurements, complete a structured assessment, and review results. All essential functionality must run locally after deployment.

The main risk engine is not implemented. The frontend must not invent medical alerts, diagnoses, risk probabilities, or severity classifications to fill that gap. It can display measurement quality, trends, and the chatbot's existing follow-up flags.

## 2. MVP Scope and Priority

**First working flow:** register or sign in → dashboard → start assessment → save answers → complete → view result → return to dashboard.

**Second flow:** generate a simulated sample → inspect measurements → select a body region → inspect relevant readings and recent samples.

Include account/profile controls, assessment resume, result history, an environmental panel, and explicit service availability. Defer 3D anatomy, unrestricted AI conversation, model training, professional portals, Earth dashboards, and gamification.

Consent, retention, event-resolution authority, disclosure policies, hardware qualification, and model memory/latency budgets remain outside the hackathon backlog, as agreed. Basic login, ownership enforcement, accurate status displays, and deterministic backend scoring remain required.

## 3. Application Structure

Use Vite with React and TypeScript. Add routing and a small authentication context. Keep backend responses in feature-specific state; introduce a broader state library only if an actual coordination problem requires it.

```text
Project/web_app/
  src/
    app/                  # routes, app shell, providers
    features/
      auth/               # registration, login, token lifecycle
      profile/            # profile display and edit form
      monitoring/         # samples, cabin panel, local trend buffer
      body-map/           # interactive SVG and metric mapping
      chatbot/            # sessions, questions, results, support panel
    services/             # identity and simulation clients
    components/           # buttons, fields, status labels, dialogs
    styles/               # tokens, typography, layout, focus states
    test/                 # API fixtures and UI tests
  public/                 # bundled local assets only
```

Reuse the chatbot's generated types and client rather than creating a second handwritten contract. Either import them through an explicitly configured workspace path or copy them through a documented generation task. Regenerate on backend contract changes; do not maintain two independent definitions.

Suggested routes:

| Route | Purpose |
| --- | --- |
| `/login`, `/register` | Account entry. |
| `/dashboard` | Monitoring overview, cabin conditions, assessment summary. |
| `/wellbeing` | Assessment selection and resumable sessions. |
| `/wellbeing/sessions/:sessionId` | Structured questionnaire and static assistance. |
| `/wellbeing/results/:sessionId` | Completed assessment result. |
| `/wellbeing/history` | Completed results, grouped by compatible instrument/version. |
| `/profile` | Display name, mission, and logout. |

## 4. Visual Direction

Create a working monitoring interface with a consistent layout, typography scale, button style, spacing system, and restrained status colors. Use the actual product information as the visual focus: readings, a body map, trends, and questionnaire state.

- Desktop: compact navigation, main monitoring/body-map area, adjacent details panel, persistent access to follow-up guidance.
- Tablet/mobile: stack regions into a readable single-column flow; selected measurements and alerts must remain accessible without hovering.
- Reserve strong status colors for actual states; pair every color with text or an icon. Missing data must never resemble a healthy reading.
- Keep body-map labels, units, timestamps, simulation labels, and quality indicators visible where they help interpret data.
- Use plain copy: “Generate sample,” “Start assessment,” “Save answer,” “Resume assessment,” and “View result.” Avoid “AI analysis” when only static explanations are available.
- Use quiet hover/press feedback, clear focus rings, and reduced-motion support. Motion must not delay questions, conceal readings, or imply a changing medical status.
- Use local icons/fonts or system fonts; no runtime CDN dependencies.

Apply the design-taste-frontend skill's consistency, spacing, readability, interaction, and browser-review guidance. Its marketing-page conventions—full-screen heroes, decorative scenes, and promotional section pacing—must be adapted to this operational application rather than added to the dashboard. Medical labels and simulation provenance are functional UI, not decorative image captions.

Before styling components, define a short design sheet with colors, typography, spacing, status semantics, component states, and desktop/mobile wireframes. The document does not preselect a skill palette or claim a design gate has passed; that happens during frontend implementation.

## 5. Integrate the APIs Correctly

### Authentication and profiles

1. Register through `POST /api/v1/auth/register`, then sign in through `POST /api/v1/auth/login`.
2. Keep the returned bearer token in memory and use the returned server-generated astronaut UUID.
3. Load `/api/v1/astronauts/me` for the profile and navigation identity. Update only supported fields through `PATCH`.
4. Protect application routes. On 401, clear user-specific state and show login; preserve no previous user's data on screen.
5. Logout calls the backend before clearing the local token. If revocation fails, clear local UI state but report that server logout was not confirmed.

A full page reload loses an in-memory token: require login again, then load saved assessment sessions from the backend. This is acceptable for the demo and must be handled intentionally.

### Simulator: explicit generation first

Use `GET /api/v1/simulation/runs/demo-run/astronauts/A01/inputs` initially, but identify this visibly as fixture data. The registered UUID is not currently accepted by simulator configuration.

**Required integration decision:** either add a backend mechanism that maps registered astronaut UUIDs to simulator subjects, or provide a clearly labeled demo-subject selector (`A01` / `AST-001`) separate from the signed-in profile. Start with the selector to avoid silently presenting unrelated fixture data as the astronaut's actual measurements.

Every successful request generates a new sample. Therefore:

- Start with an explicit “Generate sample” button.
- Do not prefetch this endpoint or enable automatic retries, focus refetching, or duplicate mount effects.
- Disable the action while a request is pending. An aborted browser request may already have generated data on the server; do not promise rollback.
- If automatic sampling is added, provide explicit start/stop controls, one request at a time, and cleanup on route exit/logout. Stop when the document is hidden.
- Keep a bounded client-side sample buffer for demo charts, reset it when the selected subject changes, and label its limited history.
- Deduplicate by record ID. Preserve timestamps and units. Display null values as unavailable, not zero.
- Daily aggregate values are freshly simulated estimates on each request; do not sum them across samples or present them as independent daily history.

The simulator currently lacks the other services' documented frontend CORS configuration. Use a Vite development proxy and a same-origin production reverse proxy, or add an explicit origin allowlist to that service before direct browser calls. Do not solve this with browser security bypasses.

### Chatbot

Reuse `Project/chatbot_app/contracts/client.ts` and its generated types.

- Load definitions and render official backend text/options unchanged.
- Create a session with an idempotency key retained until the request outcome is known.
- Display the backend's `current_question`, `revision`, responses, and status. Never calculate the next question or score independently.
- Submit one answer at a time with `expected_revision`. Show saving state and advance only after success.
- On 409, reload authoritative state and explain that the session changed. Do not blindly repeat a conflicting write.
- Support pause, resume, cancellation, corrections before completion, and immutable completed results.
- Complete with a stable idempotency key; retries must reuse the original body/key.
- Static assistance uses typed intents: instructions, question, result, or support. Use buttons for these actions; do not show a free-text chat box that the API cannot support.
- Show follow-up guidance immediately when returned with an answer, before waiting for dashboard summary polling.

### Dashboard risk summaries

Read the chatbot's summary for the authenticated UUID. Poll only while the relevant screen is active; a proposed initial interval is 10 seconds, with bounded retry/backoff for read-only requests.

Render `not_assessed`, `available`, `stale`, and transport-unavailable distinctly. Show the source assessment and timestamp. Never imply that `not_triggered` establishes overall safety.

Deduplicate follow-up notifications by summary ID/revision, but re-read availability on every poll: a result can become stale without a revision change. Do not automatically clear a follow-up flag when a newer low score arrives. No resolution button is supported by the current API.

## 6. Dashboard and Body Map

Build 2D SVG anatomy after authentication and the first questionnaire flow work.

| UI region | Initial measurements |
| --- | --- |
| Heart/circulation | Heart rate, blood pressure, HRV. |
| Respiratory view | SpO2, with its limits as a measurement explained in existing product guidance. |
| General health | Body temperature and glucose. |
| Activity and well-being | Sleep, exercise, mood, and links to assessments. |
| Cabin panel | CO2, cabin temperature/pressure, humidity, noise, radiation rate, gravity. |

This mapping is navigation, not a diagnostic claim. Keep multi-system measurements accessible from the metric list as well. Do not place a warning color on an organ unless a real backend assessment supports it. Radiation and cabin conditions belong in the environmental panel rather than being assigned to a single organ.

Make SVG regions keyboard-operable with accessible names, selected states, and equivalent list controls. Selecting a region opens related measurements and brief functional information. Keep follow-up messages outside the map so they cannot be missed behind a click target.

## 7. Ordered Implementation Backlog

| Step | Deliverables | Acceptance gate |
| --- | --- | --- |
| 1. Scaffold and contracts | React/TypeScript/Vite, routes, local proxy configuration, API adapters, shared error handling. | Production build succeeds; clients use local services; no CDN dependency. |
| 2. Login and profile | Register/login forms, auth context, protected routes, profile edit, logout. | A registered astronaut can sign in, update supported fields, and sign out; expired tokens return to login. |
| 3. Structured chatbot | Assessment picker, question/options, save states, pause/resume/cancel, static help. | A session survives navigation and backend restart; a reauthenticated user can resume it. |
| 4. Results and follow-up | Completion, result card, history, immediate guidance, summary display. | Backend score is shown unchanged; duplicate completion does not duplicate results; flags appear before completion. |
| 5. Simulated monitoring | Explicit sample generation, demo-subject labeling, metric panels, bounded trends. | Exactly one intended request per action; all 20 fields represented, with unsupported fields unavailable. |
| 6. Interactive body map | Responsive SVG, region selection, metric details, environmental separation. | All regions work with keyboard/touch and the dashboard remains usable without the graphic. |
| 7. Browser verification and demo packaging | Responsive review, accessibility checks, error-state tests, local production serving instructions. | Full walkthrough passes at desktop/tablet/mobile sizes and without external internet. |

Prefer one complete login-to-assessment flow before expanding the dashboard. Do not build a separate marketing landing page for this MVP.

## 8. Verification Checklist

- Register, sign in, edit profile, logout, and reject an expired/revoked token.
- Complete both questionnaires using synthetic answers; display backend results without recomputation.
- Pause, reload, sign in again, and resume the correct saved session.
- Prevent double submission; recover from a lost response or revision conflict without overwriting answers.
- Display follow-up guidance before completion and retain it when summary data becomes stale.
- Reject cross-user access and clear all previous user's cached UI data on logout/account changes.
- Generate one simulator sample per explicit action; verify no extra request from Strict Mode, focus changes, or navigation prefetch.
- Verify fixtures are labeled separately from registered identities and unsupported measurements remain null/unavailable.
- Stop each backend independently: show the relevant outage without turning missing data green or hiding unrelated working features.
- Test keyboard-only navigation, visible labels/focus, status announcements, readable contrast, reduced motion, and long question text.
- Inspect screenshots at 1440, 1024, 768, and 390 pixels; check 320-pixel overflow and touch target spacing.
- Run the skill's applicable design checks on the actual built interface and record any app-specific exceptions honestly; no visual gate is complete at planning time.
- Build once, disconnect external internet, and run locally with all three services. All scripts, fonts, icons, and assets must already be available.

Use component/integration tests for user flows and API error states, and a real browser walkthrough for layout and accessibility. Do not mark a mocked test as proof of live integration.

## 9. Demo Completion Criteria

A presenter can start the local services and frontend, create an account, inspect a labeled simulated sample, navigate the body map, complete an assessment, see follow-up guidance when triggered, view the stored result, and resume a paused session after signing in again. Every screen distinguishes simulated inputs, missing data, static assistance, and backend-generated results.

Deliver startup instructions, environment examples, the production build, and a short verification report. Pending capabilities must remain plainly identified: no free-form model conversation, autonomous main risk engine, real sensor integration, or Earth dashboard.

## References

- [Main platform requirements](Solution-Requirements-and-Architecture.md).
- [Simulated-inputs contract](Simulated-Astronaut-Inputs-Contract.md).
- [Astronaut service](../../Project/astronaut_app/README.md).
- [Chatbot service and API walkthrough](../../Project/chatbot_app/README.md).
- [Chatbot implementation plan](../../Prototypes/chatbot/chatbot-implementation-plan.md).
- [Design-taste-frontend skill](../../.agents/skills/design-taste-frontend/SKILL.md).
