"""Local simulation API. Run with uvicorn Project.simulated_inputs_app.api:app."""
import copy
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator, FormatChecker

from .simulador_tiempo_real import generar_medicion

DOCS = Path(__file__).resolve().parents[2] / "Docs" / "Challenge"
SCHEMA = json.loads((DOCS / "simulated-astronaut-inputs.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
MAPPING = {
    "physiological": [
        ("heart_rate", "fc (lpm)"), ("systolic_pressure", "pa_sis (mmHg)"),
        ("diastolic_pressure", "pa_dia (mmHg)"), ("spo2", "spo2 (%)"),
        ("body_temperature", "temp (°C)"), ("glucose", "glucosa (mg/dL)"),
        ("hrv_rmssd", "hrv (ms)")],
    "self_assessment": [("sleep_duration", "sueño (h)"), ("mood", "ánimo (1-5)"),
                        ("exercise_duration", "ejercicio (min)")],
    "environment": [("radiation_dose_rate", "radiación (mSv/día)"),
        ("co2", "co2 (ppm)"), ("cabin_temperature", "temp_cabina (°C)"),
        ("humidity", "humedad (%)"), ("noise", "ruido (dBA)"),
        ("cabin_pressure", "presión (kPa)"), ("gravity", "gravedad (g)"),
        ("earth_latency", None), ("simulated_daylight_duration", None),
        ("social_interaction_duration", None)]}


def utc(value):
    return value.isoformat().replace("+00:00", "Z")


def create_app():
    app = FastAPI(title="Simulated Astronaut Inputs API", version="1.1.0",
                  docs_url=None, redoc_url=None)
    # Fixed initial run; state is process-local, intentionally not persisted yet.
    app.state.runs = {"demo-run": {"seed": 42, "scenario_id": "normal",
        "mission": "MISION-01", "astronauts": {"A01", "AST-001"}}}
    app.state.sequences = {}
    app.state.lock = Lock()

    @app.middleware("http")
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def error(status, code, message):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error(422, "invalid_query", "Invalid request parameters.")

    @app.get("/api/v1/simulation/runs/{run_id}/astronauts/{astronaut_id}/inputs")
    def inputs(run_id: str, astronaut_id: str, request: Request):
        if request.query_params:
            return error(422, "invalid_query", "This endpoint accepts no query parameters; each call generates one sample.")
        run = app.state.runs.get(run_id)
        if run is None:
            return error(404, "run_not_found", "Unknown simulation run.")
        if astronaut_id not in run["astronauts"]:
            return error(404, "astronaut_not_found", "Astronaut is not configured in this run.")
        with app.state.lock:
            key = (run_id, astronaut_id)
            previous = app.state.sequences.get(key)
            sequence = previous[0] + 1 if previous else 1
            now = datetime.now(timezone.utc)
            if previous and now <= previous[1]:
                now = previous[1] + timedelta(microseconds=1)
            # Stable independent streams: other astronauts' requests do not affect values.
            seed = hashlib.sha256(f"{run['seed']}:{run_id}:{astronaut_id}:{sequence}".encode()).digest()
            raw = generar_medicion(rng=random.Random(seed))
            timestamp = utc(now)
            day_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            record = {"record_id": f"{astronaut_id}-{sequence}-{timestamp}",
                "astronaut_id": astronaut_id, "observed_at": timestamp,
                "mission": run["mission"], "source": "simulated",
                "context": {"activity": "unknown", "fasting": None, "hrv_baseline_ms": None}}
            for group, fields in MAPPING.items():
                record[group] = {}
                for name, source in fields:
                    properties = SCHEMA["$defs"]["Observation"]["properties"][group]["properties"][name]["properties"]
                    unit = properties["unit"]["const"]
                    value = raw[source] if source else None
                    if value is not None:
                        bounds = properties["value"]
                        value = max(bounds.get("minimum", float("-inf")), min(bounds.get("maximum", float("inf")), value))
                        value = int(round(value)) if name == "mood" else round(value, 4)
                    daily = unit in ("h/day", "min/day") and value is not None
                    record[group][name] = {"value": value, "unit": unit,
                        "observed_at": timestamp if value is not None else None,
                        "quality": "valid" if value is not None else "missing",
                        "period_start": utc(day_end - timedelta(days=1)) if daily else None,
                        "period_end": utc(day_end) if daily else None}
            payload = {"schema_version": "1.1.0", "run_id": run_id,
                "scenario_id": run["scenario_id"], "seed": run["seed"],
                "generator_version": "initial-app-1.1.0", "simulation_time": timestamp,
                "items": [record], "next_cursor": None}
            try:
                VALIDATOR.validate(payload)
            except Exception:
                return error(503, "simulation_unavailable", "Could not produce contract-valid simulation inputs.")
            app.state.sequences[key] = (sequence, now)
            return payload

    def openapi():
        if app.openapi_schema is None:
            app.openapi_schema = json.loads((DOCS / "simulated-astronaut-inputs.openapi.json").read_text(encoding="utf-8"))
        return copy.deepcopy(app.openapi_schema)

    app.openapi = openapi
    return app


app = create_app()
