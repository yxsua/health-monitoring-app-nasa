# Local simulated inputs API

From the repository root, create a Python virtual environment, install `Project/simulated_inputs_app/requirements-dev.txt`, and run:

```powershell
Project/simulated_inputs_app/.venv/Scripts/python.exe -m uvicorn Project.simulated_inputs_app.api:app --host 127.0.0.1 --port 8000
```

Request a fresh sample:

```http
GET http://127.0.0.1:8000/api/v1/simulation/runs/demo-run/astronauts/A01/inputs
```

`AST-001` is also configured. Every successful call recalculates the existing simulator's 17 measurements, assigns a new timestamp and record ID, and returns all 20 contracted indicators. Earth latency, daylight, and social interaction remain explicitly missing. Mood is rounded to an integer; values are bounded by data domains (such as percentages), not clinical reference ranges. The original generator baselines are retained. `normal` names its generator mode and does not imply healthy values.

Version 1.1.0 deliberately replaces the previous read-only pagination behavior: no query parameters are supported, each response has one item, and `next_cursor` is null. Avoid prefetch or automatic retries unless another sample is wanted. Daily totals are newly simulated estimates of the previous completed UTC day on every call, not historical measurements.

Run only one worker. Sequence state is held in memory and resets on restart. The seed and per-astronaut call sequence reproduce values; timestamps use actual UTC time. Persistent history, additional scenario controls, and authentication are not implemented. Bind to loopback until local access control is implemented.

The API uses the existing measurement generator without loading or retraining Isolation Forest or LSTM models. The original `main.py` console workflow is retained and needs its separate pandas/numpy/scikit-learn/TensorFlow dependencies. API requirements do not install that training stack.

The API validates outputs against [the JSON Schema](../../Docs/Challenge/simulated-astronaut-inputs.schema.json) and serves [the OpenAPI contract](../../Docs/Challenge/simulated-astronaut-inputs.openapi.json) at `/openapi.json`. Schemas are loaded from the repository's `Docs/Challenge` folder; include that folder when packaging the app. Hosted Swagger/ReDoc pages are disabled so runtime does not fetch CDN assets. No external service is used after dependencies are installed.

Run integration tests from the repository root:

```powershell
Project/simulated_inputs_app/.venv/Scripts/python.exe -m unittest Project.simulated_inputs_app.test_api -v
```
