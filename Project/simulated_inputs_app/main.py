
 # main.py
import pandas as pd
import numpy as np
from datetime import datetime

from generador_datos import VARIABLES
from isolation_forest import detectar
from lstm_model import predecir
from simulador_tiempo_real import iniciar
from alert_engine import generar_alertas_actuales, generar_alertas_preventivas

def preparar_modelos():
    print("Generating aligned three-second data and training models...")
    try:
        from .train_models import train
    except ImportError:
        from train_models import train
    train(10000)
    print("Models and manifest ready.")

def monitorear():
    historial = []
    print("\nASTRAHEALTH AI INICIADO - SISTEMA DE ALERTAS TEMPRANAS\n")

    for medicion in iniciar():
        timestamp = medicion["timestamp"].strftime("%H:%M:%S")
        print(f"\n[{timestamp}] --- TELEMETRÍA RECIBIDA ---")
        
        # 1. EVALUACIÓN DE REGLAS ACTUALES (El motor de alertas)
        estado_global, alertas_actuales = generar_alertas_actuales(medicion)
        
        # 2. ISOLATION FOREST (Detección de anomalías multivariable)
        # Eliminamos 'timestamp' para el modelo IF
        medicion_if = {k: v for k, v in medicion.items() if k in VARIABLES}
        resultado_if = detectar(medicion_if)
        
        # 3. PREPARAR HISTORIAL PARA LSTM
        historial.append([medicion[v] for v in VARIABLES])
        
        # Imprimir Estado Actual
        print(f"ESTADO GENERAL: {estado_global}")
        if alertas_actuales:
            for a in alertas_actuales:
                icono = "🔴" if a['nivel'] == "CRITICO" else "🟡"
                print(f"  {icono} ALERTA: {a['mensaje']} (Valor: {a['valor']})")
        else:
            print("  🟢 Todos los parámetros en rango normal.")
            
        if resultado_if["anomalia"]:
            print(f"  🧠 IF: Anomalía multivariable detectada (Score: {resultado_if['puntuacion']:.3f}). Combinación inusual de signos.")

        # 4. PREDICCIÓN LSTM Y ALERTAS PREVENTIVAS
        if len(historial) >= 24:
            secuencia = historial[-24:]
            resultado_lstm = predecir(secuencia)
            
            # Formatear predicción del LSTM
            prediccion_dict = dict(zip(VARIABLES, resultado_lstm))
            
            # Generar alertas preventivas
            alertas_futuras = generar_alertas_preventivas(prediccion_dict, estado_global)
            
            if alertas_futuras:
                print("  ⚠️ SISTEMA DE PREVENCIÓN (LSTM Próximos 24 min):")
                for ap in alertas_futuras:
                    print(f"     -> {ap['mensaje']} (Predicción: {ap['valor_predicho']})")
            else:
                print("  📈 LSTM: Proyección estable para los próximos 24 minutos.")
                
        print("-" * 60)

if __name__ == "__main__":
    print("1. Entrenar modelos")
    print("2. Iniciar monitoreo")
    opcion = input("Selecciona: ")
    if opcion == "1":
        preparar_modelos()
    elif opcion == "2":
        monitorear()
