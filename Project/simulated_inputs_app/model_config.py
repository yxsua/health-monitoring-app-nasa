"""Shared paths and feature order for training and runtime inference."""
import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TRAINING_DATA_PATH = Path(os.getenv("TRAINING_DATA_PATH", str(PACKAGE_DIR / "training_data" / "datos_entrenamiento.csv")))
MODEL_ARTIFACTS_DIR = Path(os.getenv("MODEL_ARTIFACTS_DIR", str(PACKAGE_DIR / "model_artifacts")))

MODEL_FIELDS = [
    "heart_rate", "systolic_pressure", "diastolic_pressure", "spo2",
    "body_temperature", "glucose", "hrv_rmssd", "sleep_duration", "mood",
    "exercise_duration", "radiation_dose_rate", "co2", "cabin_temperature",
    "humidity", "noise", "cabin_pressure", "gravity",
]
