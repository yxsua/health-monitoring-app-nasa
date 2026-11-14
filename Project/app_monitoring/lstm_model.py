
import pandas as pd
import numpy as np
import joblib

from sklearn.preprocessing import MinMaxScaler

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

VARIABLES = [
    "fc (lpm)", "pa_sis (mmHg)", "pa_dia (mmHg)",
    "spo2 (%)", "temp (°C)", "glucosa (mg/dL)",
    "hrv (ms)", "sueño (h)", "ánimo (1-5)",
    "ejercicio (min)", "radiación (mSv/día)",
    "co2 (ppm)", "temp_cabina (°C)",
    "humedad (%)", "ruido (dBA)",
    "presión (kPa)", "gravedad (g)"
]

VENTANA = 24

def entrenar():

    df = pd.read_csv("datos_entrenamiento.csv")

    df = df.sort_values(
        ["astronauta_id", "timestamp"]
    )

    X_total = []

    for astronauta, grupo in df.groupby("astronauta_id"):

        valores = grupo[VARIABLES].values

        X_total.extend(valores)

    scaler = MinMaxScaler()

    valores = scaler.fit_transform(X_total)

    X, y = [], []

    # Construcción de secuencias
    for i in range(len(valores) - VENTANA):

        X.append(valores[i:i + VENTANA])
        y.append(valores[i + VENTANA])

    X = np.array(X)
    y = np.array(y)

    model = Sequential([
        LSTM(64, return_sequences=True,
             input_shape=(VENTANA, len(VARIABLES))),
        Dropout(0.2),

        LSTM(32),

        Dense(32, activation="relu"),

        Dense(len(VARIABLES))
    ])

    model.compile(
        optimizer="adam",
        loss="mse"
    )

    model.fit(
        X,
        y,
        epochs=30,
        batch_size=64,
        validation_split=0.2,
        shuffle=False,
        callbacks=[
            EarlyStopping(
                patience=5,
                restore_best_weights=True
            )
        ]
    )

    model.save("lstm_model.keras")

    joblib.dump(scaler, "scaler.pkl")

    print("LSTM entrenada.")

def predecir(secuencia):

    from tensorflow.keras.models import load_model

    model = load_model("lstm_model.keras")
    scaler = joblib.load("scaler.pkl")

    valores = np.array(secuencia)

    valores = scaler.transform(valores)

    entrada = valores.reshape(
        1, VENTANA, len(VARIABLES)
    )

    prediccion = model.predict(entrada, verbose=0)

    resultado = scaler.inverse_transform(prediccion)

    return resultado[0]

