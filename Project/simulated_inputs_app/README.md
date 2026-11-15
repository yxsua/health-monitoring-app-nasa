# Local simulated inputs API

From the repository root, create a Python virtual environment, install `Project/simulated_inputs_app/requirements-dev.txt`, and run:

```powershell
Project/simulated_inputs_app/.venv/Scripts/python.exe -m uvicorn Project.simulated_inputs_app.api:app --host 127.0.0.1 --port 8000
```

Request a fresh sample:

```http
GET http://127.0.0.1:8000/api/v1/simulation/runs/demo-run/astronauts/A01/inputs
```

Analyze that exact sample without generating another one:

```http
POST http://127.0.0.1:8000/api/v1/simulation/runs/demo-run/astronauts/A01/analysis
Content-Type: application/json
```

Send a JSON object with `scenario_id` from the GET response and `observation` set to the GET response's `items[0]`.

Before sampling a different scenario, select it on the dashboard or call:

```http
PUT http://127.0.0.1:8000/api/v1/simulation/runs/demo-run/scenario
Content-Type: application/json

{"scenario_id":"high_co2"}
```

Configured scenarios are `normal`, `solar_event`, `high_co2`, and `prolonged_isolation`. The last three apply controlled shifts to the shared live/training distributions. Scenario selection is run-wide and resets to `normal` on service restart.

The analysis request body is `{"scenario_id":"high_co2","observation":{...}}`, using the same scenario ID and observation from the GET response. The versioned analysis response (`contract_version: 1.1.0`) echoes both the scenario and `record_id`. Rule alerts are calculated from the arithmetic mean of valid values in the latest eight inputs for each run and astronaut; the response reports `rules.window_available` and `rules.window_size`, and rule history retains only those eight observations. A scenario change interpolates the simulator's means and standard deviations over eight generated inputs per astronaut, so polling a full crew does not accelerate a member's transition. In addition to the demo IDs, registered astronaut UUIDs can use the same input and analysis routes; each UUID gets a stable independent synthetic stream. Deterministic demonstration rules are available immediately. Isolation Forest and LSTM results report `unavailable` until reviewed model artifacts, a manifest, and optional runtime dependencies are installed. LSTM history remains separate and is stored in SQLite per run and astronaut; it uses a 24-sample rolling window at the configured three-second model cadence, resets on incomplete required features or a gap greater than 15 seconds, and retains only the latest 24 samples and analysis responses for idempotency. Configure `SIMULATION_HISTORY_DB`, `LSTM_SAMPLE_PERIOD_SECONDS`, and `LSTM_MAX_GAP_SECONDS` to change these settings.

`AST-001` is also configured. Every successful call recalculates the simulator's 17 generated measurements, assigns a new timestamp and record ID, and returns all 20 contracted indicators. Earth latency, daylight, and social interaction remain explicitly missing. Mood is rounded to an integer; values are bounded by data domains (such as percentages), not clinical reference ranges. `normal` names the baseline scenario and does not imply healthy values.

Version 1.1.0 deliberately replaces the previous read-only pagination behavior: no query parameters are supported, each response has one item, and `next_cursor` is null. Avoid prefetch or automatic retries unless another sample is wanted. Daily totals are newly simulated estimates of the previous completed UTC day on every call, not historical measurements.

Run only one worker. Simulator sequence and scenario selection are held in memory and reset on restart. Analysis forecast history persists in the configured SQLite database. The seed and per-astronaut call sequence reproduce values; timestamps use actual UTC time. Authentication is not implemented. Bind to loopback until local access control is implemented.

The training path uses the exact same baseline means, per-feature spreads, scenario overrides, feature order, and three-second cadence as live simulation. Training windows stay within one astronaut; the LSTM scaler is fit only on each stream's chronological training partition. From the repository root, install optional training dependencies and run:

```powershell
Project/simulated_inputs_app/.venv/Scripts/pip.exe install -r Project/simulated_inputs_app/requirements-ml.txt
Project/simulated_inputs_app/.venv/Scripts/python.exe -m Project.simulated_inputs_app.train_models --rows 10000
```

This writes the three model artifacts and `model-manifest.json` under `model_artifacts/`. The manifest records feature order, cadence, dataset hash, package versions, and synthetic validation metrics. Docker Compose builds the simulator with the matching inference runtime by default; rebuild and restart the simulator after training or replacing artifacts. `INSTALL_ML_RUNTIME=false` can still be used for a smaller rules-only image. Review evaluation metrics before treating outputs as useful. These models and scenarios are synthetic demonstrations, not clinical validation.

API runtime model loading is optional and lazy; model libraries are not imported unless artifact files exist. The base API requirements do not install the training/inference stack.

The inputs API validates outputs against [the simulator JSON Schema](../../Docs/Challenge/simulated-astronaut-inputs.schema.json). Analysis responses are validated against [analysis-response.schema.json](analysis-response.schema.json). The OpenAPI document at `/openapi.json` includes both endpoints. Hosted Swagger/ReDoc pages are disabled so runtime does not fetch CDN assets. No external service is used after dependencies are installed.

Run integration tests from the repository root:

```powershell
Project/simulated_inputs_app/.venv/Scripts/python.exe -m unittest Project.simulated_inputs_app.test_api -v
```
