import numpy as np

from generador_datos import (
    generar_datos,
    VARIABLES,
    evaluar_variable
)

from isolation_forest import entrenar as entrenar_if
from isolation_forest import detectar

from lstm_model import entrenar as entrenar_lstm
from lstm_model import predecir

from simulador_tiempo_real import iniciar


def solicitar_datos_astronauta():

    print("\n======================================")
    print("       ASTRAHEALTH AI")
    print("  REGISTRO DEL ASTRONAUTA")
    print("======================================")

    astronauta = {}

    astronauta["id"] = input(
        "\nIdentificador del astronauta: "
    ).strip()

    astronauta["nombre"] = input(
        "Nombre del astronauta: "
    ).strip()

    astronauta["edad"] = int(input(
        "Edad del astronauta: "
    ))

    astronauta["mision"] = input(
        "Nombre de la misión: "
    ).strip()

    if not all([
        astronauta["id"],
        astronauta["nombre"],
        astronauta["mision"]
    ]) or astronauta["edad"] <= 0:

        raise ValueError("Los datos del astronauta no son válidos.")

    return astronauta


def preparar_modelos(astronauta):

    print("\n======================================")
    print("GENERANDO DATOS DEL ASTRONAUTA")
    print("======================================")

    generar_datos(
        n=10000,
        astronauta=astronauta
    )

    print("\n======================================")
    print("ENTRENANDO ISOLATION FOREST")
    print("======================================")

    entrenar_if()

    print("\n======================================")
    print("ENTRENANDO LSTM")
    print("======================================")

    entrenar_lstm()

    print("\nTODOS LOS MODELOS FUERON ENTRENADOS.")


def mostrar_alertas(medicion):

    estados = {}

    print("\n========== ALERTAS INDIVIDUALES ==========")

    for variable in VARIABLES:

        valor = medicion[variable]

        estado = evaluar_variable(
            variable,
            valor
        )

        estados[variable] = estado

        if estado == "ALARMA":
            etiqueta = "[ALARMA]"
        elif estado == "PRECAUCION":
            etiqueta = "[PRECAUCION]"
        else:
            etiqueta = "[NORMAL]"

        print(
            f"{etiqueta:15} {variable}: {valor:.2f}"
        )

    return estados


def mostrar_estado_general(estados, resultado_if):

    print("\n========== ESTADO DEL ASTRONAUTA ==========")

    alarmas = [
        variable
        for variable, estado in estados.items()
        if estado == "ALARMA"
    ]

    precauciones = [
        variable
        for variable, estado in estados.items()
        if estado == "PRECAUCION"
    ]

    if alarmas:

        print("ESTADO GENERAL: ALARMA")

        for variable in alarmas:
            print(" -", variable)

    elif precauciones:

        print("ESTADO GENERAL: PRECAUCION")

        for variable in precauciones:
            print(" -", variable)

    else:

        print("ESTADO GENERAL: NORMAL")

    print(
        "\nIsolation Forest:",
        resultado_if["resultado"]
    )

    print(
        "Puntuación:",
        round(resultado_if["puntuacion"], 4)
    )


def monitorear(astronauta):

    historial = []

    print("\n======================================")
    print("ASTRAHEALTH AI INICIADO")
    print("ASTRONAUTA:", astronauta["nombre"])
    print("======================================")

    for medicion in iniciar(astronauta):

        # 1. Detección de anomalías globales.
        resultado_if = detectar(medicion)

        # 2. Guardar historial para LSTM.
        historial.append([
            medicion[v] for v in VARIABLES
        ])

        # 3. Evaluar las 17 variables individualmente.
        estados = mostrar_alertas(medicion)

        # 4. Predicción LSTM.
        if len(historial) >= 24:

            secuencia = historial[-24:]

            resultado_lstm = predecir(secuencia)

            print("\n========== PREDICCION LSTM ==========")

            for variable, valor in zip(
                VARIABLES,
                resultado_lstm
            ):

                estado_predicho = evaluar_variable(
                    variable,
                    float(valor)
                )

                print(
                    f"{variable}: {valor:.2f} "
                    f"-> {estado_predicho}"
                )

        # 5. Estado general.
        mostrar_estado_general(
            estados,
            resultado_if
        )

        print("\n" + "=" * 55)


if __name__ == "__main__":

    try:

        # Solicitar astronauta.
        astronauta = solicitar_datos_astronauta()

        # Entrenamiento automático.
        preparar_modelos(astronauta)

        # Iniciar monitoreo.
        monitorear(astronauta)

    except KeyboardInterrupt:

        print("\nASTRAHEALTH AI detenido.")

    except Exception as error:

        print("\nERROR EN ASTRAHEALTH AI:")
        print(error)
