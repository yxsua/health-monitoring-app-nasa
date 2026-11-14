# Simulated Astronaut Inputs API Contract

Version: 1.0.0 (proposed). Source: [modelo_DatosAstronautas.xlsx](modelo_DatosAstronautas.xlsx). Companion schema: [simulated-astronaut-inputs.schema.json](simulated-astronaut-inputs.schema.json). Sample response: [simulated-astronaut-inputs.example.json](simulated-astronaut-inputs.example.json).

OpenAPI 3.1 contract: [simulated-astronaut-inputs.openapi.json](simulated-astronaut-inputs.openapi.json). This self-contained specification embeds the response schemas and examples, defines all parameters and error responses, and uses a same-origin server. Authentication transport remains deployment-specific, as described below; configure a local security scheme before protected deployment.

The sample response preserves the workbook's numeric example values but adds illustrative run metadata and explicitly assigns the previous UTC day to daily aggregates. Those periods are synthetic example configuration, not information extracted from the workbook. Activity, fasting status, and HRV baseline remain unknown. The three indicators absent from the source example are missing.

## Source Findings

The workbook contains five sheets: `Fisiológicas` (7 indicators), `Autoevaluación` (3), `Entorno` (10), `Escenarios de demo` (4 scenarios), and `Registro de ejemplo` (one example with 20 columns: 3 identifiers/context fields and 17 indicators). There are no time series in this workbook.

Three indicators described in `Entorno` are absent from the example: Earth communication latency, simulated daylight hours, and social interaction minutes. Include them in the API with explicit missing values until a scenario supplies them. Social interaction remains in the environment group to preserve source organization, although it describes the individual astronaut.

The source explicitly labels its ranges as simulation references, not official clinical criteria. The endpoint serves inputs, not diagnoses or alert severities. Alert interpretation belongs to the assessment service.

## Endpoint

```http
GET /api/v1/simulation/runs/{run_id}/astronauts/{astronaut_id}/inputs?limit=100
Accept: application/json
```

Returns an ordered page of immutable observations already produced by a local simulation run. GET does not advance simulation time, generate a new random sample, create a run, or modify stored observations. Run creation and playback controls are separate APIs outside this contract.

| Parameter | Location | Type | Rules |
| --- | --- | --- | --- |
| `run_id` | path | string | Required, nonempty; identifies a persisted run and its fixed scenario configuration. |
| `astronaut_id` | path | string | Required, nonempty; source example is `A01`. |
| `from` | query | UTC RFC 3339 timestamp | Optional, inclusive lower observation-time bound. |
| `to` | query | UTC RFC 3339 timestamp | Optional, exclusive upper bound; must be later than `from` when both supplied. |
| `limit` | query | integer | Optional, default 100, minimum 1, maximum 1000. |
| `cursor` | query | string | Optional opaque continuation token from the previous page. Keep all other query parameters identical. |

Results sort by `(observed_at, record_id)` ascending. The first page freezes a snapshot of matching records; cursors retain that snapshot so playback cannot cause omissions or duplicates during pagination. Start a new request without a cursor to see newly generated records. A known run/astronaut with no matching observations returns HTTP 200 with `items: []` and `next_cursor: null`.

Local authorization must restrict access to the requested astronaut; no external identity service is required. Return `Content-Type: application/json` and `Cache-Control: no-store`. Authentication transport is a deployment decision; missing/invalid credentials return 401 and insufficient permission returns 403 when authorization is enabled.

## Response Envelope

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | string | Literal `1.0.0`. |
| `run_id` | string | Requested run. |
| `scenario_id` | enum | `normal`, `solar_event`, `high_co2`, `prolonged_isolation`. |
| `seed` | integer | Persisted nonnegative random seed. |
| `generator_version` | string | Simulator implementation/configuration version. |
| `simulation_time` | UTC timestamp | Simulation clock at the page snapshot, not wall-clock response time. |
| `items` | array | Observations matching the astronaut and filters. |
| `next_cursor` | string or null | Next snapshot page, or null when exhausted. |

Each item requires `record_id`, `astronaut_id`, `observed_at`, `mission`, `source: "simulated"`, `context`, and the three metric groups. `record_id` is stable and unique within the run. `mission` preserves the source text (for example `Marte`) and is not an enum. Do not infer local gravity from mission destination: the source's Mars mission example has gravity `0`.

`context` contains `activity` (`rest`, `exercise`, `sleep`, `unknown`), `fasting` (boolean or null), and `hrv_baseline_ms` (positive number or null). These are proposed additions, not fields supplied by the example row. Unknown context must remain unknown. A baseline must come from configured individual history, not from the current HRV reading.

## Measurement Representation

Every indicator key is present and contains:

```json
{
  "value": 72,
  "unit": "bpm",
  "observed_at": "2026-11-14T08:30:00Z",
  "quality": "valid",
  "period_start": null,
  "period_end": null
}
```

- `quality` is `valid`, `missing`, or `invalid`; it describes data usability, not health status. Valid measurements have a finite numeric value and an observation timestamp. Missing measurements use null value and timestamp. Invalid measurements use null value and may retain an observation timestamp; malformed raw values belong in diagnostic logs, not numeric API fields.
- A record timestamp identifies the snapshot. A metric timestamp identifies when that metric was actually observed. Carrying a previous measurement forward must retain its original timestamp.
- Daily aggregates require `period_start` and `period_end` when valid. Use a completed UTC day `[00:00:00Z, next 00:00:00Z)` in this proposed version. Missing or invalid measurements and instantaneous measurements use null periods. A future mission-day convention requires an explicit contract change.
- The workbook does not specify aggregate periods or actual per-metric observation times. Imported example daily values cannot be represented as valid aggregates until a period is supplied; do not manufacture one from the row timestamp.
- Consumers compute freshness using simulation time and configured indicator-specific staleness limits. The source's word “continuous” does not define a sampling interval or expiry time.
- Never replace missing measurements with zero. Preserve valid zero gravity and zero activity durations.

## Complete Field Mapping

All numeric values are JSON numbers except mood, which is an integer. Bounds below are data-domain checks, not normal-health bands. Decimal measurements are allowed. Each indicator uses the measurement representation above; units are fixed strings.

| Group / API key | Workbook source | Example column/value | API unit | Data-domain constraint | Cadence / period |
| --- | --- | --- | --- | --- | --- |
| `physiological.heart_rate` | Fisiológicas row 5 | D / 72 | `bpm` | >= 0 | Continuous; resting reference only |
| `physiological.systolic_pressure` | Fisiológicas row 6 | E / 115 | `mmHg` | >= 0 | Twice daily |
| `physiological.diastolic_pressure` | Fisiológicas row 7 | F / 75 | `mmHg` | >= 0 | Twice daily |
| `physiological.spo2` | Fisiológicas row 8 | G / 98 | `%` | 0–100 | Continuous |
| `physiological.body_temperature` | Fisiológicas row 9 | H / 36.6 | `degC` | Finite number | Hourly |
| `physiological.glucose` | Fisiológicas row 10 | I / 88 | `mg/dL` | >= 0 | Continuous CGM or daily; fasting reference only |
| `physiological.hrv_rmssd` | Fisiológicas row 11 | J / 54 | `ms` | >= 0 | Continuous |
| `self_assessment.sleep_duration` | Autoevaluación row 5 | K / 6.5 | `h/day` | 0–24 | Daily aggregate |
| `self_assessment.mood` | Autoevaluación row 6 | L / 4 | `score_1_5` | Integer 1–5 | Daily point-in-time check-in |
| `self_assessment.exercise_duration` | Autoevaluación row 7 | M / 100 | `min/day` | 0–1440 | Daily aggregate |
| `environment.radiation_dose_rate` | Entorno row 5 | N / 0.4 | `mSv/day` | >= 0 | Cadence unspecified; rate, not cumulative dose |
| `environment.co2` | Entorno row 6 | O / 2500 | `ppm` | >= 0 | Unspecified |
| `environment.cabin_temperature` | Entorno row 7 | P / 22 | `degC` | Finite number | Unspecified |
| `environment.humidity` | Entorno row 8 | Q / 50 | `%` | 0–100 | Unspecified |
| `environment.noise` | Entorno row 9 | R / 48 | `dBA` | Finite number | Unspecified |
| `environment.cabin_pressure` | Entorno row 10 | S / 101 | `kPa` | >= 0 | Unspecified |
| `environment.gravity` | Entorno row 11 | T / 0 | `g` | >= 0 | Unspecified; context, not severity |
| `environment.earth_latency` | Entorno row 12 | Absent | `s` | >= 0 | Unspecified; source does not define one-way vs round-trip |
| `environment.simulated_daylight_duration` | Entorno row 13 | Absent | `h/day` | 0–24 | Daily aggregate; sampling cadence unspecified |
| `environment.social_interaction_duration` | Entorno row 14 | Absent | `min/day` | 0–1440 | Daily aggregate; sampling cadence unspecified |

Identity mapping: `Registro de ejemplo!A4:A5` → `astronaut_id`; B → `observed_at`; C → `mission`. API keys and normalized unit strings are proposed contract decisions. All numeric example values above are extracted unchanged from row 5.

## Reference Ranges Extracted from the Workbook

Preserve these as source metadata for scenario design. Do not use them as schema bounds, automatically reject abnormal measurements, or silently resolve their ambiguities.

| Indicator | Normal | Caution | Critical |
| --- | --- | --- | --- |
| Resting heart rate | 60–100 | 50–59 / 101–120 | <50 / >120 |
| Systolic pressure | 90–120 | 121–139 | >=140 / <90 |
| Diastolic pressure | 60–80 | 81–89 | >=90 / <60 |
| SpO2 | >=95 | 92–94 | <92 |
| Body temperature | 36.1–37.2 | 37.3–38.0 | >38.0 / <35.5 |
| Fasting glucose | 70–99 | 100–125 / 60–69 | >=126 / <60 |
| HRV RMSSD | Near individual baseline | Drop >20% vs baseline | Drop >40% vs baseline |
| Sleep duration | 6–9 | 5–6 | <5 |
| Mood | 4–5 | 3 | 1–2, or 3 for several consecutive days |
| Exercise duration | >=90 | 45–89 | <45 |
| Radiation dose rate | <0.8 | 0.8–2 | >2 (solar event) |
| CO2 | <3,000 | 3,000–5,000 | >5,000 |
| Cabin temperature | 18–27 | 27–30 / 15–18 | >30 / <15 |
| Humidity | 40–60 | 30–40 / 60–70 | <30 / >70 |
| Noise | <55 | 55–65 | >65 |
| Cabin pressure | 99–102 | 95–99 | <95 |
| Gravity | 0 (microgravity), 0.16 (Moon), 0.38 (Mars) | n/a | n/a |
| Earth latency | ~1.3 (Moon), 240–1,440 (Mars) | n/a | n/a |
| Simulated daylight | 14–16 | 10–14 | <10 |
| Social interaction | >=60 | 20–59 | <20 |

Unresolved interpretation: sleep at 6, cabin temperature at 18/27, humidity at 40/60, cabin pressure at 99, and daylight at 14 overlap. Body temperature 35.5–36.1 is uncovered; values between decimal/integer band endpoints can also be uncovered. Sleep >9, cabin pressure >102, and daylight >16 have no specified classification. HRV bands overlap and “near baseline” is undefined; “several days” for mood is unspecified. These need explicit assessment policy before alert implementation. No clinical inference is made here.

## Simulation Scenarios

| `scenario_id` | Source label | Source behavior |
| --- | --- | --- |
| `normal` | Normal | All values within reference ranges. |
| `solar_event` | Evento solar | Radiation exceeds 2 mSv/day; after 24–48 hours temperature and heart rate rise and HRV falls. |
| `high_co2` | CO2 alto | CO2 exceeds 5,000 ppm, sleep worsens, and mood declines. |
| `prolonged_isolation` | Aislamiento prolongado | Mood and social interaction decline over several days. |

Source: `Escenarios de demo!A5:B8`. These are scripted synthetic demonstrations, not validated causal models. Row 2 recommends an individual baseline and realistic noise (±3–5%); the exact distribution, cadence, seed, bounds handling, and scenario timing must be versioned in generator configuration. Do not apply continuous percentage noise directly to categorical mood scores. Sampling periods for environmental metrics remain simulator configuration, not source facts.

## Errors

All error responses use `{"error":{"code":"...","message":"..."}}`.

| HTTP | Code | Meaning |
| --- | --- | --- |
| 400 | `invalid_cursor` | Cursor is malformed or its run, astronaut, or filters do not match. |
| 401 | `unauthorized` | Missing or invalid local credentials. |
| 403 | `forbidden` | Caller cannot access this astronaut. |
| 404 | `run_not_found` / `astronaut_not_found` | Unknown run, or astronaut not configured in that run. |
| 410 | `cursor_expired` | Snapshot no longer retained; restart pagination. |
| 422 | `invalid_query` | Invalid timestamp, range, limit, or unsupported query parameter. |
| 503 | `simulation_unavailable` | Local simulation storage cannot be read; do not substitute an empty success response. |

FastAPI implementations should normalize validation errors to this envelope. This document defines behavior independently of a framework's default error representation.

## Acceptance Criteria

1. All 20 mapped indicators are represented with exact units and explicit null/quality handling; none are silently omitted.
2. Numeric examples round-trip without changing units or values. The example's three absent fields remain missing. Daily values require explicit periods before import as valid aggregates.
3. An abnormal but well-formed input (for example CO2 of 5,500 ppm) is returned successfully, without an endpoint-generated diagnosis or severity.
4. Repeating a request against unchanged run state returns identical observations; GET never advances the run.
5. Pagination yields no duplicates or omissions despite subsequent simulation writes. Filters use inclusive `from` and exclusive `to`.
6. Missing, stale, invalid, and zero values remain distinguishable. Carried readings retain their original observation times.
7. UTC timestamps, enum values, required keys, units, numeric domains, and period rules are validated. NaN and infinity are not serialized.
8. Record and metric timestamps do not exceed snapshot simulation time; metric timestamps do not exceed record time; valid aggregate periods satisfy start < end <= metric observation time.
9. API retrieval, authorization, and stored-run replay work with external network access disabled.

The companion JSON Schema validates response structure and local field constraints. Cross-field time ordering, query semantics, cursor behavior, authorization, and scenario determinism require implementation tests. This deliverable defines a contract; it does not implement the endpoint.
