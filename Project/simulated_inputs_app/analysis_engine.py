"""Analysis of one simulator observation plus a bounded LSTM history."""
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from threading import RLock

from .alert_engine import CONTRATO, triage_payload
from .model_config import MODEL_ARTIFACTS_DIR, MODEL_FIELDS


MODEL_VARIABLES = [CONTRATO[field] for field in MODEL_FIELDS]
UNITS = {
    "heart_rate": "bpm", "systolic_pressure": "mmHg", "diastolic_pressure": "mmHg",
    "spo2": "%", "body_temperature": "degC", "glucose": "mg/dL", "hrv_rmssd": "ms",
    "sleep_duration": "h/day", "mood": "score_1_5", "exercise_duration": "min/day",
    "radiation_dose_rate": "mSv/day", "co2": "ppm", "cabin_temperature": "degC",
    "humidity": "%", "noise": "dBA", "cabin_pressure": "kPa", "gravity": "g",
}
FIELD_BY_VARIABLE = {variable: field for field, variable in zip(MODEL_FIELDS, MODEL_VARIABLES)}
SEVERITY = {"NORMAL": "normal", "PRECAUCION": "caution", "ADVERTENCIA": "warning", "CRITICO": "critical"}
LEVEL_SEVERITY = {0: "normal", 1: "caution", 2: "warning", 3: "critical"}


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _field_reading(observation, field):
    for group in ("physiological", "self_assessment", "environment"):
        reading = observation.get(group, {}).get(field)
        if reading is not None:
            return reading
    return None


def _features(observation):
    values = {}
    quality_counts = {"valid": 0, "missing": 0, "invalid": 0}
    for field in MODEL_FIELDS:
        reading = _field_reading(observation, field)
        quality = reading.get("quality", "missing") if reading else "missing"
        if quality not in quality_counts:
            quality = "invalid"
        quality_counts[quality] += 1
        value = reading.get("value") if reading else None
        if quality == "valid" and isinstance(value, (int, float)):
            values[field] = float(value)
    complete = len(values) == len(MODEL_FIELDS)
    return values, quality_counts, complete


def _reason_code(reason):
    if reason in {"artifact_missing", "manifest_missing", "manifest_invalid", "feature_order_mismatch", "window_mismatch", "cadence_mismatch", "dependencies_missing", "dependency_version_mismatch"}:
        return reason
    return "inference_error"


class ModelRuntime:
    """Optional artifact loader. Model libraries are imported only when artifacts exist."""

    def __init__(self):
        artifact_root = Path(os.getenv("MODEL_ARTIFACTS_DIR", str(MODEL_ARTIFACTS_DIR)))
        manifest_path = Path(os.getenv("MODEL_MANIFEST_PATH", str(artifact_root / "model-manifest.json")))
        self.manifest = {}
        self.manifest_reason = "manifest_missing"
        if manifest_path.is_file():
            try:
                self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if (
                    not isinstance(self.manifest, dict)
                    or not isinstance(self.manifest.get("features"), list)
                    or not isinstance(self.manifest.get("runtime_versions"), dict)
                    or not isinstance(self.manifest.get("isolation_forest"), dict)
                    or not isinstance(self.manifest.get("lstm"), dict)
                ):
                    raise ValueError("Invalid model manifest structure")
                self.manifest_reason = None
            except Exception:
                self.manifest = {}
                self.manifest_reason = "manifest_invalid"

        self.anomaly = None
        self.anomaly_reason = "artifact_missing"
        self.anomaly_version = os.getenv("ANOMALY_MODEL_VERSION") or self.manifest.get("isolation_forest", {}).get("version")
        anomaly_path = Path(os.getenv("ISOLATION_FOREST_PATH", str(artifact_root / "isolation_forest.pkl")))
        if anomaly_path.is_file():
            if self.manifest_reason:
                self.anomaly_reason = self.manifest_reason
            elif self.manifest.get("features") != MODEL_FIELDS:
                self.anomaly_reason = "feature_order_mismatch"
            else:
                try:
                    import joblib
                    self.anomaly = joblib.load(anomaly_path)
                    self.anomaly_reason = None
                    self.anomaly_version = self.anomaly_version or "unversioned"
                except ImportError:
                    self.anomaly_reason = "dependencies_missing"
                except Exception:
                    self.anomaly_reason = "inference_error"

        self.forecast = None
        self.scaler = None
        self.forecast_reason = "artifact_missing"
        self.forecast_version = os.getenv("FORECAST_MODEL_VERSION") or self.manifest.get("lstm", {}).get("version")
        manifest_period = self.manifest.get("sample_period_seconds")
        configured_period = int(os.getenv("LSTM_SAMPLE_PERIOD_SECONDS", str(manifest_period or 3)))
        self.sample_period_seconds = max(1, configured_period)
        forecast_path = Path(os.getenv("LSTM_MODEL_PATH", str(artifact_root / "lstm_model.keras")))
        scaler_path = Path(os.getenv("LSTM_SCALER_PATH", str(artifact_root / "scaler.pkl")))
        if forecast_path.is_file() and scaler_path.is_file():
            if self.manifest_reason:
                self.forecast_reason = self.manifest_reason
            elif self.manifest.get("features") != MODEL_FIELDS:
                self.forecast_reason = "feature_order_mismatch"
            elif self.manifest.get("forecast_window_samples") != 24:
                self.forecast_reason = "window_mismatch"
            elif manifest_period != self.sample_period_seconds:
                self.forecast_reason = "cadence_mismatch"
            elif (runtime_error := self._runtime_error(("numpy", "scikit-learn", "joblib", "tensorflow"))):
                self.forecast_reason = runtime_error
            else:
                try:
                    import joblib
                    from tensorflow.keras.models import load_model
                    self.forecast = load_model(forecast_path)
                    self.scaler = joblib.load(scaler_path)
                    self.forecast_reason = None
                    self.forecast_version = self.forecast_version or "unversioned"
                except ImportError:
                    self.forecast_reason = "dependencies_missing"
                except Exception:
                    self.forecast_reason = "inference_error"

        if anomaly_path.is_file() and not self.anomaly_reason:
            runtime_error = self._runtime_error(("numpy", "scikit-learn", "joblib", "pandas"))
            if runtime_error:
                self.anomaly = None
                self.anomaly_reason = runtime_error

    def _runtime_error(self, packages):
        expected = self.manifest.get("runtime_versions", {})
        for package in packages:
            if not expected.get(package):
                continue
            try:
                actual = version(package)
            except PackageNotFoundError:
                return "dependencies_missing"
            if actual != expected[package]:
                return "dependency_version_mismatch"
        return None

    def score_anomaly(self, features):
        if self.anomaly is None:
            return None
        import pandas as pd
        row = pd.DataFrame([[features[field] for field in MODEL_FIELDS]], columns=MODEL_VARIABLES)
        prediction = int(self.anomaly.predict(row)[0])
        score = float(self.anomaly.decision_function(row)[0])
        return {"is_anomaly": prediction == -1, "score": score}

    def predict_next(self, rows):
        if self.forecast is None or self.scaler is None:
            return None
        import numpy as np
        matrix = np.asarray([[row[field] for field in MODEL_FIELDS] for row in rows], dtype=float)
        scaled = self.scaler.transform(matrix)
        predicted = self.forecast.predict(scaled.reshape(1, len(rows), len(MODEL_FIELDS)), verbose=0)
        return self.scaler.inverse_transform(predicted)[0].tolist()


class AnalysisEngine:
    """Serializes analysis with bounded alert and forecast history per stream."""

    def __init__(self, database_path=None, models=None):
        default_path = os.getenv("SIMULATION_HISTORY_DB", str(Path(tempfile.gettempdir()) / "simulation-analysis.sqlite3"))
        self.database_path = database_path or default_path
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.database_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = RLock()
        self.models = models or ModelRuntime()
        self.rule_window_size = 8
        self.window_size = 24
        configured_period = os.getenv("LSTM_SAMPLE_PERIOD_SECONDS")
        self.sample_period_seconds = max(1, int(configured_period or getattr(self.models, "sample_period_seconds", 3)))
        self.max_gap_seconds = max(self.sample_period_seconds * 1.5, int(os.getenv("LSTM_MAX_GAP_SECONDS", "15")))
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS analysis_results (
                run_id TEXT NOT NULL, astronaut_id TEXT NOT NULL, record_id TEXT NOT NULL,
                observed_at TEXT NOT NULL, response_json TEXT NOT NULL,
                PRIMARY KEY (run_id, astronaut_id, record_id)
            );
            CREATE TABLE IF NOT EXISTS forecast_history (
                run_id TEXT NOT NULL, astronaut_id TEXT NOT NULL, record_id TEXT NOT NULL,
                observed_at TEXT NOT NULL, features_json TEXT NOT NULL,
                PRIMARY KEY (run_id, astronaut_id, record_id)
            );
            CREATE INDEX IF NOT EXISTS forecast_history_stream_time
                ON forecast_history (run_id, astronaut_id, observed_at);
            CREATE TABLE IF NOT EXISTS rule_history (
                run_id TEXT NOT NULL, astronaut_id TEXT NOT NULL, record_id TEXT NOT NULL,
                observed_at TEXT NOT NULL, observation_json TEXT NOT NULL,
                PRIMARY KEY (run_id, astronaut_id, record_id)
            );
            CREATE INDEX IF NOT EXISTS rule_history_stream_time
                ON rule_history (run_id, astronaut_id, observed_at);
        """)

    def _rule_window_observation(self, observations):
        """Average valid numeric values from the last rule-window observations."""
        latest = json.loads(observations[-1]["observation_json"])
        for group in ("physiological", "self_assessment", "environment"):
            for field, latest_reading in latest.get(group, {}).items():
                values = []
                qualities = []
                for row in observations:
                    item = json.loads(row["observation_json"])
                    reading = item.get(group, {}).get(field)
                    if reading is None:
                        continue
                    quality = reading.get("quality", "missing")
                    qualities.append(quality)
                    value = reading.get("value")
                    if quality == "valid" and isinstance(value, (int, float)):
                        values.append(float(value))
                if values:
                    latest_reading["value"] = sum(values) / len(values)
                    latest_reading["quality"] = "valid"
                else:
                    latest_reading["value"] = None
                    latest_reading["quality"] = "invalid" if "invalid" in qualities else "missing"
        return latest

    def _rule_result(self, observation, quality_counts):
        triage = triage_payload({"items": [observation]})
        alerts = []
        for alert in triage["alertas"]:
            variable_names = alert["variable"].split("+")
            evidence = []
            for variable in variable_names:
                field = FIELD_BY_VARIABLE.get(variable)
                if field:
                    reading = _field_reading(observation, field) or {}
                    evidence.append({
                        "field": field,
                        "value": reading.get("value"),
                        "unit": reading.get("unit", UNITS[field]),
                        "quality": reading.get("quality", "missing"),
                    })
            normalized = unicodedata.normalize("NFKD", alert["variable"]).encode("ascii", "ignore").decode("ascii")
            code = re.sub(r"[^A-Z0-9]+", "_", normalized.upper()).strip("_")
            alerts.append({
                "code": code,
                "severity": LEVEL_SEVERITY.get(alert["nivel_num"], "caution"),
                "system": alert["sistema"].lower(),
                "message": alert["mensaje"],
                "evidence": evidence,
                "procedure_id": None,
            })
        return {
            "status": "available",
            "version": "demo-rules-v1",
            "overall_level": SEVERITY.get(triage["estado_global"], "normal"),
            "alerts": alerts,
            "input_quality": quality_counts,
        }

    def _anomaly_result(self, features, complete):
        base = {"model_id": "isolation-forest", "model_version": self.models.anomaly_version,
                "is_anomaly": None, "score": None,
                "score_meaning": "Higher decision-function scores are more typical; lower scores are more anomalous."}
        if not complete:
            return {**base, "status": "insufficient_data", "reason": "required_features_missing"}
        if self.models.anomaly is None:
            return {**base, "status": "unavailable", "reason": _reason_code(self.models.anomaly_reason)}
        try:
            result = self.models.score_anomaly(features)
            return {**base, "status": "available", "reason": None, **result}
        except Exception:
            return {**base, "status": "unavailable", "reason": "inference_error"}

    def _forecast_result(self, run_id, astronaut_id, observation, features, complete):
        rows = self.db.execute(
            "SELECT observed_at, features_json FROM forecast_history WHERE run_id=? AND astronaut_id=? ORDER BY observed_at",
            (run_id, astronaut_id),
        ).fetchall()
        window = [{"observed_at": row["observed_at"], **json.loads(row["features_json"])} for row in rows]
        base = {
            "model_id": "lstm-next-step", "model_version": self.models.forecast_version,
            "window_required": self.window_size, "window_available": len(window),
            "sample_period_seconds": self.sample_period_seconds,
            "horizon_seconds": self.sample_period_seconds if self.models.forecast is not None else None,
            "target_time": None, "values": None,
        }
        if not complete:
            return {**base, "status": "insufficient_data", "reason": "required_features_missing"}
        if self.models.forecast is None or self.models.scaler is None:
            return {**base, "status": "unavailable", "reason": _reason_code(self.models.forecast_reason)}
        if len(window) < self.window_size:
            return {**base, "status": "warming_up", "reason": None}
        try:
            predicted = self.models.predict_next(window[-self.window_size:])
            target = _utc(window[-1]["observed_at"]) + timedelta(seconds=self.sample_period_seconds)
            values = {
                field: {"value": round(float(value), 4), "unit": UNITS[field]}
                for field, value in zip(MODEL_FIELDS, predicted)
            }
            return {**base, "status": "available", "target_time": _utc_text(target), "values": values, "reason": None}
        except Exception:
            return {**base, "status": "unavailable", "reason": "inference_error", "horizon_seconds": None}

    def analyze(self, run_id, astronaut_id, scenario_id, observation):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                cached = self.db.execute(
                    "SELECT response_json FROM analysis_results WHERE run_id=? AND astronaut_id=? AND record_id=?",
                    (run_id, astronaut_id, observation["record_id"]),
                ).fetchone()
                if cached:
                    self.db.commit()
                    return json.loads(cached["response_json"]), False

                latest = self.db.execute(
                    "SELECT observed_at FROM analysis_results WHERE run_id=? AND astronaut_id=? ORDER BY observed_at DESC LIMIT 1",
                    (run_id, astronaut_id),
                ).fetchone()
                observed_at = _utc(observation["observed_at"])
                if latest and observed_at <= _utc(latest["observed_at"]):
                    raise ValueError("out_of_order_observation")

                features, quality_counts, complete = _features(observation)
                last_forecast = self.db.execute(
                    "SELECT observed_at FROM forecast_history WHERE run_id=? AND astronaut_id=? ORDER BY observed_at DESC LIMIT 1",
                    (run_id, astronaut_id),
                ).fetchone()
                if not complete:
                    self.db.execute("DELETE FROM forecast_history WHERE run_id=? AND astronaut_id=?", (run_id, astronaut_id))
                else:
                    elapsed = observed_at - _utc(last_forecast["observed_at"]) if last_forecast else None
                    if elapsed and elapsed.total_seconds() > self.max_gap_seconds:
                        self.db.execute("DELETE FROM forecast_history WHERE run_id=? AND astronaut_id=?", (run_id, astronaut_id))
                        last_forecast = None
                        elapsed = None
                    if last_forecast is None or (elapsed and elapsed.total_seconds() >= self.sample_period_seconds):
                        self.db.execute(
                            "INSERT INTO forecast_history VALUES (?, ?, ?, ?, ?)",
                            (run_id, astronaut_id, observation["record_id"], observation["observed_at"], json.dumps(features)),
                        )
                        self.db.execute(
                            "DELETE FROM forecast_history WHERE run_id=? AND astronaut_id=? AND record_id NOT IN "
                            "(SELECT record_id FROM forecast_history WHERE run_id=? AND astronaut_id=? ORDER BY observed_at DESC LIMIT ?)",
                            (run_id, astronaut_id, run_id, astronaut_id, self.window_size),
                        )

                self.db.execute(
                    "INSERT INTO rule_history VALUES (?, ?, ?, ?, ?)",
                    (run_id, astronaut_id, observation["record_id"], observation["observed_at"], json.dumps(observation)),
                )
                self.db.execute(
                    "DELETE FROM rule_history WHERE run_id=? AND astronaut_id=? AND record_id NOT IN "
                    "(SELECT record_id FROM rule_history WHERE run_id=? AND astronaut_id=? ORDER BY observed_at DESC LIMIT ?)",
                    (run_id, astronaut_id, run_id, astronaut_id, self.rule_window_size),
                )
                rule_window = self.db.execute(
                    "SELECT observation_json FROM rule_history WHERE run_id=? AND astronaut_id=? "
                    "ORDER BY observed_at DESC LIMIT ?",
                    (run_id, astronaut_id, self.rule_window_size),
                ).fetchall()
                rule_window = list(reversed(rule_window))
                smoothed_observation = self._rule_window_observation(rule_window)
                rules = self._rule_result(smoothed_observation, quality_counts)
                rules["window_size"] = self.rule_window_size
                rules["window_available"] = len(rule_window)
                anomaly = self._anomaly_result(features, complete)
                forecast = self._forecast_result(run_id, astronaut_id, observation, features, complete)
                statuses = (rules["status"], anomaly["status"], forecast["status"])
                overall = "complete" if all(status == "available" for status in statuses) else "partial"
                response = {
                    "contract_version": "1.1.0",
                    "run_id": run_id,
                    "astronaut_id": astronaut_id,
                    "scenario_id": scenario_id,
                    "record_id": observation["record_id"],
                    "observed_at": observation["observed_at"],
                    "analyzed_at": _utc_text(datetime.now(timezone.utc)),
                    "analysis_status": overall,
                    "rules": rules,
                    "anomaly": anomaly,
                    "forecast": forecast,
                }
                self.db.execute(
                    "INSERT INTO analysis_results VALUES (?, ?, ?, ?, ?)",
                    (run_id, astronaut_id, observation["record_id"], observation["observed_at"], json.dumps(response)),
                )
                self.db.execute(
                    "DELETE FROM analysis_results WHERE run_id=? AND astronaut_id=? AND record_id NOT IN "
                    "(SELECT record_id FROM analysis_results WHERE run_id=? AND astronaut_id=? ORDER BY observed_at DESC LIMIT 24)",
                    (run_id, astronaut_id, run_id, astronaut_id),
                )
                self.db.commit()
                return response, True
            except Exception:
                self.db.rollback()
                raise
