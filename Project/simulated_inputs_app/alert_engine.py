# alert_engine.py
from enum import Enum

class MissionPhase(Enum):
    REPOSO = "reposo"
    EJERCICIO = "ejercicio"
    EVA = "eva" # Paseo espacial
    SUEÑO = "sueño"

class TriageLevel(Enum):
    NOMINAL = 0
    WATCH = 1     # Precaución
    WARNING = 2   # Advertencia
    CRITICAL = 3  # Emergencia

# Umbrales dinámicos según la fase de la misión (ej. FC)
UMBRALES_FISIOLOGICOS = {
    MissionPhase.REPOSO: {"fc (lpm)": (100, 120, "up")},
    MissionPhase.EJERCICIO: {"fc (lpm)": (150, 180, "up")}, # En ejercicio es normal subir
    MissionPhase.EVA: {"fc (lpm)": (130, 160, "up")},
    MissionPhase.SUEÑO: {"fc (lpm)": (80, 100, "up")}
}

# Umbrales ambientales (estáticos, no dependen del astronauta)
UMBRALES_AMBIENTALES = {
    "co2 (ppm)": (1500, 2000, "up"),
    "radiación (mSv/día)": (1.0, 2.0, "up"),
    "presión (kPa)": (98, 95, "down")
}

def evaluar_variable(variable, valor, fase_mision):
    # Lógica de evaluación fisiológica dinámica
    if variable in UMBRALES_FISIOLOGICOS.get(fase_mision, {}):
        lim_prac, lim_crit, _ = UMBRALES_FISIOLOGICOS[fase_mision][variable]
        if valor >= lim_crit: return TriageLevel.CRITICAL
        if valor >= lim_prac: return TriageLevel.WATCH
    
    # Lógica de evaluación ambiental
    if variable in UMBRALES_AMBIENTALES:
        lim_prac, lim_crit, direccion = UMBRALES_AMBIENTALES[variable]
        if direccion == "up":
            if valor >= lim_crit: return TriageLevel.CRITICAL
            if valor >= lim_prac: return TriageLevel.WARNING
        elif direccion == "down":
            if valor <= lim_crit: return TriageLevel.CRITICAL
            if valor <= lim_prac: return TriageLevel.WARNING
            
    return TriageLevel.NOMINAL

def evaluar_correlaciones(medicion, fase_mision):
    """
    Lógica de Soporte Vital: Cruza variables para detectar fallos sistémicos.
    """
    alertas_correlacionadas = []
    
    # 1. Correlación de Hipoxia (Fallo de Soporte Vital)
    # Si el CO2 sube, el SpO2 baja y la FC sube -> No es un problema cardíaco, es el aire.
    if (medicion.get("co2 (ppm)", 0) > 1500 and 
        medicion.get("spo2 (%)", 100) < 95 and 
        medicion.get("fc (lpm)", 60) > 100):
        alertas_correlacionadas.append({
            "nivel": TriageLevel.CRITICAL,
            "sistema": "SOPORTE_VITAL",
            "mensaje": "FALLO DE VENTILACIÓN: CO2 elevado causando hipoxia y taquicardia. Activar scrubbers de emergencia."
        })

    # 2. Correlación de Fatiga Cognitiva (Riesgo en EVA)
    # Si el astronauta durmió mal, tiene HRV bajo y ánimo bajo -> Riesgo de error humano.
    if (medicion.get("sueño (h)", 8) < 6 and 
        medicion.get("hrv (ms)", 50) < 40 and 
        medicion.get("ánimo (1-5)", 5) <= 2):
        alertas_correlacionadas.append({
            "nivel": TriageLevel.WARNING,
            "sistema": "COGNITIVO",
            "mensaje": "Riesgo de fatiga extrema detectado. Restringir maniobras EVA complejas. Sugerir descanso."
        })

    # 3. Correlación de Radiación
    if medicion.get("radiación (mSv/día)", 0) > 2.0 and medicion.get("temp (°C)", 37) > 37.5:
        alertas_correlacionadas.append({
            "nivel": TriageLevel.WATCH,
            "sistema": "RADIACION",
            "mensaje": "Exposición a radiación con fiebre leve. Monitorear posibles náuseas o síndrome de radiación."
        })
        
    return alertas_correlacionadas

def generar_triage(medicion, fase_mision=MissionPhase.REPOSO):
    alertas_individuales = []
    nivel_maximo = TriageLevel.NOMINAL
    
    # 1. Evaluar variables una por una
    for variable, valor in medicion.items():
        if variable in ["astronauta_id", "timestamp"]: continue
        nivel = evaluar_variable(variable, valor, fase_mision)
        if nivel != TriageLevel.NOMINAL:
            alertas_individuales.append({"variable": variable, "nivel": nivel.name, "valor": valor})
            if nivel.value > nivel_maximo.value: nivel_maximo = nivel

    # 2. Evaluar correlaciones cruzadas (El toque de NASA)
    alertas_cruzadas = evaluar_correlaciones(medicion, fase_mision)
    for a in alertas_cruzadas:
        if a["nivel"].value > nivel_maximo.value: nivel_maximo = a["nivel"]

    return {
        "estado_global": nivel_maximo.name,
        "fase_mision": fase_mision.value,
        "alertas_individuales": alertas_individuales,
        "alertas_sistemicas": alertas_cruzadas
    }
