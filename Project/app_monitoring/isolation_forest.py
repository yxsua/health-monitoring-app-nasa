import pandas as pd
import joblib

from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from generador_datos import VARIABLES

ARCHIVO_MODELO = "isolation_forest.pkl"

modelo = None


def entrenar():

    global modelo

    df = pd.read_csv("datos_entrenamiento.csv")

    columnas_estado = [
        f"estado_{i}" for i in range(len(VARIABLES))
    ]

    normales = df[
        (df[columnas_estado] == "NORMAL").all(axis=1)
    ]

    X = normales[VARIABLES]

    if len(X) < 100:
        raise ValueError(
            "No hay suficientes registros completamente normales."
        )

    modelo = Pipeline([
        ("escalador", StandardScaler()),
        ("detector", IsolationForest(
            n_estimators=200,
            contamination=0.03,
            random_state=42,
            n_jobs=-1
        ))
    ])

    modelo.fit(X)

    joblib.dump(modelo, ARCHIVO_MODELO)

    print(
        "Isolation Forest entrenado con",
        len(X),
        "registros normales."
    )


def detectar(datos):

    global modelo

    if modelo is None:
        modelo = joblib.load(ARCHIVO_MODELO)

    X = pd.DataFrame(
        [[datos[v] for v in VARIABLES]],
        columns=VARIABLES
    )

    prediccion = modelo.predict(X)[0]

    puntuacion = modelo.decision_function(X)[0]

    return {
        "anomalia": bool(prediccion == -1),
        "puntuacion": float(puntuacion),
        "resultado": (
            "ANOMALIA" if prediccion == -1 else "NORMAL"
        )
    }