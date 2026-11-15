"""Train and run the one-step LSTM on per-astronaut, three-second windows."""
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf

from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.models import load_model

try:
    from .generador_datos import VARIABLES
    from .model_config import MODEL_ARTIFACTS_DIR, TRAINING_DATA_PATH
    from .simulador_tiempo_real import SAMPLE_PERIOD_SECONDS
except ImportError:  # Support the legacy `python main.py` console entry point.
    from generador_datos import VARIABLES
    from model_config import MODEL_ARTIFACTS_DIR, TRAINING_DATA_PATH
    from simulador_tiempo_real import SAMPLE_PERIOD_SECONDS

VENTANA = 24


def _build_windows(values, window):
    X, y = [], []
    for index in range(len(values) - window):
        X.append(values[index:index + window])
        y.append(values[index + window])
    return X, y


def entrenar():
    tf.keras.utils.set_random_seed(42)
    dataframe = pd.read_csv(TRAINING_DATA_PATH)
    streams = {}
    train_rows = []
    for astronaut, group in dataframe.sort_values(["astronauta_id", "timestamp"]).groupby("astronauta_id"):
        values = group[VARIABLES].to_numpy(dtype=float)
        split = int(len(values) * 0.8)
        if split <= VENTANA or len(values) - split == 0:
            continue
        streams[astronaut] = (values[:split], values[split:])
        train_rows.append(values[:split])
    if not streams:
        raise ValueError("Training data must contain more than 24 chronological rows per astronaut.")

    # Fit preprocessing only to each astronaut's chronological training partition.
    scaler = MinMaxScaler()
    scaler.fit(np.concatenate(train_rows, axis=0))
    X_train, y_train, X_validation, y_validation = [], [], [], []
    for train_values, validation_values in streams.values():
        train_scaled = scaler.transform(train_values)
        validation_scaled = scaler.transform(validation_values)
        train_X, train_y = _build_windows(train_scaled, VENTANA)
        X_train.extend(train_X)
        y_train.extend(train_y)

        # Validation context may use the final training rows, but never another astronaut.
        context = train_scaled[-VENTANA:]
        for index, target in enumerate(validation_scaled):
            X_validation.append(context[-VENTANA:])
            y_validation.append(target)
            context = np.concatenate((context, target.reshape(1, -1)), axis=0)
    if not X_train or not X_validation:
        raise ValueError("Could not construct non-empty training and validation windows.")

    X_train = np.asarray(X_train, dtype=float)
    y_train = np.asarray(y_train, dtype=float)
    X_validation = np.asarray(X_validation, dtype=float)
    y_validation = np.asarray(y_validation, dtype=float)

    model = Sequential([
        LSTM(64, return_sequences=True, input_shape=(VENTANA, len(VARIABLES))),
        Dropout(0.2),
        LSTM(32),
        Dense(32, activation="relu"),
        Dense(len(VARIABLES)),
    ])
    model.compile(optimizer="adam", loss="mse")
    history = model.fit(
        X_train, y_train, epochs=30, batch_size=64, shuffle=False,
        validation_data=(X_validation, y_validation),
        callbacks=[EarlyStopping(patience=5, restore_best_weights=True)],
    )

    MODEL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_ARTIFACTS_DIR / "lstm_model.keras")
    joblib.dump(scaler, MODEL_ARTIFACTS_DIR / "scaler.pkl")
    predicted_scaled = model.predict(X_validation, verbose=0)
    predicted_values = scaler.inverse_transform(predicted_scaled)
    actual_values = scaler.inverse_transform(y_validation)
    absolute_error = np.abs(predicted_values - actual_values)
    metrics = {
        "validation_rows": int(len(y_validation)),
        "best_validation_loss_scaled_mse": float(min(history.history["val_loss"])),
        "mae_by_feature": {variable: float(value) for variable, value in zip(VARIABLES, absolute_error.mean(axis=0))},
    }
    print(f"LSTM trained: {VENTANA} steps, {SAMPLE_PERIOD_SECONDS}s cadence, one-step horizon.")
    return metrics


def predecir(secuencia, model=None, scaler=None):
    """Predict one following row. Loaded objects may be injected to avoid reloads."""
    if model is None:
        model = load_model(MODEL_ARTIFACTS_DIR / "lstm_model.keras")
    if scaler is None:
        scaler = joblib.load(MODEL_ARTIFACTS_DIR / "scaler.pkl")
    values = np.asarray(secuencia, dtype=float)
    if values.shape != (VENTANA, len(VARIABLES)):
        raise ValueError(f"Expected input shape ({VENTANA}, {len(VARIABLES)}), received {values.shape}.")
    scaled = scaler.transform(values).reshape(1, VENTANA, len(VARIABLES))
    predicted = model.predict(scaled, verbose=0)
    return scaler.inverse_transform(predicted)[0]
