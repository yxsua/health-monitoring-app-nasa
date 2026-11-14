# Mission Health Console design sheet

## Product kind and scope

**Kind:** software — local astronaut health monitoring and structured wellbeing assessments. The interface is an authenticated operations console, not a promotional landing page. The first complete journey is register/sign in → overview → assessment → saved result → overview.

## Voice

**Facts only:** short labels and direct instructions. Measurement names, values, units, timestamps, source and quality remain explicit. Simulator IDs are fixtures, separate from the account. Assessment text and interpretations come from the chatbot service unchanged. The interface does not infer health or risk.

## Colors

- Canvas: `#0A1422`; surfaces: `#111F32`; raised surface: `#172941`.
- Ink: `#E8F0FA`; secondary text: `#AFBED0`; quiet text: `#879BB1`.
- Blue interface: `#6BB8FF` links, focus, and selected controls; deep blue panels and navigation surfaces.
- Red accent: `#C83F3A` primary actions. Brighter red is reserved for returned follow-up flags and actual request errors.
- Missing data: neutral grey with the word “Unavailable”; never green or a zero value.

## Typography and spacing

- System sans stack; no remote font or runtime asset dependency.
- Page title 32/38 desktop, 28/34 mobile; section title 19/26; body 15–16/24; metadata 12–13/18.
- Spacing steps: 4, 8, 12, 16, 20, 24, 32, 40, 48.
- Content max width 1360px; desktop page gutters 40px, tablet 24px, mobile 16px.
- 12px panel corners, 8px control corners, 44px minimum controls, 1px borders, no decorative gradients.

## Component states and interactions

- Buttons: one filled primary action per panel, outlined secondary, text utility; hover shifts slightly, press returns, focus has a 3px visible ring. Reduced motion disables transitions.
- Service state: explicit loading, available, not assessed, stale, and transport unavailable labels. Follow-up text is displayed as soon as the assessment response includes it.
- Measurement: value + unit + quality; null is “Unavailable”. Fixture source and selected fixture subject stay visible.
- Assessment: server question, answer options, revision and status are authoritative. Saving disables duplicate action; conflicts reload current server state.
- Responsive: no hover-only content. Desktop uses overview and adjacent status panels; tablet stacks the main regions; mobile uses one column and wraps controls.

## Wireframes

### Desktop, 1440px

```text
┌ fixed topbar: mark · Overview / Wellbeing / History · profile · sign out ┐
│ page title, signed-in profile and mission                                  │
│ ┌ simulated measurements, 8-col ──────────────┐ ┌ wellbeing, 4-col ────┐ │
│ │ explicit subject selector + Generate sample │ │ summary + follow-up  │ │
│ │ physiological and self-assessment values    │ │ assessment action    │ │
│ └─────────────────────────────────────────────┘ └───────────────────────┘ │
│ ┌ keyboard/touch measurement groups, 7-col ───┐ ┌ cabin values, 5-col ─┐ │
└───────────────────────────────────────────────────────────────────────────┘
```

### Mobile, 390px

```text
┌ compact header / navigation ───────────────┐
│ title and profile                          │
│ fixture subject + Generate sample          │
│ readings, two columns                      │
│ wellbeing status and follow-up             │
│ measurement group list + selected readings │
│ cabin values                               │
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
