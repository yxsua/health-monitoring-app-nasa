
import random
from datetime import datetime, timezone
import time

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

def generar_medicion(escenario="normal", rng=None):

    rng = rng or random

    datos = {}

    for variable in BASE:

        valor = BASE[variable]

        desviacion = abs(valor * 0.03)

        nuevo = rng.gauss(valor, desviacion)

        if escenario == "precaucion":
            nuevo += desviacion * 3

        elif escenario == "critico":
            nuevo += desviacion * 6

        datos[variable] = float(nuevo)

    datos["astronauta_id"] = "AST-001"

    datos["timestamp"] = datetime.now(timezone.utc)

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

            time.sleep(5)

    except KeyboardInterrupt:
        print("Simulación detenida.")


