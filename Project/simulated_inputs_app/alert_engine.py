# alert_engine.py

# Definición de umbrales: (limite_precaucion, limite_critico, direccion)
# direccion: "up" (si sube es malo), "down" (si baja es malo)
UMBRALES = {
    "fc (lpm)": (100, 120, "up"),
    "pa_sis (mmHg)": (130, 140, "up"),
    "pa_dia (mmHg)": (85, 90, "up"),
    "spo2 (%)": (95, 90, "down"),
    "temp (°C)": (37.5, 38.5, "up"),
    "glucosa (mg/dL)": (120, 150, "up"),
    "hrv (ms)": (40, 30, "down"), # HRV bajo indica estrés
    "sueño (h)": (6, 4, "down"),
    "ánimo (1-5)": (3, 2, "down"),
    "ejercicio (min)": (0, 0, "none"), # El ejercicio bajo no es alerta médica
    "radiación (mSv/día)": (1.0, 2.0, "up"),
    "co2 (ppm)": (1500, 2000, "up"),
    "temp_cabina (°C)": (26, 30, "up"),
    "humedad (%)": (60, 70, "up"),
    "ruido (dBA)": (60, 70, "up"),
    "presión (kPa)": (98, 95, "down"),
    "gravedad (g)": (0.5, 1.0, "up")
}

def evaluar_variable(variable, valor):
    if variable not in UMBRALES:
        return "NORMAL"
    
    lim_prac, lim_crit, direccion = UMBRALES[variable]
    
    if direccion == "none":
        return "NORMAL"
        
    if direccion == "up":
        if valor >= lim_crit: return "CRITICO"
        if valor >= lim_prac: return "PRECAUCION"
    elif direccion == "down":
        if valor <= lim_crit: return "CRITICO"
        if valor <= lim_prac: return "PRECAUCION"
        
    return "NORMAL"

def generar_alertas_actuales(medicion):
    """Evalúa la medición actual y genera alertas de estado."""
    alertas = []
    estado_global = "NORMAL"
    
    for variable, valor in medicion.items():
        if variable in ["astronauta_id", "timestamp"]: continue
        
        nivel = evaluar_variable(variable, valor)
        
        if nivel != "NORMAL":
            alertas.append({
                "variable": variable,
                "valor": round(valor, 2),
                "nivel": nivel,
                "mensaje": f"{variable} en estado {nivel}"
            })
            
            # El estado global toma la peor alerta
            if nivel == "CRITICO":
                estado_global = "CRITICO"
            elif nivel == "PRECAUCION" and estado_global != "CRITICO":
                estado_global = "PRECAUCION"
                
    return estado_global, alertas

def generar_alertas_preventivas(prediccion_dict, estado_actual_global):
    """
    Compara la predicción del LSTM con el estado actual.
    Si el futuro es peor que el presente, lanza alerta preventiva.
    """
    alertas_preventivas = []
    
    # Solo alertamos preventivamente si el paciente está estable ahora
    # Si ya está crítico, las alertas preventivas no tienen sentido
    if estado_actual_global != "NORMAL":
        return alertas_preventivas

    for variable, valor_futuro in prediccion_dict.items():
        nivel_futuro = evaluar_variable(variable, valor_futuro)
        
        if nivel_futuro in ["PRECAUCION", "CRITICO"]:
            alertas_preventivas.append({
                "variable": variable,
                "valor_predicho": round(valor_futuro, 2),
                "nivel_riesgo": nivel_futuro,
                "mensaje": f"Tendencia indica que {variable} llegará a {nivel_futuro} pronto."
            })
            
    return alertas_preventivas
