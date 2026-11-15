"""Create a deterministic, scenario-labelled training set using the live sampler."""
import random
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    from .model_config import TRAINING_DATA_PATH
    from .simulador_tiempo_real import SCENARIOS, SCENARIO_WEIGHTS, SAMPLE_PERIOD_SECONDS, generar_medicion
except ImportError:  # Support the legacy `python main.py` console entry point.
    from model_config import TRAINING_DATA_PATH
    from simulador_tiempo_real import SCENARIOS, SCENARIO_WEIGHTS, SAMPLE_PERIOD_SECONDS, generar_medicion

DB_PATH = TRAINING_DATA_PATH.with_suffix(".db")
VARIABLES = [
    "fc (lpm)", "pa_sis (mmHg)", "pa_dia (mmHg)", "spo2 (%)", "temp (°C)",
    "glucosa (mg/dL)", "hrv (ms)", "sueño (h)", "ánimo (1-5)", "ejercicio (min)",
    "radiación (mSv/día)", "co2 (ppm)", "temp_cabina (°C)", "humedad (%)",
    "ruido (dBA)", "presión (kPa)", "gravedad (g)",
]
ASTRONAUT_COUNT = 10
SCENARIO_SEGMENT_SAMPLES = 120


def generar_datos(n=10000):
    rng = random.Random(42)
    TRAINING_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    registros = []
    samples_per_astronaut, remainder = divmod(n, ASTRONAUT_COUNT)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    for astronaut_index in range(ASTRONAUT_COUNT):
        astronaut_id = f"AST-{astronaut_index + 1:03d}"
        count = samples_per_astronaut + (1 if astronaut_index < remainder else 0)
        scenarios = []
        for segment_start in range(0, count, SCENARIO_SEGMENT_SAMPLES):
            scenario = rng.choices(SCENARIOS, weights=SCENARIO_WEIGHTS, k=1)[0]
            segment_length = min(SCENARIO_SEGMENT_SAMPLES, count - segment_start)
            scenarios.extend([scenario] * segment_length)

        for index, scenario in enumerate(scenarios):
            timestamp = start + timedelta(seconds=index * SAMPLE_PERIOD_SECONDS)
            measurement = generar_medicion(
                scenario, rng=rng, astronauta_id=astronaut_id, timestamp=timestamp,
            )
            record = {
                "astronauta_id": astronaut_id,
                "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                "misión": "MISION-01",
                "escenario": scenario,
            }
            record.update({variable: measurement[variable] for variable in VARIABLES})
            registros.append(record)

    dataframe = pd.DataFrame(registros)
    dataframe.to_csv(TRAINING_DATA_PATH, index=False)
    with sqlite3.connect(DB_PATH) as connection:
        dataframe.to_sql("registros", connection, if_exists="replace", index=False)
    print(f"Base de datos generada: {len(dataframe)} muestras a {SAMPLE_PERIOD_SECONDS}s.")
    print(f"CSV: {TRAINING_DATA_PATH}")
    return dataframe


if __name__ == "__main__":
    generar_datos()
