
import pandas as pd
import joblib

from sklearn.ensemble import IsolationForest
try:
    from .generador_datos import VARIABLES
    from .model_config import MODEL_ARTIFACTS_DIR, TRAINING_DATA_PATH
except ImportError:  # Support the legacy `python main.py` console entry point.
    from generador_datos import VARIABLES
    from model_config import MODEL_ARTIFACTS_DIR, TRAINING_DATA_PATH

def entrenar():
    dataframe = pd.read_csv(TRAINING_DATA_PATH).sort_values(["astronauta_id", "timestamp"])
    train_rows, validation_rows = [], []
    for _, group in dataframe.groupby("astronauta_id"):
        split = int(len(group) * 0.8)
        train_rows.append(group.iloc[:split])
        validation_rows.append(group.iloc[split:])
    train = pd.concat(train_rows, ignore_index=True)
    validation = pd.concat(validation_rows, ignore_index=True)
    X = train.loc[train["escenario"] == "normal", VARIABLES]
    if len(X) < 10:
        raise ValueError("Training data needs at least 10 nominal rows for Isolation Forest.")

    modelo = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42
    )

    modelo.fit(X)

    # Scenario names are proxy labels for synthetic evaluation only.
    predictions = modelo.predict(validation[VARIABLES])
    validation = validation.assign(predicted_anomaly=predictions == -1)
    nominal_validation = validation.loc[validation["escenario"] == "normal", "predicted_anomaly"]
    metrics = {
        "validation_rows": int(len(validation)),
        "nominal_false_positive_rate": float(nominal_validation.mean()) if len(nominal_validation) else None,
        "scenario_detection_rate": {
            scenario: float(group["predicted_anomaly"].mean())
            for scenario, group in validation.loc[validation["escenario"] != "normal"].groupby("escenario")
        },
        "evaluation_note": "Synthetic scenario detection rates; scenario labels are proxies, not clinical truth.",
    }

    MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, MODEL_ARTIFACTS_DIR / "isolation_forest.pkl")

    print("Isolation Forest entrenado.")
    return metrics

def detectar(datos, modelo=None):

    if modelo is None:
        modelo = joblib.load(MODEL_ARTIFACTS_DIR / "isolation_forest.pkl")

    X = pd.DataFrame([datos])[VARIABLES]

    prediccion = modelo.predict(X)[0]

    puntuacion = modelo.decision_function(X)[0]

    return {
        "anomalia": prediccion == -1,
        "puntuacion": float(puntuacion),
        "resultado": "ANOMALIA" if prediccion == -1 else "NORMAL"
    }
