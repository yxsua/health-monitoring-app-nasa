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

# Formato:
# (alarma_baja, precaucion_baja,
#  normal_min, normal_max,
#  precaucion_alta, alarma_alta)

UMBRALES = {
    "fc (lpm)": (50, 60, 60, 100, 120, 140),
    "pa_sis (mmHg)": (80, 90, 90, 130, 160, 180),
    "pa_dia (mmHg)": (40, 60, 60, 85, 100, 120),
    "spo2 (%)": (80, 90, 95, 100, None, None),
    "temp (°C)": (34, 35, 36, 38, 39, 40),
    "glucosa (mg/dL)": (54, 70, 70, 140, 250, 300),
    "hrv (ms)": (15, 25, 25, 120, 150, 180),
    "sueño (h)": (2, 4, 6, 9, 12, 14),
    "ánimo (1-5)": (None, 2, 3, 5, None, None),
    "ejercicio (min)": (None, 5, 10, 120, 180, 240),
    "radiación (mSv/día)": (None, None, 0, 0.8, 1.5, 3),
    "co2 (ppm)": (None, None, 400, 2000, 3000, 5000),
    "temp_cabina (°C)": (10, 15, 18, 26, 30, 35),
    "humedad (%)": (10, 20, 30, 60, 70, 85),
    "ruido (dBA)": (None, None, 0, 70, 85, 100),
    "presión (kPa)": (80, 90, 95, 105, 110, 120),
    "gravedad (g)": (0, 0.02, 0.05, 0.15, 0.20, 0.30)
}

BASE = {
    "fc (lpm)": (70, 8),
    "pa_sis (mmHg)": (115, 7),
    "pa_dia (mmHg)": (75, 5),
    "spo2 (%)": (98, 0.5),
    "temp (°C)": (36.7, 0.15),
    "glucosa (mg/dL)": (95, 7),
    "hrv (ms)": (65, 8),
    "sueño (h)": (7, 0.5),
    "ánimo (1-5)": (4, 0.3),
    "ejercicio (min)": (30, 5),
    "radiación (mSv/día)": (0.5, 0.1),
    "co2 (ppm)": (1000, 100),
    "temp_cabina (°C)": (22, 0.5),
    "humedad (%)": (45, 3),
    "ruido (dBA)": (40, 3),
    "presión (kPa)": (101, 0.5),
    "gravedad (g)": (0.1, 0.005)
}


def evaluar_variable(variable, valor):

    al, pl, nmin, nmax, ph, ah = UMBRALES[variable]

    # Alarmas
    if al is not None and valor < al:
        return "ALARMA"

    if ah is not None and valor >= ah:
        return "ALARMA"

    # Precauciones
    if pl is not None and valor < pl:
        return "PRECAUCION"

    if ph is not None and valor > ph:
        return "PRECAUCION"

    if nmin is not None and valor < nmin:
        return "PRECAUCION"

    if nmax is not None and valor > nmax:
        return "PRECAUCION"

    return "NORMAL"

def generar_valor(variable, rng, estado="NORMAL"):

    media, desviacion = BASE[variable]

    al, pl, nmin, nmax, ph, ah = UMBRALES[variable]

    if estado == "NORMAL":

        minimo = nmin if nmin is not None else media - 3 * desviacion
        maximo = nmax if nmax is not None else media + 3 * desviacion

        return float(np.clip(
            rng.normal(media, desviacion),
            minimo,
            maximo
        ))

    if estado == "PRECAUCION":

        lados = []

        if pl is not None and nmin is not None:
            lados.append("bajo")

        if ph is not None and nmax is not None:
            lados.append("alto")

        if not lados:
            return float(rng.normal(media, desviacion))

        lado = rng.choice(lados)

        if lado == "bajo":
            return float(rng.uniform(pl, nmin))

        return float(rng.uniform(nmax, ph))

    if estado == "ALARMA":

        lados = []

        if al is not None and pl is not None:
            lados.append("bajo")

        if ah is not None and ph is not None:
            lados.append("alto")

        if not lados:
            return float(rng.normal(media, desviacion))

        lado = rng.choice(lados)

        if lado == "bajo":
            return float(rng.uniform(al - (pl - al), al - 0.01))

        return float(rng.uniform(ah + 0.01, ah + (ah - ph)))

    return float(rng.normal(media, desviacion))


def generar_datos(n=10000, astronauta=None):

    rng = np.random.default_rng(42)

    if astronauta is None:
        astronauta = {
            "id": "AST-001",
            "nombre": "Astronauta",
            "edad": 30,
            "mision": "MISION-01"
        }

    registros = []

    for i in range(n):

        registro = {
            "astronauta_id": astronauta["id"],
            "nombre": astronauta["nombre"],
            "edad": astronauta["edad"],
            "misión": astronauta["mision"],
            "timestamp": pd.Timestamp("2026-01-01")
                         + pd.Timedelta(minutes=i)
        }

        estados = []

        for variable in VARIABLES:

            # Cada variable recibe su propio estado.
            estado = rng.choice(
                ["NORMAL", "PRECAUCION", "ALARMA"],
                p=[0.90, 0.07, 0.03]
            )

            valor = generar_valor(variable, rng, estado)

            registro[variable] = valor
            registro[f"estado_{VARIABLES.index(variable)}"] = estado

            estados.append(estado)

        # Estado general: el de mayor severidad.
        if "ALARMA" in estados:
            registro["escenario"] = "critico"
        elif "PRECAUCION" in estados:
            registro["escenario"] = "precaucion"
        else:
            registro["escenario"] = "normal"

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

    print(f"\nSe generaron {len(df)} registros.")
    print(f"Astronauta: {astronauta['nombre']}")
    print(f"Identificador: {astronauta['id']}")

    return df


if __name__ == "__main__":
    generar_datos()