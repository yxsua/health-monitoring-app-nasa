
import pandas as pd
import numpy as np
import joblib

from sklearn.ensemble import IsolationForest

VARIABLES = [
    "fc (lpm)", "pa_sis (mmHg)", "pa_dia (mmHg)",
    "spo2 (%)", "temp (°C)", "glucosa (mg/dL)",
    "hrv (ms)", "sueño (h)", "ánimo (1-5)",
    "ejercicio (min)", "radiación (mSv/día)",
    "co2 (ppm)", "temp_cabina (°C)",
    "humedad (%)", "ruido (dBA)",
    "presión (kPa)", "gravedad (g)"
]

def entrenar():

    df = pd.read_csv("datos_entrenamiento.csv")

    # Entrenamiento inicial con datos normales
    normales = df[df["escenario"] == "normal"]

    X = normales[VARIABLES]

    modelo = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42
    )

    modelo.fit(X)

    joblib.dump(modelo, "isolation_forest.pkl")

    print("Isolation Forest entrenado.")

def detectar(datos):

    modelo = joblib.load("isolation_forest.pkl")

    X = pd.DataFrame([datos])[VARIABLES]

    prediccion = modelo.predict(X)[0]

    puntuacion = modelo.decision_function(X)[0]

    return {
        "anomalia": prediccion == -1,
        "puntuacion": float(puntuacion),
        "resultado": "ANOMALIA" if prediccion == -1 else "NORMAL"
    }
