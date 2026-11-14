import pandas as pd
import time

from generador_datos import (
    VARIABLES,
    SimuladorFisiologico,
    INTERVALO_S,
    DURACION_RAMPA_S
)


def elegir_modo(simulador):

    print("\nModo de simulación:")
    print("1. Normal")
    print("2. Generar precaución individual")
    print("3. Generar alarma individual")

    opcion = input("Selecciona el modo: ").strip()

    if opcion not in ["2", "3"]:
        return

    nivel = "PRECAUCION" if opcion == "2" else "ALARMA"

    while True:

        print("\nVariables disponibles:")

        for i, variable in enumerate(VARIABLES):
            print(f"{i + 1}. {variable}")

        try:
            seleccion = int(input("\nSelecciona variable: "))
        except ValueError:
            print("Escribe un número.")
            continue

        if seleccion < 1 or seleccion > len(VARIABLES):
            print("Selección inválida.")
            continue

        variable = VARIABLES[seleccion - 1]

        if simulador.activar_alerta(variable, nivel):

            print(
                f"\n{variable} derivará de forma gradual hacia "
                f"{nivel.lower()} (aprox. {DURACION_RAMPA_S} s)."
            )
            return

        print(
            f"'{variable}' no tiene zona de {nivel.lower()} definida. "
            "Elige otra variable."
        )


def iniciar(astronauta, intervalo=INTERVALO_S):

    print("\nASTRAHEALTH AI - MONITOREO")
    print("Astronauta:", astronauta["nombre"])
    print("Presiona Ctrl+C para detener.")

    # Un solo simulador para toda la sesión: cada medición parte de la anterior.
    simulador = SimuladorFisiologico()

    elegir_modo(simulador)

    try:

        while True:

            medicion = simulador.siguiente()

            medicion["astronauta_id"] = astronauta["id"]
            medicion["nombre"] = astronauta["nombre"]
            medicion["timestamp"] = pd.Timestamp.now()

            print("\nNueva medición:")
            print(medicion)

            yield medicion

            time.sleep(intervalo)

    except KeyboardInterrupt:

        print("\nSimulación detenida.")
