
import random
from datetime import datetime, timezone
import time
SAMPLE_PERIOD_SECONDS = 3

BASE = {
    "fc (lpm)": 70,
    "pa_sis (mmHg)": 115,
    "pa_dia (mmHg)": 75,
    "spo2 (%)": 98,
    "temp (°C)": 36.7,
    "glucosa (mg/dL)": 95,
    "hrv (ms)": 65,
    "sueño (h)": 7,
    "ánimo (1-5)": 4,
    "ejercicio (min)": 30,
    "radiación (mSv/día)": 0.5,
    "co2 (ppm)": 1000,
    "temp_cabina (°C)": 22,
    "humedad (%)": 45,
    "ruido (dBA)": 40,
    "presión (kPa)": 101,
    "gravedad (g)": 0.1
}

# One canonical baseline/spread is shared by live simulation and training data.
SIGMA = {variable: abs(value * 0.03) for variable, value in BASE.items()}
SCENARIOS = ("normal", "solar_event", "high_co2", "prolonged_isolation")
SCENARIO_WEIGHTS = (0.7, 0.1, 0.1, 0.1)
SCENARIO_OVERRIDES = {
    "solar_event": {"radiación (mSv/día)": (3.5, 0.35)},
    "high_co2": {"co2 (ppm)": (7000.0, 350.0), "fc (lpm)": (112.0, 5.0)},
    "prolonged_isolation": {"sueño (h)": (5.0, 0.35), "ánimo (1-5)": (1.5, 0.15),
                            "hrv (ms)": (34.0, 3.0), "ejercicio (min)": (10.0, 3.0)},
}

def parametros_escenario(escenario="normal"):
    """Return the configured mean and spread for every simulator signal."""
    return {
        variable: SCENARIO_OVERRIDES.get(escenario, {}).get(variable, (baseline, SIGMA[variable]))
        for variable, baseline in BASE.items()
    }


def interpolar_parametros(parametros_inicio, escenario_destino, progreso):
    """Blend scenario distributions without abruptly switching their means."""
    destino = parametros_escenario(escenario_destino)
    progreso = min(1.0, max(0.0, float(progreso)))
    return {
        variable: (
            parametros_inicio[variable][0] + (destino[variable][0] - parametros_inicio[variable][0]) * progreso,
            parametros_inicio[variable][1] + (destino[variable][1] - parametros_inicio[variable][1]) * progreso,
        )
        for variable in BASE
    }


def generar_medicion(escenario="normal", rng=None, astronauta_id="AST-001", timestamp=None,
                     parametros_inicio=None, progreso=1.0):

    rng = rng or random

    datos = {}

    parametros_objetivo = parametros_escenario(escenario)
    parametros = (interpolar_parametros(parametros_inicio, escenario, progreso)
                  if parametros_inicio is not None else parametros_objetivo)
    for variable, baseline in BASE.items():
        mean, deviation = parametros[variable]
        nuevo = rng.gauss(mean, deviation)
        # Keep the old CLI demonstration modes available to main.py.
        if escenario == "precaucion":
            nuevo += SIGMA[variable] * 3
        elif escenario == "critico":
            nuevo += SIGMA[variable] * 6
        if variable == "ánimo (1-5)":
            nuevo = int(round(min(5, max(1, nuevo))))
        elif variable in ("spo2 (%)", "humedad (%)"):
            nuevo = min(100.0, max(0.0, nuevo))
        else:
            nuevo = max(0.0, nuevo)
        datos[variable] = float(nuevo)

    datos["astronauta_id"] = astronauta_id
    datos["timestamp"] = timestamp or datetime.now(timezone.utc)

    return datos

def iniciar():

    print("ASTRAHEALTH AI - MONITOREO")
    print("Presiona Ctrl+C para detener.")

    try:
        while True:

            # Cambiar a precaucion o critico
            # para probar las alertas.
            medicion = generar_medicion("normal")

            print("\nNueva medición:")
            print(medicion)

            yield medicion

            time.sleep(SAMPLE_PERIOD_SECONDS)

    except KeyboardInterrupt:
        print("Simulación detenida.")


