"""Local simulation API. Run with uvicorn Project.simulated_inputs_app.api:app."""
import copy
import hashlib
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator, FormatChecker

from .simulador_tiempo_real import (
    SCENARIOS, generar_medicion, interpolar_parametros, parametros_escenario,
)
from .analysis_engine import AnalysisEngine

SCENARIO_TRANSITION_SAMPLES = 8
LOGGER = logging.getLogger(__name__)

DOCS = Path(__file__).resolve().parents[2] / "Docs" / "Challenge"
SCHEMA = json.loads((DOCS / "simulated-astronaut-inputs.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
ANALYSIS_SCHEMA = json.loads((Path(__file__).resolve().parent / "analysis-response.schema.json").read_text(encoding="utf-8"))
ANALYSIS_VALIDATOR = Draft202012Validator(ANALYSIS_SCHEMA, format_checker=FormatChecker())
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
    app.state.runs = {"demo-run": {"seed": 42, "scenario_id": "normal", "active_scenario_id": "normal",
        "scenario_transition": None, "scenarios": list(SCENARIOS), "mission": "MISION-01",
        "astronauts": {"A01", "AST-001"}}}
    app.state.sequences = {}
    app.state.lock = Lock()
    app.state.analysis = AnalysisEngine()

    @app.middleware("http")
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def error(status, code, message):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        if request.url.path.endswith("/analysis"):
            return error(422, "invalid_observation", "The request body must be a simulator observation.")
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
            scenario_id = run["scenario_id"]
            transition = run["scenario_transition"]
            if transition is not None:
                transition_step = min(transition["step"] + 1, SCENARIO_TRANSITION_SAMPLES)
                progress = transition_step / SCENARIO_TRANSITION_SAMPLES
                raw = generar_medicion(
                    escenario=scenario_id, rng=random.Random(seed), astronauta_id=astronaut_id,
                    timestamp=now, parametros_inicio=transition["from_parameters"], progreso=progress,
                )
                transition_status = {
                    "active": transition_step < SCENARIO_TRANSITION_SAMPLES,
                    "step": transition_step, "total_steps": SCENARIO_TRANSITION_SAMPLES,
                }
            else:
                transition_step = SCENARIO_TRANSITION_SAMPLES
                raw = generar_medicion(escenario=scenario_id, rng=random.Random(seed), astronauta_id=astronaut_id, timestamp=now)
                transition_status = {"active": False, "step": SCENARIO_TRANSITION_SAMPLES,
                    "total_steps": SCENARIO_TRANSITION_SAMPLES}
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
                "scenario_transition": transition_status,
                "items": [record], "next_cursor": None}
            try:
                VALIDATOR.validate(payload)
            except Exception:
                return error(503, "simulation_unavailable", "Could not produce contract-valid simulation inputs.")
            if transition is not None:
                transition["step"] = transition_step
                if transition_step >= SCENARIO_TRANSITION_SAMPLES:
                    run["active_scenario_id"] = scenario_id
                    run["scenario_transition"] = None
            app.state.sequences[key] = (sequence, now)
            return payload

    @app.get("/api/v1/simulation/runs/{run_id}/scenario")
    def get_scenario(run_id: str):
        run = app.state.runs.get(run_id)
        if run is None:
            return error(404, "run_not_found", "Unknown simulation run.")
        with app.state.lock:
            transition = run["scenario_transition"]
            transition_status = ({"active": True, "step": transition["step"],
                "total_steps": SCENARIO_TRANSITION_SAMPLES} if transition else
                {"active": False, "step": SCENARIO_TRANSITION_SAMPLES,
                 "total_steps": SCENARIO_TRANSITION_SAMPLES})
            return {"run_id": run_id, "scenario_id": run["scenario_id"],
                "available_scenarios": run["scenarios"], "scenario_transition": transition_status}

    @app.put("/api/v1/simulation/runs/{run_id}/scenario")
    def set_scenario(run_id: str, body: dict = Body(...)):
        run = app.state.runs.get(run_id)
        if run is None:
            return error(404, "run_not_found", "Unknown simulation run.")
        scenario_id = body.get("scenario_id")
        if scenario_id not in run["scenarios"]:
            return error(422, "invalid_scenario", "Scenario must be one of the configured simulator scenarios.")
        with app.state.lock:
            if scenario_id != run["scenario_id"]:
                previous_transition = run["scenario_transition"]
                if previous_transition is not None:
                    start_parameters = interpolar_parametros(
                        previous_transition["from_parameters"],
                        previous_transition["to_scenario_id"],
                        previous_transition["step"] / SCENARIO_TRANSITION_SAMPLES,
                    )
                    from_scenario_id = previous_transition["from_scenario_id"]
                else:
                    from_scenario_id = run["active_scenario_id"]
                    start_parameters = parametros_escenario(from_scenario_id)
                run["scenario_transition"] = {
                    "from_scenario_id": from_scenario_id,
                    "from_parameters": start_parameters,
                    "to_scenario_id": scenario_id,
                    "step": 0,
                }
            run["scenario_id"] = scenario_id
            transition_active = run["scenario_transition"] is not None
        return {"run_id": run_id, "scenario_id": scenario_id,
            "transition": {"active": transition_active, "total_steps": SCENARIO_TRANSITION_SAMPLES}}

    @app.post("/api/v1/simulation/runs/{run_id}/astronauts/{astronaut_id}/analysis")
    def analyze(run_id: str, astronaut_id: str, body: dict = Body(...)):
        run = app.state.runs.get(run_id)
        if run is None:
            return error(404, "run_not_found", "Unknown simulation run.")
        if astronaut_id not in run["astronauts"]:
            return error(404, "astronaut_not_found", "Astronaut is not configured in this run.")
        scenario_id = body.get("scenario_id")
        observation = body.get("observation")
        if scenario_id not in run["scenarios"] or not isinstance(observation, dict):
            return error(422, "invalid_observation", "The request must include a configured scenario and one observation.")
        if observation.get("astronaut_id") != astronaut_id:
            return error(422, "observation_subject_mismatch", "The observation does not belong to the requested astronaut.")
        candidate = {
            "schema_version": "1.1.0", "run_id": run_id, "scenario_id": scenario_id,
            "seed": run["seed"], "generator_version": "initial-app-1.1.0",
            "simulation_time": observation.get("observed_at"),
            "scenario_transition": {"active": False, "step": SCENARIO_TRANSITION_SAMPLES,
                "total_steps": SCENARIO_TRANSITION_SAMPLES},
            "items": [observation], "next_cursor": None,
        }
        try:
            VALIDATOR.validate(candidate)
        except Exception:
            return error(422, "invalid_observation", "The submitted observation does not match the simulator contract.")
        try:
            result, _ = app.state.analysis.analyze(run_id, astronaut_id, scenario_id, observation)
        except ValueError as reason:
            if str(reason) == "out_of_order_observation":
                return error(409, "out_of_order_observation", "The observation is older than the latest analyzed sample.")
            return error(422, "invalid_observation", "The submitted observation could not be analyzed.")
        except Exception:
            return error(503, "analysis_unavailable", "The analysis service could not produce a result.")
        try:
            ANALYSIS_VALIDATOR.validate(result)
        except Exception:
            LOGGER.exception("Analysis response contract validation failed.")
            return error(503, "analysis_unavailable", "The analysis service returned a response outside its contract.")
        return result

    generated_openapi = app.openapi
    def openapi():
        if app.openapi_schema is None:
            contract = json.loads((DOCS / "simulated-astronaut-inputs.openapi.json").read_text(encoding="utf-8"))
            generated = generated_openapi()
            contract["paths"].update({path: spec for path, spec in generated["paths"].items() if path.endswith("/analysis") or path.endswith("/scenario")})
            contract.setdefault("components", {}).setdefault("schemas", {}).update(generated.get("components", {}).get("schemas", {}))
            for path, path_spec in contract["paths"].items():
                if path.endswith("/analysis") and "post" in path_spec:
                    operation = path_spec["post"]
                    operation.setdefault("requestBody", {}).setdefault("content", {}).setdefault("application/json", {})["schema"] = {
                        "type": "object", "additionalProperties": False,
                        "required": ["scenario_id", "observation"],
                        "properties": {"scenario_id": {"enum": list(SCENARIOS)}, "observation": copy.deepcopy(SCHEMA["$defs"]["Observation"])},
                    }
                    operation.setdefault("responses", {}).setdefault("200", {}).setdefault("content", {}).setdefault("application/json", {})["schema"] = copy.deepcopy(ANALYSIS_SCHEMA)
                if path.endswith("/scenario") and "put" in path_spec:
                    path_spec["put"].setdefault("requestBody", {}).setdefault("content", {}).setdefault("application/json", {})["schema"] = {
                        "type": "object", "additionalProperties": False, "required": ["scenario_id"],
                        "properties": {"scenario_id": {"enum": list(SCENARIOS)}},
                    }
            app.openapi_schema = contract
        return copy.deepcopy(app.openapi_schema)

    app.openapi = openapi
    return app


app = create_app()
