import pandas as pd
import numpy as np
import time

from generador_datos import (
    VARIABLES,
    BASE,
    UMBRALES,
    evaluar_variable,
    generar_valor
)


def generar_medicion(astronauta, variable_alerta=None, nivel=None):

    rng = np.random.default_rng()

    datos = {}

    for variable in VARIABLES:

        if variable == variable_alerta and nivel is not None:
            estado = nivel
        else:
            estado = "NORMAL"

        datos[variable] = generar_valor(
            variable,
            rng,
            estado
        )

    datos["astronauta_id"] = astronauta["id"]
    datos["nombre"] = astronauta["nombre"]
    datos["timestamp"] = pd.Timestamp.now()

    return datos


def iniciar(astronauta):

    print("\nASTRAHEALTH AI - MONITOREO")
    print("Astronauta:", astronauta["nombre"])
    print("Presiona Ctrl+C para detener.")

    print("\nModo de simulación:")
    print("1. Normal")
    print("2. Generar precaución individual")
    print("3. Generar alarma individual")

    opcion = input("Selecciona el modo: ").strip()

    variable_alerta = None
    nivel = None

    if opcion in ["2", "3"]:

        print("\nVariables disponibles:")

        for i, variable in enumerate(VARIABLES):
            print(f"{i + 1}. {variable}")

        seleccion = int(input("\nSelecciona variable: "))

        if seleccion < 1 or seleccion > len(VARIABLES):
            print("Selección inválida.")
            return

        variable_alerta = VARIABLES[seleccion - 1]

        nivel = "PRECAUCION" if opcion == "2" else "ALARMA"

    try:

        while True:

            medicion = generar_medicion(
                astronauta,
                variable_alerta,
                nivel
            )

            print("\nNueva medición:")
            print(medicion)

            yield medicion

            time.sleep(5)

    except KeyboardInterrupt:

        print("\nSimulación detenida.")