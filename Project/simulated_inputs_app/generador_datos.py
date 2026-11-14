
import pandas as pd
import numpy as np
import sqlite3

EXCEL = "modelo_DatosAstronautas.xlsx"
DB = "astronautas.db"

VARIABLES = [
    "fc (lpm)", "pa_sis (mmHg)", "pa_dia (mmHg)",
    "spo2 (%)", "temp (°C)", "glucosa (mg/dL)",
    "hrv (ms)", "sueño (h)", "ánimo (1-5)",
    "ejercicio (min)", "radiación (mSv/día)",
    "co2 (ppm)", "temp_cabina (°C)",
    "humedad (%)", "ruido (dBA)",
    "presión (kPa)", "gravedad (g)"
]

def generar_datos(n=10000):
    rng = np.random.default_rng(42)

    # Rangos iniciales de simulación.
    # Sustituir por los valores exactos del Excel.
    rangos = {
        "fc (lpm)": (70, 12),
        "pa_sis (mmHg)": (115, 10),
        "pa_dia (mmHg)": (75, 8),
        "spo2 (%)": (98, 1),
        "temp (°C)": (36.7, 0.3),
        "glucosa (mg/dL)": (95, 10),
        "hrv (ms)": (65, 10),
        "sueño (h)": (7, 1),
        "ánimo (1-5)": (4, 0.5),
        "ejercicio (min)": (30, 10),
        "radiación (mSv/día)": (0.5, 0.2),
        "co2 (ppm)": (1000, 100),
        "temp_cabina (°C)": (22, 1),
        "humedad (%)": (45, 5),
        "ruido (dBA)": (40, 5),
        "presión (kPa)": (101, 1),
        "gravedad (g)": (0.1, 0.02)
    }

    registros = []

    escenarios = ["normal", "precaucion", "critico"]

    for i in range(n):
        escenario = rng.choice(
            escenarios,
            p=[0.70, 0.20, 0.10]
        )

        astronauta = f"AST-{rng.integers(1, 11):03d}"

        registro = {
            "astronauta_id": astronauta,
            "timestamp": pd.Timestamp("2026-01-01")
                         + pd.Timedelta(minutes=i),
            "misión": "MISION-01",
            "escenario": escenario
        }

        for variable in VARIABLES:
            media, desviacion = rangos[variable]

            valor = rng.normal(media, desviacion)

            if escenario == "precaucion":
                valor += rng.choice([-1, 1]) * desviacion * 2

            elif escenario == "critico":
                valor += rng.choice([-1, 1]) * desviacion * 4

            registro[variable] = valor

        registros.append(registro)

    df = pd.DataFrame(registros)

    df.to_csv("datos_entrenamiento.csv", index=False)

    with sqlite3.connect(DB) as conexion:
        df.to_sql(
            "registros",
            conexion,
            if_exists="replace",
            index=False
        )

    print("Base de datos generada:", len(df), "registros")

if __name__ == "__main__":
    generar_datos()

