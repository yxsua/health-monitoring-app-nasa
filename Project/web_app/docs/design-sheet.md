# AstraHealth design sheet

## Product kind and scope

**Kind:** software — local astronaut health monitoring and structured wellbeing assessments. The interface is an authenticated operations console, not a promotional landing page. The first complete journey is register/sign in → overview → assessment → saved result → overview.

## Voice

**Facts only:** short labels and direct instructions. Measurement names, values, units, timestamps, source and quality remain explicit. Simulator IDs are fixtures, separate from the account. Assessment text and interpretations come from the chatbot service unchanged. Risk coloring follows explicit backend rule evidence and is not a clinical conclusion.

## Colors

- Canvas: `#050609`; surfaces: `#0A0B12`; raised surface: `#11131E`.
- Ink: `#F0F1F5`; secondary text: `#B3B7C4`; quiet text: `#888E9F`.
- Deep blue: `#0E0B9C` for selected controls, mission markers, and interface emphasis.
- Electric lime: `#C6FF00` for primary actions, live status, and nominal measurements. Amber and red remain reserved for returned caution and elevated/critical risk.
- Missing data: neutral grey with the word “Unavailable”; never green or a zero value.

## Typography and spacing

- System sans stack; no remote font or runtime asset dependency.
- Page title 32/38 desktop, 28/34 mobile; section title 19/26; body 15–16/24; metadata 12–13/18.
- Spacing steps: 4, 8, 12, 16, 20, 24, 32, 40, 48.
- Content max width 1360px; desktop page gutters 40px, tablet 24px, mobile 16px.
- 12px panel corners, 8px control corners, 44px minimum controls, 1px borders. Earth shading is isolated to the login illustration.

## Component states and interactions

- Buttons: one filled primary action per panel, outlined secondary, text utility; hover shifts slightly, press returns, focus has a 3px visible ring. Reduced motion disables transitions.
- Service state: explicit loading, available, not assessed, stale, and transport unavailable labels. Follow-up text is displayed as soon as the assessment response includes it.
- Measurement: value + unit + quality; null is “Unavailable”. Fixture source and selected fixture subject stay visible. Simulated inputs refresh every three seconds while the dashboard is active and the tab is visible; pause/resume is explicit, and only one request may be in flight.
- Overview: body-map regions provide keyboard- and pointer-accessible shortcuts to their measurements. Every metric card draws a sparkline from the latest eight returned samples. Rule evidence colors the affected metric chart and status icon by risk; nominal, caution, warning, critical, and unknown remain distinct. Repeated alert types are shown as upper-right notifications no more than once per three minutes.
- Login: the left half is a locally bundled NASA Blue Marble texture shaded as a rotating WebGL Earth, with a user-controlled pause and reduced-motion support. The sign-in panel keeps only the access label, form, and account action.
- Identity: AstraHealth is the document, navigation, social-card, and favicon brand.
- Automated analysis: rule assessment, anomaly detection and forecast remain separate cards. Each has loading, available, warming-up/insufficient-data and unavailable states; missing analysis never hides measurements. Rule thresholds are labeled as demonstrations, anomaly scores are not percentages, and forecasts show their sample cadence and horizon.
- Simulator controls: fixture subject and active scenario are visibly selected and remain separate from the signed-in account; scenario changes apply before the next sample is accepted.
- Assessment: server question, answer options, revision and status are authoritative. Saving disables duplicate action; conflicts reload current server state.
- Responsive: no hover-only content. Desktop uses overview and adjacent status panels; tablet stacks the main regions; mobile uses one column and wraps controls.

## Wireframes

### Desktop, 1440px

```text
┌ fixed topbar: mark · Overview / Wellbeing / History · profile · sign out ┐
│ page title, signed-in profile and mission                                  │
│ ┌ body overview, 5-col ───────┐ ┌ live simulated metrics, 7-col ────────┐ │
│ │ keyboard/touch body regions │ │ physical and wellbeing measurements │ │
│ │ selected region details     │ │ environmental metrics + sample trend │ │
│ └─────────────────────────────┘ └───────────────────────────────────────┘ │
│ fixture selector · sync time · pause/resume · assessment summary            │
└───────────────────────────────────────────────────────────────────────────┘
```

### Mobile, 390px

```text
┌ compact header / navigation ───────────────┐
│ title and profile                          │
│ fixture subject + live/pause state          │
│ body overview and selected region          │
│ physical and wellbeing readings            │
│ environmental readings                     │
│ assessment status and follow-up            │
└────────────────────────────────────────────┘
```

### Assessment session

```text
┌ breadcrumb + instrument and server status ──┐
│ progress                                     │
│ follow-up notice, when returned              │
│ question, official options, Save answer       │
│ static help actions · pause/resume/cancel     │
└──────────────────────────────────────────────┘
```
