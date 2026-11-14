import pandas as pd
import numpy as np
import joblib

from sklearn.preprocessing import MinMaxScaler

from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

from generador_datos import VARIABLES

VENTANA = 24

ARCHIVO_MODELO = "lstm_model.keras"
ARCHIVO_SCALER = "scaler.pkl"

modelo = None
scaler = None


def entrenar():

    global modelo, scaler

    df = pd.read_csv("datos_entrenamiento.csv")

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df = df.sort_values(
        ["astronauta_id", "timestamp"]
    )

    # Ajustar escalador con los primeros datos temporales.
    grupos = [
        grupo[VARIABLES].values
        for _, grupo in df.groupby("astronauta_id")
    ]

    scaler = MinMaxScaler()

    datos_entrenamiento = np.concatenate([
        grupo[:int(len(grupo) * 0.8)]
        for grupo in grupos
    ])

    scaler.fit(datos_entrenamiento)

    X, y = [], []

    # Crear secuencias separadas por astronauta.
    for _, grupo in df.groupby("astronauta_id"):

        valores = scaler.transform(
            grupo[VARIABLES].values
        )

        for i in range(len(valores) - VENTANA):

            X.append(valores[i:i + VENTANA])
            y.append(valores[i + VENTANA])

    X = np.array(X)
    y = np.array(y)

    if len(X) < 100:
        raise ValueError("No hay suficientes secuencias para entrenar.")

    # Separación temporal.
    corte = int(len(X) * 0.8)

    X_train = X[:corte]
    y_train = y[:corte]

    X_val = X[corte:]
    y_val = y[corte:]

    modelo = Sequential([

        LSTM(
            64,
            return_sequences=True,
            input_shape=(VENTANA, len(VARIABLES))
        ),

        Dropout(0.2),

        LSTM(32),

        Dense(32, activation="relu"),

        Dense(len(VARIABLES))
    ])

    modelo.compile(
        optimizer="adam",
        loss="mse"
    )

    modelo.fit(
        X_train,
        y_train,
        epochs=30,
        batch_size=64,
        validation_data=(X_val, y_val),
        shuffle=False,
        callbacks=[
            EarlyStopping(
                patience=5,
                restore_best_weights=True
            )
        ]
    )

    modelo.save(ARCHIVO_MODELO)

    joblib.dump(scaler, ARCHIVO_SCALER)

    print("LSTM entrenada correctamente.")

    return modelo


def predecir(secuencia):

    global modelo, scaler

    if modelo is None:
        modelo = load_model(ARCHIVO_MODELO)

    if scaler is None:
        scaler = joblib.load(ARCHIVO_SCALER)

    valores = np.array(secuencia, dtype=float)

    if valores.shape != (VENTANA, len(VARIABLES)):
        raise ValueError(
            f"La secuencia debe tener dimensiones "
            f"{VENTANA} x {len(VARIABLES)}."
        )

    valores = scaler.transform(valores)

    entrada = valores.reshape(
        1,
        VENTANA,
        len(VARIABLES)
    )

    prediccion = modelo.predict(
        entrada,
        verbose=0
    )

    resultado = scaler.inverse_transform(prediccion)

    return resultado[0]