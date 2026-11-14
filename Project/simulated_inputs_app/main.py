
import pandas as pd
import numpy as np

from generador_datos import generar_datos, VARIABLES
from isolation_forest import entrenar as entrenar_if
from isolation_forest import detectar
from lstm_model import entrenar as entrenar_lstm
from lstm_model import predecir
from simulador_tiempo_real import iniciar

def preparar_modelos():

    generar_datos(10000)

    entrenar_if()

    entrenar_lstm()

def monitorear():

    historial = []

    print("\nASTRAHEALTH AI INICIADO")

    for medicion in iniciar():

        # Modelo Isolation Forest
        resultado_if = detectar(medicion)

        print("\n--- ISOLATION FOREST ---")
        print(resultado_if)

        historial.append([
            medicion[v] for v in VARIABLES
        ])

        if len(historial) >= 24:

            secuencia = historial[-24:]

            resultado_lstm = predecir(secuencia)

            print("\n--- PREDICCIÓN LSTM ---")

            for variable, valor in zip(
                VARIABLES,
                resultado_lstm
            ):
                print(f"{variable}: {valor:.2f}")

        print("\n--- ESTADO DEL ASTRONAUTA ---")

        if resultado_if["anomalia"]:
            print("ALERTA: comportamiento anómalo detectado")
        else:
            print("Estado: sin anomalías detectadas")

        print("-" * 50)

if __name__ == "__main__":

    print("1. Entrenar modelos")
    print("2. Iniciar monitoreo")

    opcion = input("Selecciona: ")

    if opcion == "1":
        preparar_modelos()

    elif opcion == "2":
        monitorear()
