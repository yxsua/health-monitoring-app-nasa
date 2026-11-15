"""Motor de triaje de AstraHealth.

Las reglas son deterministas (seguridad). Isolation Forest y LSTM solo asesoran.
Los umbrales son de DEMOSTRACIÓN y no están revisados clínicamente.
Compatible con main.py: generar_alertas_actuales() y generar_alertas_preventivas().
"""
from enum import Enum


class MissionPhase(Enum):
    REPOSO = "reposo"
    EJERCICIO = "ejercicio"
    EVA = "eva"  # paseo espacial
    SUEÑO = "sueño"


NIVELES = ["NORMAL", "PRECAUCION", "ADVERTENCIA", "CRITICO"]
SISTEMICOS = {"SOPORTE_VITAL", "COGNITIVO", "RADIACION", "SENSOR"}

# Frecuencia cardiaca por fase: (precaución, advertencia, crítico), siempre "hacia arriba".
FC = {MissionPhase.REPOSO: (100, 120, 140), MissionPhase.EJERCICIO: (150, 175, 190),
      MissionPhase.EVA: (130, 155, 175), MissionPhase.SUEÑO: (80, 95, 110)}
# variable: (precaución, advertencia, crítico, dirección)
LIMITES = {"spo2 (%)": (95, 92, 88, "down"), "temp (°C)": (37.5, 38.0, 39.0, "up"),
           "presión (kPa)": (98, 95, 90, "down"), "radiación (mSv/día)": (1.0, 5.0, 12.0, "up"),
           "pa_sis (mmHg)": (140, 160, 180, "up")}
PPCO2_MMHG = (4.0, 5.3, 7.6)   # presión parcial de CO2, unidad que usa NASA
PPO2_KPA = (17.0, 16.0, 14.0)

# Campo del contrato JSON (Docs/Challenge) -> clave plana del simulador (igual que MAPPING en api.py)
CONTRATO = {"heart_rate": "fc (lpm)", "systolic_pressure": "pa_sis (mmHg)", "diastolic_pressure": "pa_dia (mmHg)",
            "spo2": "spo2 (%)", "body_temperature": "temp (°C)", "glucose": "glucosa (mg/dL)", "hrv_rmssd": "hrv (ms)",
            "sleep_duration": "sueño (h)", "mood": "ánimo (1-5)", "exercise_duration": "ejercicio (min)",
            "radiation_dose_rate": "radiación (mSv/día)", "co2": "co2 (ppm)", "cabin_temperature": "temp_cabina (°C)",
            "humidity": "humedad (%)", "noise": "ruido (dBA)", "cabin_pressure": "presión (kPa)", "gravity": "gravedad (g)"}
CRITICAS = ("co2 (ppm)", "fc (lpm)", "spo2 (%)", "presión (kPa)")
FIELD_LABELS_EN = {
    "fc (lpm)": "Heart rate", "pa_sis (mmHg)": "Systolic pressure", "pa_dia (mmHg)": "Diastolic pressure",
    "spo2 (%)": "SpO₂", "temp (°C)": "Body temperature", "glucosa (mg/dL)": "Glucose",
    "hrv (ms)": "HRV (RMSSD)", "sueño (h)": "Sleep duration", "ánimo (1-5)": "Mood",
    "ejercicio (min)": "Exercise duration", "radiación (mSv/día)": "Radiation dose rate",
    "co2 (ppm)": "Cabin CO₂", "temp_cabina (°C)": "Cabin temperature", "humedad (%)": "Humidity",
    "ruido (dBA)": "Noise", "presión (kPa)": "Cabin pressure", "gravedad (g)": "Gravity",
}


def _field_label(variable):
    return FIELD_LABELS_EN.get(variable, variable)


def nivel(valor, limites, abajo=False):
    """Cuenta cuántos límites se cruzaron: 0 normal ... 3 crítico."""
    return sum((valor <= l) if abajo else (valor >= l) for l in limites)


def ppco2_mmhg(ppm, kpa):
    return ppm * 1e-6 * kpa * 7.50062


def _a(variable, lvl, mensaje, valor=None, sistema="FISIOLOGIA"):
    return {"variable": variable, "nivel": NIVELES[lvl], "nivel_num": lvl,
            "mensaje": mensaje, "valor": valor, "sistema": sistema}


def aplanar_item(item):
    """Convierte un item del contrato anidado a (dict plano, variables no disponibles)."""
    plano, faltantes = {}, []
    for grupo in ("physiological", "self_assessment", "environment"):
        for campo, obs in item.get(grupo, {}).items():
            clave = CONTRATO.get(campo)
            if not clave:
                continue
            if obs.get("quality") == "valid" and obs.get("value") is not None:
                plano[clave] = obs["value"]
            else:
                faltantes.append(clave)
    return plano, faltantes


def generar_alertas_actuales(m, fase=MissionPhase.REPOSO, faltantes=()):
    alertas = []
    kpa = m.get("presión (kPa)", 101)
    n_co2 = nivel(ppco2_mmhg(m["co2 (ppm)"], kpa), PPCO2_MMHG) if "co2 (ppm)" in m else 0
    n_fc = nivel(m["fc (lpm)"], FC[fase]) if "fc (lpm)" in m else 0
    n_sp = nivel(m["spo2 (%)"], LIMITES["spo2 (%)"][:3], True) if "spo2 (%)" in m else 0
    n_o2 = nivel(kpa * 0.2094, PPO2_KPA, True)

    if n_co2:
        alertas.append(_a("co2 (ppm)", n_co2, "Cabin CO₂ is above the nominal range.", m["co2 (ppm)"], "AMBIENTE"))
    if n_fc:
        phase_label = {MissionPhase.REPOSO: "rest", MissionPhase.EJERCICIO: "exercise", MissionPhase.EVA: "EVA", MissionPhase.SUEÑO: "sleep"}[fase]
        alertas.append(_a("fc (lpm)", n_fc, f"Heart rate is outside the expected range during {phase_label}.", m["fc (lpm)"]))
    for var, (*lims, sentido) in LIMITES.items():
        if var in m and (n := nivel(m[var], lims, sentido == "down")):
            amb = var in ("presión (kPa)", "radiación (mSv/día)")
            alertas.append(_a(var, n, f"{_field_label(var)} is outside the configured range.", m[var], "AMBIENTE" if amb else "FISIOLOGIA"))

    # Correlaciones: separan causa ambiental de causa médica.
    if n_co2 and n_fc:  # hipercapnia: cefalea, taquipnea y taquicardia; NO es hipoxia
        alertas.append(_a("co2+fc", max(n_co2, 2), "Elevated heart rate with high CO₂ may have an environmental cause (hypercapnia). "
                          "Review the CO₂ scrubber before treating it as a cardiac issue.", None, "SOPORTE_VITAL"))
    if n_o2 and n_sp:
        alertas.append(_a("presión+spo2", max(n_o2, n_sp), "Low SpO₂ with reduced ppO₂ indicates possible environmental hypoxia. "
                          "Restore oxygen and isolate the leak.", None, "SOPORTE_VITAL"))
    if m.get("sueño (h)", 8) < 6 and m.get("hrv (ms)", 50) < 40 and m.get("ánimo (1-5)", 5) <= 2:
        alertas.append(_a("sueño+hrv+ánimo", 2, "Possible cognitive fatigue based on sleep, HRV, and mood readings. Review complex EVA activity.",
                          None, "COGNITIVO"))
    if m.get("radiación (mSv/día)", 0) >= 5 and m.get("temp (°C)", 37) > 37.5:
        alertas.append(_a("radiación+temp", 1, "High radiation with mildly elevated body temperature; monitor for nausea (radiation syndrome).",
                          None, "RADIACION"))
    for var in faltantes:  # dato ausente = condición NO resuelta, se avisa de forma explícita
        if var in CRITICAS:
            alertas.append(_a(var, 1, f"No valid {_field_label(var)} reading is available; this variable was not evaluated.", None, "SENSOR"))
    estado = max((a["nivel_num"] for a in alertas), default=0)
    return NIVELES[estado], alertas


def generar_alertas_preventivas(prediccion, estado_global="NORMAL", fase=MissionPhase.REPOSO):
    """Evalúa la predicción del LSTM con las mismas reglas. Solo informa; no escala el estado."""
    if estado_global == "CRITICO":
        return []
    _, alertas = generar_alertas_actuales(prediccion, fase)
    return [{"mensaje": "Projection: " + a["mensaje"], "valor_predicho": a["valor"]} for a in alertas]


def triage_payload(payload, fase=MissionPhase.REPOSO):
    """Triaje de una respuesta del contrato (simulated-astronaut-inputs)."""
    item = payload["items"][0]
    plano, faltantes = aplanar_item(item)
    estado, alertas = generar_alertas_actuales(plano, fase, faltantes)
    return {"astronaut_id": item["astronaut_id"], "estado_global": estado,
            "fase_mision": fase.value, "alertas": alertas}


def generar_triage(medicion, fase_mision=MissionPhase.REPOSO):
    """Compatibilidad con la versión anterior del módulo."""
    estado, alertas = generar_alertas_actuales(medicion, fase_mision)
    return {"estado_global": estado, "fase_mision": fase_mision.value,
            "alertas_individuales": [a for a in alertas if a["sistema"] not in SISTEMICOS],
            "alertas_sistemicas": [a for a in alertas if a["sistema"] in SISTEMICOS]}
