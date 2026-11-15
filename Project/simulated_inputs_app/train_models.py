"""Generate aligned three-second training data, train both models, and write a manifest."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version

from .generador_datos import generar_datos
from .isolation_forest import entrenar as entrenar_anomaly
from .lstm_model import entrenar as entrenar_forecast, SAMPLE_PERIOD_SECONDS, VENTANA
from .model_config import MODEL_ARTIFACTS_DIR, MODEL_FIELDS, TRAINING_DATA_PATH


def _package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def train(rows=10000):
    dataframe = generar_datos(rows)
    anomaly_metrics = entrenar_anomaly()
    forecast_metrics = entrenar_forecast()
    digest = hashlib.sha256(TRAINING_DATA_PATH.read_bytes()).hexdigest()
    timestamp_version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    model_version = os.getenv("MODEL_VERSION", f"sim-demo-{timestamp_version}")
    manifest = {
        "manifest_version": "1.0.0",
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "training_data": {
            "path": TRAINING_DATA_PATH.name,
            "sha256": digest,
            "rows": int(len(dataframe)),
            "scenario_counts": {key: int(value) for key, value in dataframe["escenario"].value_counts().items()},
            "source": "shared live simulation generator; synthetic demonstration data",
        },
        "features": MODEL_FIELDS,
        "sample_period_seconds": SAMPLE_PERIOD_SECONDS,
        "forecast_window_samples": VENTANA,
        "forecast_horizon_steps": 1,
        "isolation_forest": {"file": "isolation_forest.pkl", "version": model_version},
        "lstm": {"file": "lstm_model.keras", "scaler_file": "scaler.pkl", "version": model_version},
        "runtime_versions": {
            name: _package_version(name)
            for name in ("numpy", "pandas", "scikit-learn", "joblib", "tensorflow")
        },
        "evaluation": {
            "isolation_forest": anomaly_metrics,
            "lstm": forecast_metrics,
            "note": "Synthetic training and scenario evaluation only; not clinically validated.",
        },
    }
    MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = MODEL_ARTIFACTS_DIR / "model-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Model artifacts and manifest saved to {MODEL_ARTIFACTS_DIR}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10000, help="Total synthetic observations across astronauts.")
    train(parser.parse_args().rows)
