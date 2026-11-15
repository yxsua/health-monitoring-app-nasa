"""Mantenimiento correctivo y predictivo del cuerpo y de la cabina (AstraHealth).

Qué hace
  * CORRECTIVO (ahora): lee las mediciones actuales + el resultado del Isolation Forest y devuelve
    acciones inmediatas para reducir el riesgo.
  * PREDICTIVO (siguiente paso): compara el pronóstico del LSTM con los umbrales y devuelve acciones
    preventivas antes de que el valor cruce el umbral.
  * Umbrales = hoja Reglas_Alerta de tu Excel (cargar_umbrales). Los de HRV y cabina son supuestos de
    demostración (ver hoja Umbrales del libro). Todo debe validarlo el cirujano de vuelo.

Integración (con el motor de la Parte 3):
    from mantenimiento import Evaluador, cargar_umbrales
    ev = Evaluador(cargar_umbrales("Historial_medico_sintetico_IA_ampliado.xlsx"))
    st = engine.state(now)                                   # estado del motor (Parte 3)
    res = ev.evaluar(st["values"], if_result=st["ai"]["anomaly"], pron=pronostico_lstm,
                     actividad=st["phase"], paso_s=3.0, estimados=st["estimated_vars"])
    # res["cuerpo"]["correctivo"], res["cuerpo"]["predictivo"], res["cabina"][...], res["if"], res["global"]
Regla de oro: el IF nunca baja un nivel que hayan subido las reglas; solo cambia la prioridad y el texto.
"""
import copy
import math

NIVELES = ["NORMAL", "PRECAUCION", "ALERTA", "CRITICO"]
ALIAS = {"fc": "fc (lpm)", "sis": "pa_sis (mmHg)", "dia": "pa_dia (mmHg)", "spo2": "spo2 (%)", "temp": "temp (°C)",
         "glu": "glucosa (mg/dL)", "hrv": "hrv (ms)", "sueno": "sueño (h)", "co2": "co2 (ppm)", "pres": "presión (kPa)",
         "ppo2": "ppo2 (kPa)", "tcab": "temp_cabina (°C)", "hum": "humedad (%)", "ruido": "ruido (dBA)",
         "rad": "radiación (mSv/día)"}
CUERPO = ("fc", "sis", "dia", "spo2", "temp", "glu", "hrv")
CABINA = ("co2", "pres", "ppo2", "tcab", "hum", "ruido", "rad")


def _u(lo, hi, margen):  # lo=(precaución, alerta, crítico) para x < t ; hi=(...) para x >= t
    return {"lo": lo, "hi": hi, "margen": margen}


UMBRALES = {  # Cuerpo: Reglas_Alerta (tu Excel), salvo HRV (supuesto). Cabina: supuestos de demostración.
    "fc": _u((50, 45, 40), (100, 120, 150), 5), "sis": _u((100, 90, 80), (130, 140, 180), 5),
    "dia": _u((60, 55, 50), (85, 90, 120), 4), "spo2": _u((95, 92, 90), None, 1),
    "temp": _u((36.0, 35.5, 35.0), (37.5, 38.0, 39.5), 0.3), "glu": _u((74, 70, 54), (140, 180, 250), 8),
    "hrv": _u((30, 20, 10), None, 4),
    "co2": _u(None, (5300, 7000, 10000), 300),  # ppm equivalentes a 101,3 kPa (≈4,0 / 5,3 / 7,6 mmHg de ppCO2)
    "pres": _u((98, 95, 90), None, 1), "ppo2": _u((17, 16, 14), None, 0.5),
    "tcab": _u((18.3, 16, 12), (26.7, 30, 35), 1), "hum": _u((30, 25, 15), (60, 70, 85), 4),
    "ruido": _u(None, (55, 65, 85), 3), "rad": _u(None, (1.0, 5.0, 12.0), 0.3)}
REFERENCIA = {"fc": 70, "sis": 115, "dia": 75, "spo2": 98, "temp": 36.7, "glu": 95, "hrv": 65,
              "co2": 1000, "pres": 101, "tcab": 22, "hum": 45, "ruido": 40, "rad": 0.5}
SIGMA = {"fc": 12, "sis": 10, "dia": 8, "spo2": 1, "temp": 0.3, "glu": 10, "hrv": 10,  # de generador_datos.py
         "co2": 100, "pres": 1, "tcab": 1, "hum": 5, "ruido": 5, "rad": 0.2}
LIM_EJ = {"fc": 150, "sis": 180, "temp": 38.5}  # en ejercicio/EVA, por debajo de esto es lo esperado (caso C14)
EJERCICIO = ("exercise", "ejercicio", "eva")
_MAPA_EXCEL = {"Glucosa": "glu", "Presión sistólica": "sis", "Presión diastólica": "dia", "Saturación": "spo2",
               "Temperatura": "temp", "Frecuencia cardiaca": "fc"}


def cargar_umbrales(ruta):
    """Lee Reglas_Alerta (tu Excel) o la hoja Umbrales del libro de mantenimiento. Sin openpyxl o sin archivo: valores por defecto."""
    u = copy.deepcopy(UMBRALES)
    try:
        from openpyxl import load_workbook
        wb = load_workbook(ruta, read_only=True, data_only=True)
        ws = wb["Reglas_Alerta"] if "Reglas_Alerta" in wb.sheetnames else wb["Umbrales"]
        filas = list(ws.iter_rows(values_only=True))
    except Exception:
        return u
    cab = next((i for i, f in enumerate(filas) if f and f[0] == "Parametro"), None)
    if cab is None:
        return u
    col = {n: i for i, n in enumerate(filas[cab])}
    lim = lambda x: None if x is None or float(x) in (9999.0, -9999.0) else float(x)  # centinelas del Excel
    for f in filas[cab + 1:]:
        if not f or not f[0]:
            continue
        k = next((c for c, full in ALIAS.items() if full == f[0]), None) or next((c for n, c in _MAPA_EXCEL.items() if str(f[0]).startswith(n)), None)
        if not k:
            continue
        lo = tuple(lim(f[col[h]]) for h in ("Precaucion_si_<", "Alerta_si_<", "Critico_si_<"))
        hi = tuple(lim(f[col[h]]) for h in ("Precaucion_si_≥", "Alerta_si_≥", "Critico_si_≥"))
        u[k] = {"lo": lo if any(x is not None for x in lo) else None, "hi": hi if any(x is not None for x in hi) else None,
                "margen": float(f[col["Margen_proyeccion"]]) if "Margen_proyeccion" in col and f[col["Margen_proyeccion"]] else u[k]["margen"]}
    return u


def nivel(u, x):
    """Regla de tu Excel: 3 si x < crítico_bajo o x ≥ crítico_alto; si no 2; si no 1; si no 0."""
    if x is None:
        return 0
    for n in (3, 2, 1):
        if (u["lo"] and u["lo"][n - 1] is not None and x < u["lo"][n - 1]) or \
           (u["hi"] and u["hi"][n - 1] is not None and x >= u["hi"][n - 1]):
            return n
    return 0


def lado(u, x):
    if x is None:
        return None
    if u["hi"] and u["hi"][0] is not None and x >= u["hi"][0]:
        return "alto"
    if u["lo"] and u["lo"][0] is not None and x < u["lo"][0]:
        return "bajo"
    return None


def _E(id, nombre, casos, disparador, tipico, accion, pasos, reducir, escalar, si_if, suprime=()):
    return dict(id=id, nombre=nombre, casos=casos, disparador=disparador, nivel_tipico=tipico, accion=accion,
                pasos=pasos, reducir=reducir, escalar=escalar, si_if_anomalo=si_if, suprime=list(suprime))


# ───────────────────────── CATÁLOGO · CORRECTIVO · CUERPO ─────────────────────────
ESC_CUERPO = [
 _E("B01", "Hipoglucemia", "C01", "Glucosa < 74 (precaución), < 70 (alerta), < 54 mg/dL (crítico)", "Precaución–Crítico",
    "Detener la tarea, sentarse o anclarse y dar ~15 g de carbohidrato rápido si está consciente.",
    "1) Medir de nuevo a los 15 min; repetir el carbohidrato si sigue < 70. 2) Al normalizar, refrigerio con carbohidrato complejo y proteína. 3) Revisar la causa: comida omitida, ejercicio, medicación. 4) Vigilar FC y confusión.",
    "Evitar tareas críticas (EVA, maniobras) hasta tener dos lecturas normales; planear comida antes del ejercicio; mantener carbohidrato rápido al alcance.",
    "Confusión, no puede tragar, convulsión o glucosa < 54 que no sube: ayuda médica inmediata y no dar nada por la boca si no responde.",
    "Si FC sube y HRV baja a la vez (activación simpática), es real y no artefacto."),
 _E("B02", "Hiperglucemia", "C02", "Glucosa ≥ 140 (precaución), ≥ 180 (alerta), ≥ 250 mg/dL (crítico)", "Precaución–Crítico",
    "Hidratarse con agua y revisar comida, medicación y estrés.",
    "1) Volver a medir en 1–2 h y registrar la tendencia. 2) Actividad ligera si no hay síntomas. 3) Seguir el plan médico si usa medicación o insulina. 4) Vigilar sed, visión borrosa y náuseas.",
    "Evitar bebidas azucaradas, mantener horarios de comida y actividad; vigilar la tendencia más que el valor aislado.",
    "≥ 250 persistente, náuseas o vómito, dolor abdominal, respiración rápida, somnolencia o confusión.",
    "Con PAS baja y FC alta a la vez, priorizar deshidratación (B14).", ()),
 _E("B03", "Presión arterial elevada", "C03", "PAS ≥ 130 o PAD ≥ 85 (precaución); PAS ≥ 140 o PAD ≥ 90 (alerta)", "Precaución–Alerta",
    "Reposar sentado 5 min con el brazo a la altura del corazón y repetir la medición.",
    "1) Promediar 2 mediciones separadas 1–2 min. 2) Reducir sal, cafeína y estimulantes. 3) Descartar dolor, estrés o ejercicio reciente. 4) Medir siempre con la misma postura y hora.",
    "Medicación solo según indicación médica; menos sodio de alimentos procesados; ejercicio y sueño regulares.",
    "≥ 140/90 sostenido: consultar en 24–48 h. Dolor de pecho, falta de aire, cefalea intensa o déficit neurológico: urgente.",
    "PA alta con HRV baja apunta a estrés o fatiga (B16, B11)."),
 _E("B04", "Crisis hipertensiva", "C04, C24", "PAS ≥ 180 y/o PAD ≥ 120 mmHg", "Crítico",
    "Confirmar tras 5 min de reposo; con síntomas es emergencia: avisar a la tripulación y al cirujano de vuelo.",
    "1) Reposo sentado y en calma; repetir a los 5 min. 2) No tomar dosis extra de medicamentos por cuenta propia. 3) Compartir PA y FC en tiempo real. 4) Permanecer acompañado.",
    "Reposo y entorno tranquilo hasta recibir indicaciones; revisar el CO₂ de cabina como factor agravante de cefalea.",
    "Siempre notificar. Emergencia si hay dolor torácico, falta de aire, cefalea intensa, confusión, debilidad de un lado o alteración visual.",
    "No esperar al modelo: un nivel crítico se alerta de inmediato y se reverifica en paralelo."),
 _E("B05", "Hipotensión", "C05", "PAS < 100 (precaución), < 90 (alerta), < 80 (crítico) o PAD < 60", "Precaución–Crítico",
    "Sentarse o acostarse (asegurado en microgravedad) y beber líquidos con electrolitos.",
    "1) Algo salado si no hay restricción. 2) Levantarse lentamente. 3) Medir de nuevo en 10–15 min. 4) Revisar deshidratación, calor, medicación, ayuno o sangrado.",
    "Hidratación programada, evitar cambios bruscos de postura y usar prendas de compresión según protocolo antes del regreso a la gravedad.",
    "PAS < 80 persistente, desmayo, dolor torácico, sangrado, heces negras o confusión.",
    "Con FC alta o temperatura alta, pasar a B14 o B19."),
 _E("B06", "Taquicardia en reposo", "C06", "FC ≥ 100 (precaución), ≥ 120 (alerta), ≥ 150 lpm (crítico) fuera de ejercicio", "Precaución–Crítico",
    "Sentarse 5–10 min con respiración lenta (inhalar 4 s, exhalar 6 s) y beber agua.",
    "1) Evitar cafeína, nicotina y alcohol. 2) Buscar causa: fiebre, deshidratación, ansiedad, dolor, medicación y CO₂ de cabina. 3) Recolocar el sensor y medir a los 10–15 min. 4) Registrar síntomas.",
    "Dormir y comer a horas fijas, hidratación programada y revisar la cabina antes de tratarlo como problema cardiaco.",
    "FC ≥ 120 persistente, dolor torácico, desmayo, falta de aire o mareo intenso; FC ≥ 150 con síntomas es emergencia.",
    "Mirar HRV, temperatura y CO₂ para separar estrés, infección y causa ambiental."),
 _E("B07", "Bradicardia", "C07", "FC < 50 (precaución), < 45 (alerta), < 40 lpm (crítico)", "Precaución–Crítico",
    "Preguntar por síntomas; con mareo o desmayo, sentarse o acostarse y no operar equipos.",
    "1) Sin síntomas y con buena condición física puede ser normal: comparar con la línea base individual. 2) Revisar medicación (p. ej. betabloqueantes) y colocación del sensor. 3) Tomar el pulso por otro método.",
    "Definir la línea base individual para no dar falsas alarmas; limitar el esfuerzo mientras haya síntomas.",
    "Síntomas, FC < 40, o junto a hipotensión, dolor torácico o desmayo. Portador de marcapasos: ver C21.",
    "Con PAS baja a la vez, tratar como B20."),
 _E("B08", "Fiebre / posible infección", "C08", "Temperatura ≥ 37,5 (precaución), ≥ 38,0 (alerta), ≥ 39,5 °C (crítico)", "Precaución–Crítico",
    "Hidratar, reposar y repetir la medición con el mismo método.",
    "1) Medir cada 4 h. 2) Aislar y usar mascarilla si hay síntomas respiratorios (hábitat cerrado). 3) Antipirético solo según indicación médica. 4) Registrar tos, garganta, diarrea.",
    "Higiene reforzada y limpieza de superficies para proteger a la tripulación; informar al cirujano de vuelo.",
    "> 48–72 h, ≥ 39,5 °C, rigidez de cuello, dificultad respiratoria, confusión, erupción o dolor abdominal intenso.",
    "Si el IF está normal, mandan las reglas: confirmar con una segunda medición y alertar."),
 _E("B09", "Hipotermia leve", "C09", "Temperatura < 36,0 (precaución), < 35,5 (alerta), < 35,0 °C (crítico)", "Precaución–Crítico",
    "Pasar a un lugar templado, retirar ropa húmeda y abrigar cabeza y cuello.",
    "1) Bebida tibia azucarada si está consciente. 2) Medir de nuevo a los 15–30 min y descartar sensor mal colocado. 3) Verificar el control térmico de cabina o traje.",
    "Revisar capas de ropa y calefacción; en EVA, verificar los sistemas térmicos del traje.",
    "< 35 °C con temblor intenso o ausente, confusión, somnolencia o habla arrastrada.",
    "Si la temperatura de cabina también es baja, tratar primero la cabina (K05)."),
 _E("B10", "SpO₂ baja", "C10", "SpO₂ < 95 (precaución), < 92 (alerta), < 90 % (crítico)", "Precaución–Crítico",
    "Verificar el sensor (manos tibias, quieto), sentarse erguido y respirar lento y profundo.",
    "1) Repetir 2–3 veces. 2) Revisar CO₂, O₂ y presión de cabina antes de atribuirlo a causa médica. 3) Oxígeno suplementario solo si lo indica el protocolo médico. 4) Registrar síntomas.",
    "Reducir esfuerzo y mantener buena ventilación en la zona de trabajo y descanso.",
    "< 90 % persistente, labios o dedos azulados, falta de aire en reposo, dolor torácico o confusión.",
    "SpO₂ baja con FC alta sugiere causa ambiental (B15).", ()),
 _E("B11", "HRV baja (sobrecarga fisiológica)", "C13, C38", "HRV (RMSSD) < 30 (precaución), < 20 (alerta), < 10 ms (crítico) · supuesto de demostración", "Precaución–Alerta",
    "Pausa de 5 min con respiración lenta 4-6 y reducir la carga de tareas.",
    "1) Revisar sueño, cafeína y estrés de las últimas 24 h. 2) Medir de nuevo en reposo y en la misma postura. 3) Evitar maniobras complejas si coincide con sueño corto o ánimo bajo.",
    "Protocolo de recuperación: sueño regular, luz adecuada, ejercicio moderado y apoyo psicológico.",
    "HRV muy baja sostenida con FC alta o síntomas; ánimo muy bajo o ideas de hacerse daño: apoyo psicológico inmediato.",
    "HRV baja con FC alta suele ser fatiga acumulada (B17)."),
 _E("B12", "Fiebre con taquicardia", "C08, C12", "Temperatura ≥ 37,5 y FC ≥ 100 a la vez", "Alerta",
    "Reposar, hidratar y medir temperatura y FC cada 30–60 min; aislar si hay síntomas.",
    "1) Aflojar capas de ropa y mejorar la ventilación local. 2) Hidratación en sorbos frecuentes. 3) Descartar sobrecalentamiento por esfuerzo (B13) y deshidratación (B14). 4) Informar al cirujano de vuelo.",
    "Aislar, reforzar higiene y vigilar a quienes estuvieron en contacto; reducir actividad hasta normalizar.",
    "≥ 39,5 °C, FC ≥ 120 persistente, confusión, rigidez de cuello o dificultad respiratoria.",
    "Aumentar la frecuencia de medición y compartir telemetría con Tierra.", ("B06", "B08")),
 _E("B13", "Sobrecalentamiento / golpe de calor por esfuerzo", "C12, C14", "Temperatura ≥ 38,5 °C con FC ≥ 120 (sudoración, piel caliente, confusión)", "Alerta–Crítico",
    "Detener el esfuerzo, enfriar (paños húmedos, ventilación, cuello, axilas e ingle) e hidratar.",
    "1) Medir temperatura cada 5–10 min hasta bajar de 38 °C. 2) Agua fría en sorbos si está alerta. 3) Revisar el enfriamiento del traje o de la cabina.",
    "Hidratar antes de EVA, limitar la duración y monitorear T y FC de forma continua (sin convección en microgravedad).",
    "≥ 40 °C, confusión, desmayo, convulsión o piel caliente y seca: emergencia.",
    "Tratarlo como real aunque venga de una ventana de ejercicio.", ("B06", "B08", "B12", "B18")),
 _E("B14", "Deshidratación / hipovolemia", "C11, C05", "PAS < 100 con FC ≥ 100", "Precaución–Alerta",
    "Rehidratar con agua o electrolitos en sorbos frecuentes y sentarse o anclarse.",
    "1) Descansar en lugar fresco; evitar cafeína y alcohol. 2) Repetir peso, FC y PA en 1–2 h. 3) Revisar pérdidas: sudor, diarrea, vómito, poca ingesta.",
    "Recordatorios de hidratación, sobre todo antes de EVA y del regreso a la gravedad.",
    "Vómito persistente, mareo intenso, confusión, orina casi nula o pérdida ≥ 5 % del peso.",
    "Revisar temperatura corporal y de cabina como causa de pérdidas.", ("B05", "B06")),
 _E("B15", "Hipoxia o hipercapnia de origen ambiental", "C10, C41", "SpO₂ baja, FC alta o HRV baja con CO₂, presión o ppO₂ de cabina fuera de rango", "Alerta",
    "Pasar a una zona con mejor ventilación, activar la circulación de aire y avisar a soporte vital.",
    "1) Verificar sensores de CO₂, O₂ y presión. 2) Reducir el esfuerzo. 3) Seguir los pasos de cabina K02 o K03. 4) Oxígeno según protocolo médico. 5) Registrar cefalea, somnolencia y mareo.",
    "Tratar la causa ambiental antes que la fisiología; volver a medir a los 10–15 min tras mejorar la ventilación.",
    "Confusión, desmayo, falta de aire intensa o alarma de soporte vital.",
    "Cuerpo y cabina anómalos a la vez confirman origen sistémico: priorizar la cabina.", ("B06", "B10")),
 _E("B16", "Estrés agudo", "C13", "FC 100–125 con PAS ≥ 130 o HRV baja, sin fiebre ni hipoxemia", "Precaución",
    "Detenerse, respirar lento 4-6 durante 3–5 min y usar anclaje 5-4-3-2-1.",
    "1) Beber agua; evitar cafeína. 2) Volver a medir en 10–15 min. 3) Hablar con alguien de confianza o con apoyo psicológico.",
    "Pausas programadas, carga de trabajo equilibrada y contacto con apoyo psicológico en Tierra.",
    "Dolor torácico, falta de aire intensa, desmayo, ideas de hacerse daño o síntomas que no ceden en 30 min.",
    "Descartar causa fisiológica (fiebre, hipoxemia) antes de clasificarlo como estrés.", ("B06", "B11")),
 _E("B17", "Fatiga / privación de sueño", "C38", "Sueño < 6 h con HRV baja", "Precaución",
    "Evitar tareas críticas (EVA, maniobras) y programar descanso.",
    "1) Ambiente oscuro, silencioso y fresco; sin cafeína ni pantallas 4–6 h antes. 2) Relajación y respiración. 3) Registrar horas y calidad del sueño.",
    "Horarios fijos e iluminación ajustable; revisar ruido y CO₂ de cabina durante el descanso.",
    "> 2 semanas, somnolencia peligrosa en tareas críticas o ánimo muy bajo.",
    "Restringir maniobras complejas mientras persista.", ("B11",)),
 _E("B18", "Efecto del ejercicio (esperado)", "C14", "Ejercicio o EVA con FC, PAS o temperatura algo elevadas, sin superar FC 150, PAS 180 ni 38,5 °C", "Precaución",
    "Reposar 10–30 min, hidratarse y volver a medir; no es patológico.",
    "1) Registrar tipo, duración e intensidad. 2) Reponer electrolitos. 3) Si no se normaliza en 30–60 min, aplicar el caso que corresponda (B06, B03 o B08).",
    "Marcar ventanas de ejercicio y EVA en el software para evitar falsas alarmas.",
    "Dolor torácico, mareo intenso, falta de aire desproporcionada o FC que no baja.",
    "Puede ser solo contexto: reevaluar al terminar la ventana."),
 _E("B19", "Inestabilidad hemodinámica", "C05, C06, C25, C35", "PAS < 90 con FC ≥ 120", "Crítico",
    "Acostar o asegurar, pedir ayuda médica ya y compartir telemetría en tiempo real.",
    "1) Comprobar respuesta y respiración. 2) Medir glucosa y SpO₂. 3) Considerar deshidratación, sangrado, arritmia, reacción alérgica grave o falla de soporte vital. 4) No dejarlo solo.",
    "Reposo con apoyo remoto del cirujano de vuelo hasta estabilizar.",
    "Siempre emergencia; RCP y DEA si no respira normalmente.",
    "No esperar al modelo.", ("B05", "B06", "B14")),
 _E("B20", "Riesgo de síncope (bradicardia con hipotensión)", "C07, C25", "FC < 50 con PAS < 100", "Alerta",
    "Sentarse o acostarse de inmediato, evitar esfuerzo y no operar equipos.",
    "1) Revisar medicación y colocación del sensor. 2) Verificar el pulso por otro método. 3) Medir de nuevo en 5–10 min. 4) Avisar al cirujano de vuelo.",
    "Evitar cambios bruscos de postura, hidratar y fijar la línea base individual.",
    "Desmayo, dolor torácico o FC < 40; portador de marcapasos: C21.",
    "Enviar ECG a Tierra si está disponible.", ("B05", "B07")),
 _E("B21", "Lectura dudosa de sensor", "C42", "Valor imposible o aislado (p. ej. FC = 0, SpO₂ > 100, PAS ≤ PAD, saltos bruscos)", "Precaución",
    "Verificar colocación, contacto y batería; repetir 2–3 veces con 1–2 min de intervalo.",
    "1) Contrastar con síntomas y otras variables. 2) Si persiste y hay síntomas, tratarla como real. 3) Si el nivel es crítico, alertar de inmediato y reverificar en paralelo.",
    "Filtros de calidad de señal y persistencia de 2 lecturas antes de alarmar (salvo crítico).",
    "Lectura anómala con síntomas o sensores que fallan repetidamente.",
    "IF anómalo con valor imposible: probable artefacto; aun así revalidar."),
 _E("B22", "Patrón inusual sin umbral excedido", "C00 + IF", "IF anómalo y ninguna regla en alerta", "Precaución",
    "Vigilancia reforzada: medir de nuevo en 5–10 min y preguntar por síntomas.",
    "1) Identificar las variables que más se alejan de su referencia (el sistema las lista). 2) Revisar contexto: ejercicio, comida, sueño, estrés, cabina. 3) Comprobar la calidad de señal.",
    "Actualizar la línea base individual si el patrón persiste sin síntomas.",
    "Aparición de síntomas o cruce de cualquier umbral.",
    "Es el caso donde el IF aporta: ningún umbral excedido pero combinación atípica."),
 _E("B23", "Sin hallazgos", "C00", "Todas las reglas en normal y IF sin anomalía", "Normal",
    "Continuar la rutina y el monitoreo programado.",
    "1) Hidratación, alimentación y sueño regulares. 2) Mediciones programadas. 3) Registrar síntomas nuevos.",
    "Mantener el ejercicio diario (contramedida ósea y muscular) y los chequeos periódicos.",
    "Síntomas (dolor, falta de aire, mareo, confusión) aunque las cifras sean normales.",
    "—"),
]

# ───────────────────────── CATÁLOGO · PREDICTIVO · CUERPO ─────────────────────────
ESC_PRED_CUERPO = [
 _E("P01", "Glucosa proyectada a la baja", "C01", "El pronóstico cruza o se acerca a glucosa < 74 mg/dL", "Aviso–Alerta",
    "Tomar un refrigerio de carbohidrato complejo con proteína antes de la próxima tarea exigente.",
    "1) Medir de nuevo en 15 min. 2) Dejar carbohidrato rápido a la mano. 3) Posponer ejercicio intenso o EVA si la tendencia sigue.",
    "Ajustar horarios y cantidad de comida al ejercicio; revisar medicación con el cirujano de vuelo.",
    "Si la lectura real baja de 70 pasa a B01.", "Si el IF también marca anomalía, confirmar con una medición manual."),
 _E("P02", "Glucosa proyectada al alza", "C02", "El pronóstico cruza o se acerca a glucosa ≥ 140 mg/dL", "Aviso–Alerta",
    "Hidratarse y evitar bebidas azucaradas; actividad ligera si no hay síntomas.",
    "1) Revisar la última comida y el estrés. 2) Medir de nuevo en 1–2 h.",
    "Distribuir las comidas y mantener la actividad diaria.",
    "Si la lectura real supera 180 pasa a B02.", "Revisar PAS y FC por posible deshidratación."),
 _E("P03", "Presión arterial proyectada al alza", "C03", "El pronóstico cruza o se acerca a PAS ≥ 130 o PAD ≥ 85", "Aviso–Alerta",
    "Reposar 5 min y evitar cafeína y estimulantes.", "1) Medir en reposo con técnica correcta. 2) Revisar sodio y estrés.",
    "Moderar la sal y mantener ejercicio y sueño regulares.", "Si cruza 140/90 sostenido pasa a B03.", "Con HRV baja proyectada, sumar medidas de manejo de estrés."),
 _E("P04", "Presión arterial proyectada a la baja", "C05", "El pronóstico cruza o se acerca a PAS < 100 o PAD < 60", "Aviso–Alerta",
    "Hidratarse y levantarse lentamente en las próximas horas.", "1) Tomar líquidos con electrolitos. 2) Evitar cambios bruscos de postura. 3) Medir en 10–15 min.",
    "Hidratación programada y prendas de compresión según protocolo.", "Si la lectura real baja de 90 pasa a B05.", "Con FC alta proyectada, ver P12."),
 _E("P05", "Frecuencia cardiaca proyectada al alza", "C06", "El pronóstico cruza o se acerca a FC ≥ 100 en reposo", "Aviso–Alerta",
    "Respiración lenta 4-6 durante 3 min y beber agua antes de que suba.", "1) Evitar cafeína. 2) Revisar fiebre, hidratación, estrés y CO₂ de cabina. 3) Medir en 10 min.",
    "Descanso programado y revisión de cabina.", "Si cruza 120 en reposo pasa a B06.", "Mirar HRV y temperatura proyectadas."),
 _E("P06", "Frecuencia cardiaca proyectada a la baja", "C07", "El pronóstico cruza o se acerca a FC < 50", "Aviso–Alerta",
    "Preguntar por mareo o fatiga y evitar movimientos bruscos.", "1) Comparar con la línea base individual. 2) Revisar medicación y sensor.",
    "Definir línea base individual.", "Con síntomas o PAS baja pasa a B07 o B20.", "Con PAS baja proyectada, preparar medidas contra síncope."),
 _E("P07", "Temperatura corporal proyectada al alza", "C08, C12", "El pronóstico cruza o se acerca a temperatura ≥ 37,5 °C", "Aviso–Alerta",
    "Hidratar, reducir la carga física y mejorar la ventilación local.", "1) Aflojar capas de ropa. 2) Medir con el mismo método a los 30 min. 3) Revisar temperatura de cabina.",
    "Hidratación previa al esfuerzo; vigilar contactos si hay síntomas.", "Si la lectura real supera 38,0 pasa a B08.", "Con FC alta proyectada, ver P11."),
 _E("P08", "Temperatura corporal proyectada a la baja", "C09", "El pronóstico cruza o se acerca a temperatura < 36,0 °C", "Aviso–Alerta",
    "Abrigarse y tomar una bebida tibia.", "1) Revisar la temperatura de cabina o del traje. 2) Medir de nuevo en 15–30 min.",
    "Ajustar ropa y calefacción.", "Si baja de 35,5 pasa a B09.", "Descartar sensor mal colocado."),
 _E("P09", "SpO₂ proyectada a la baja", "C10", "El pronóstico cruza o se acerca a SpO₂ < 95 %", "Aviso–Alerta",
    "Verificar el sensor y mejorar la ventilación; respirar profundo.", "1) Revisar CO₂, O₂ y presión de cabina. 2) Reducir esfuerzo. 3) Preparar oxígeno según protocolo.",
    "Mantener circulación de aire en las zonas de trabajo y descanso.", "Si la lectura real baja de 92 pasa a B10.", "Con FC alta proyectada, ver P13."),
 _E("P10", "HRV proyectada a la baja", "C13, C38", "El pronóstico cruza o se acerca a HRV < 30 ms · supuesto", "Aviso",
    "Programar una pausa de recuperación y bajar la carga de tareas.", "1) Priorizar el sueño de esta noche. 2) Evitar cafeína tarde.",
    "Rutina de sueño y apoyo psicológico.", "Si la lectura real baja de 20 pasa a B11.", "Con FC alta proyectada, ver P14."),
 _E("P11", "Fiebre o hipertermia incipiente", "C08, C12", "FC y temperatura proyectadas al alza a la vez", "Alerta",
    "Reposo, hidratación y medición cada 30 min; preparar aislamiento si hay síntomas.", "1) Mejorar ventilación y retirar capas. 2) Avisar al cirujano de vuelo. 3) Revisar actividad reciente.",
    "Reducir esfuerzo y reforzar higiene.", "Si ambas cruzan pasa a B12 o B13.", "Compartir pronóstico con Tierra.", ("P05", "P07")),
 _E("P12", "Deshidratación incipiente", "C11, C05", "FC proyectada al alza con PAS proyectada a la baja", "Alerta",
    "Rehidratar ahora con electrolitos y reducir esfuerzo.", "1) Repetir peso, FC y PA en 1–2 h. 2) Revisar pérdidas (sudor, diarrea, vómito).",
    "Hidratación programada antes de EVA.", "Si cruzan pasa a B14 o B19.", "Revisar temperatura de cabina.", ("P04", "P05")),
 _E("P13", "Hipoxia o hipercapnia incipiente", "C10, C41", "SpO₂ proyectada a la baja con FC proyectada al alza", "Alerta",
    "Revisar CO₂, O₂ y presión de cabina de inmediato y mejorar la ventilación.", "1) Reducir esfuerzo. 2) Preparar oxígeno. 3) Avisar a soporte vital.",
    "Tratar la causa ambiental antes de que se manifieste.", "Si cruza pasa a B15.", "Con cabina proyectada fuera de rango, ver Q08.", ("P05", "P09")),
 _E("P14", "Estrés o fatiga acumulada", "C13, C38", "FC proyectada al alza con HRV proyectada a la baja", "Aviso–Alerta",
    "Pausa de respiración lenta y reducir tareas de alta exigencia.", "1) Priorizar sueño. 2) Contacto con apoyo psicológico.",
    "Carga de trabajo equilibrada y descanso programado.", "Si cruzan pasa a B16 o B17.", "Evitar maniobras complejas si persiste.", ("P05", "P10")),
 _E("P15", "Recuperación proyectada", "C14", "Algún valor alterado y el pronóstico vuelve hacia el rango normal", "Aviso",
    "Mantener las medidas en curso y no suspenderlas hasta confirmar con la siguiente medición.", "1) Volver a medir en 10–15 min. 2) Registrar qué ayudó.",
    "Mantener hidratación y descanso.", "Si el valor real no mejora en 30–60 min, volver al caso correctivo.", "Con IF anómalo, confirmar la mejoría con medición manual."),
 _E("P16", "Sin riesgo proyectado", "C00, C23", "Todo normal y el pronóstico estable", "Normal",
    "Continuar la rutina y las contramedidas preventivas.", "1) Hidratación, sueño y ejercicio diarios. 2) Mediciones programadas.",
    "Mantener ejercicio de resistencia, proteína, calcio y vitamina D según plan médico (pérdida muscular y ósea).", "Cualquier cruce proyectado activa su escenario.", "—"),
]

# ───────────────────────── CATÁLOGO · CORRECTIVO · CABINA ─────────────────────────
ESC_CABINA = [
 _E("K01", "CO₂ de cabina elevado", "C41, C26", "ppCO₂ ≥ 4,0 (precaución), ≥ 5,3 (alerta), ≥ 7,6 mmHg (crítico) ≈ 5.300 / 7.000 / 10.000 ppm", "Precaución–Crítico",
    "Mejorar la ventilación y verificar los sensores de CO₂ de la cabina.",
    "1) Activar la circulación de aire y revisar el depurador (lecho en servicio, filtros). 2) Reducir el esfuerzo de la tripulación. 3) Reportar a soporte vital. 4) Preguntar por cefalea, somnolencia y mareo.",
    "Evitar bolsas de aire estancado cerca de la cabeza (sin convección el CO₂ se acumula); planear conmutación preventiva del depurador.",
    "Confusión, desmayo, falta de aire intensa o alarma del soporte vital.",
    "IF anómalo en cuerpo y cabina a la vez confirma origen sistémico."),
 _E("K02", "Hipercapnia con efecto en la tripulación", "C41, C06, C26", "CO₂ fuera de rango con FC alta o HRV baja (la SpO₂ puede seguir normal)", "Alerta",
    "Sacar a la tripulación del área afectada, ventilar y bajar el esfuerzo.",
    "1) Conmutar al lecho de depurador de respaldo. 2) Confirmar con el sensor redundante. 3) Vigilar FC, cefalea y respiración. 4) No tratarlo como problema cardiaco hasta corregir el aire.",
    "Priorizar la corrección del aire antes que la atención clínica de síntomas.",
    "Confusión, desmayo o dificultad respiratoria: emergencia.",
    "Confirma causa ambiental.", ("K01",)),
 _E("K03", "Presión baja o ppO₂ baja (posible fuga)", "C10, C25", "Presión < 98 (precaución), < 95 (alerta), < 90 kPa (crítico) o ppO₂ < 17 / 16 / 14 kPa", "Precaución–Crítico",
    "Avisar a la tripulación, aislar el módulo sospechoso y verificar la tendencia de presión.",
    "1) Localizar la fuga (detector ultrasónico). 2) Reponer O₂/N₂ desde reserva. 3) Equipar trajes de presión. 4) Preparar el cierre de escotillas.",
    "Medir la tasa de caída (kPa/min) para estimar cuánto tiempo queda; mantener libres las rutas hacia el módulo seguro.",
    "Caída continua, SpO₂ baja o alarma de presión: emergencia.",
    "Con SpO₂ baja en el cuerpo, la hipoxia es ambiental (B15)."),
 _E("K04", "Temperatura de cabina alta", "C12, C08", "Temperatura de cabina ≥ 26,7 (precaución), ≥ 30 (alerta), ≥ 35 °C (crítico)", "Precaución–Crítico",
    "Mejorar la ventilación y reducir la carga térmica y la actividad.",
    "1) Revisar el lazo de enfriamiento y equipos de alta disipación. 2) Hidratar a la tripulación. 3) Vigilar temperatura corporal y FC.",
    "Reprogramar tareas de esfuerzo a horas más frescas.", "≥ 35 °C o síntomas de golpe de calor (confusión, piel caliente y seca).",
    "Con temperatura corporal alta, ver B13."),
 _E("K05", "Temperatura de cabina baja", "C09", "Temperatura de cabina < 18,3 (precaución), < 16 (alerta), < 12 °C (crítico)", "Precaución–Crítico",
    "Verificar la calefacción y abrigar a la tripulación.", "1) Revisar el control térmico. 2) Cerrar zonas frías. 3) Vigilar temperatura corporal.",
    "Ajustar capas de ropa y zonas de descanso.", "< 12 °C o hipotermia en tripulantes.", "Con temperatura corporal baja, ver B09."),
 _E("K06", "Humedad alta", "C34", "Humedad ≥ 60 (precaución), ≥ 70 (alerta), ≥ 85 % (crítico)", "Precaución–Crítico",
    "Revisar el deshumidificador y el sistema de condensado.", "1) Inspeccionar condensación en paneles y equipos. 2) Aumentar la ventilación. 3) Limpiar superficies húmedas.",
    "Prevenir moho y daño a electrónica; vigilar fugas de líquido.", "Condensación sobre electrónica o goteo.", "Con CO₂ alto a la vez, ver K10."),
 _E("K07", "Humedad baja", "C30, C34", "Humedad < 30 (precaución), < 25 (alerta), < 15 % (crítico)", "Precaución–Crítico",
    "Revisar el humidificador y la tasa de ventilación.", "1) Hidratar a la tripulación. 2) Gotas lubricantes oculares si hay irritación. 3) Vigilar electricidad estática.",
    "Ajustar la humedad objetivo del hábitat.", "Irritación ocular o respiratoria persistente.", "—"),
 _E("K08", "Ruido elevado", "C38", "Ruido ≥ 55 (precaución), ≥ 65 (alerta), ≥ 85 dBA (crítico)", "Precaución–Crítico",
    "Localizar la fuente (ventilador, bomba) y usar protección auditiva.", "1) Limitar el tiempo de exposición. 2) Revisar equipos con vibración. 3) Mantener las zonas de descanso silenciosas.",
    "Mantenimiento de ventiladores y bombas; programar el sueño en zonas tranquilas.", "≥ 85 dBA sostenido o pérdida auditiva.", "Con HRV baja o sueño corto, ver B17."),
 _E("K09", "Radiación elevada / tormenta solar", "—", "Dosis ≥ 1,0 (precaución), ≥ 5,0 (alerta), ≥ 12 mSv/día (crítico)", "Precaución–Crítico",
    "Mover a la tripulación al refugio de tormenta y suspender actividades extravehiculares.",
    "1) Leer los dosímetros personales. 2) Vigilar náuseas, vómito y fiebre. 3) Reportar la dosis acumulada a Tierra.",
    "Reprogramar EVA a ventanas de baja actividad solar.", "Náuseas, vómito o fiebre tras exposición alta.", "Con fiebre y radiación alta, vigilar síndrome de radiación."),
 _E("K10", "Aire estancado / ventilación degradada", "C41, C12", "CO₂ alto con temperatura o humedad de cabina fuera de rango", "Alerta",
    "Restablecer la circulación de aire y revisar ventiladores y filtros.", "1) Revisar el lazo de ventilación y el intercambiador. 2) Conmutar al equipo de respaldo. 3) Reducir actividad.",
    "Evitar zonas sin flujo; programar limpieza de filtros.", "Subida rápida de CO₂ o alarma de soporte vital.", "Confirma origen común del fallo.", ("K01", "K04", "K06")),
 _E("K11", "Sensor de cabina dudoso o en estimación", "C42", "Valor imposible o variable en modo estimado por IA", "Precaución",
    "Validar con el sensor redundante antes de actuar sobre la cabina.", "1) Revisar alimentación y calibración. 2) Comparar con variables relacionadas. 3) Mantener vigilancia mientras la confianza sea baja.",
    "Programar el reemplazo o la calibración del sensor.", "Cabina estimada con confianza < 60 % o síntomas en la tripulación.", "—"),
 _E("K12", "Cabina sin hallazgos", "C00", "Todas las condiciones de cabina en rango", "Normal",
    "Continuar el monitoreo y el mantenimiento programado.", "1) Registrar lecturas. 2) Mantener filtros y calibraciones al día.",
    "Rutina de inspección de ECLSS.", "Cualquier variable fuera de rango.", "—"),
 _E("K13", "Emergencia de cabina combinada", "C41, C10", "Dos o más variables de cabina en alerta o una en crítico", "Crítico",
    "Declarar emergencia: suspender tareas no esenciales y colocarse el equipo de protección.",
    "1) Ir al módulo seguro y aislar el afectado. 2) Activar protocolos de soporte vital. 3) Contactar a Tierra. 4) Vigilar a cada tripulante.",
    "Mantener apoyo remoto del cirujano de vuelo y de ingeniería ECLSS.", "Siempre emergencia.", "No esperar al modelo."),
]

# ───────────────────────── CATÁLOGO · PREDICTIVO · CABINA ─────────────────────────
ESC_PRED_CABINA = [
 _E("Q01", "CO₂ proyectado al alza", "C41", "El pronóstico cruza o se acerca a ppCO₂ ≥ 4,0 mmHg (≈ 5.300 ppm)", "Aviso–Alerta",
    "Conmutar el depurador de forma preventiva y aumentar la circulación de aire.", "1) Inspeccionar filtros y el lecho en servicio. 2) Reducir actividades de alto esfuerzo. 3) Avisar a soporte vital.",
    "Programar la regeneración o el reemplazo del lecho antes del umbral.", "Si la lectura real cruza el umbral pasa a K01.", "Con IF anómalo, confirmar con el sensor redundante."),
 _E("Q02", "Presión u O₂ proyectados a la baja", "C10", "El pronóstico cruza o se acerca a presión < 98 kPa o ppO₂ < 17 kPa", "Aviso–Alerta",
    "Verificar la tendencia de presión y revisar escotillas y sellos.", "1) Calcular la tasa de caída. 2) Inspeccionar con detector ultrasónico. 3) Revisar reservas de O₂/N₂.",
    "Detectar la fuga cuando aún es pequeña.", "Caída sostenida pasa a K03.", "Con SpO₂ baja proyectada, ver P09."),
 _E("Q03", "Temperatura de cabina proyectada fuera de rango", "C08, C09, C12", "El pronóstico cruza o se acerca a 18,3 °C (baja) o 26,7 °C (alta)", "Aviso",
    "Revisar el control térmico y ajustar el lazo de enfriamiento o la calefacción.", "1) Reducir cargas térmicas. 2) Vigilar temperatura corporal.",
    "Ajustar el punto de consigna antes de que la tripulación lo note.", "Si cruza pasa a K04 o K05.", "—"),
 _E("Q04", "Humedad proyectada fuera de rango", "C30, C34", "El pronóstico cruza o se acerca a 30 % (baja) o 60 % (alta)", "Aviso",
    "Ajustar humidificador o deshumidificador.", "1) Inspeccionar condensado. 2) Aumentar o reducir la ventilación.",
    "Prevenir moho, condensación y resequedad.", "Si cruza pasa a K06 o K07.", "—"),
 _E("Q05", "Ruido proyectado al alza", "C38", "El pronóstico cruza o se acerca a 55 dBA", "Aviso",
    "Revisar equipos con vibración (ventiladores, bombas) y preparar protección auditiva.", "1) Programar mantenimiento del equipo sospechoso. 2) Proteger las zonas de descanso.",
    "Mantenimiento preventivo de ventiladores.", "Si cruza pasa a K08.", "—"),
 _E("Q06", "Radiación proyectada al alza", "—", "El pronóstico cruza o se acerca a 1,0 mSv/día", "Aviso–Alerta",
    "Preparar el refugio de tormenta y revisar el calendario de actividades extravehiculares.", "1) Verificar dosímetros. 2) Avisar a la tripulación.",
    "Posponer EVA si la tendencia continúa.", "Si cruza pasa a K09.", "—"),
 _E("Q07", "Ventilación degradándose", "C41, C12", "CO₂ y temperatura de cabina proyectados al alza a la vez", "Alerta",
    "Revisar el lazo de ventilación, ventiladores e intercambiador antes de que se acumule.", "1) Conmutar al equipo de respaldo. 2) Reducir actividad.",
    "Mantenimiento correctivo anticipado del lazo de aire.", "Si cruzan pasa a K10.", "Confirma origen común.", ("Q01", "Q03")),
 _E("Q08", "Efecto cabina → cuerpo", "C41, C06, C26", "CO₂ proyectado al alza con FC proyectada al alza o HRV proyectada a la baja", "Alerta",
    "Corregir la cabina primero y reducir el esfuerzo de la tripulación.", "1) Reposar y vigilar cefalea. 2) Medir FC y HRV cada 10 min. 3) Preparar oxígeno.",
    "Evitar que la fisiología se deteriore antes de corregir el aire.", "Si cruzan pasa a K02 o B15.", "Refuerza causa ambiental.", ("Q01",)),
 _E("Q09", "Recuperación de cabina proyectada", "—", "Alguna variable alterada y el pronóstico vuelve hacia el rango normal", "Aviso",
    "Mantener las medidas en curso hasta confirmar con la lectura real.", "1) Medir de nuevo en 10–15 min. 2) Registrar qué corrigió el problema.",
    "Dejar documentada la causa.", "Si no mejora, volver al caso correctivo.", "—"),
 _E("Q10", "Cabina estable", "C00", "Todo normal y el pronóstico estable", "Normal",
    "Continuar con el mantenimiento rutinario de ECLSS.", "1) Limpieza de filtros. 2) Calibración programada de sensores.",
    "Inspecciones periódicas.", "Cualquier cruce proyectado activa su escenario.", "—"),
]

# ─────────────────────────────── LÓGICA ───────────────────────────────
def _nota_if(max_reglas, if_result):
    if not if_result or if_result.get("anomaly") is None:
        return "E", "IF no disponible: decisión solo por reglas. Mantener persistencia de 2 lecturas salvo nivel crítico."
    an = bool(if_result["anomaly"])
    if max_reglas >= 1 and an:
        return "A", "Reglas e IF coinciden: tratar como real, reducir a la mitad el intervalo de medición y compartir telemetría."
    if max_reglas >= 1:
        return "B", "Solo las reglas alertan (el IF no ve patrón multivariado): puede ser una desviación aislada. Verificar sensor y contexto; si es crítico, no esperar."
    if an:
        return "C", "Patrón inusual sin umbral excedido: vigilancia reforzada y revisar qué variables se alejan de su referencia."
    return "D", "Sin hallazgos: sin acción adicional por el IF."


class _Ctx:
    def __init__(self, v, L, lado_, ej, if_anom, dudosas, estimados, ej_elev, ej_exceso):
        self.v, self.L, self.lado, self.ej, self.if_anomalo = v, L, lado_, ej, if_anom
        self.dudosas, self.estimados, self.ej_elev, self.ej_exceso = dudosas, estimados, ej_elev, ej_exceso
        self.max_cuerpo = max([L.get(k, 0) for k in CUERPO] + [0])
        self.max_cabina = max([L.get(k, 0) for k in CABINA] + [0])
        self.cab_resp = max(L.get("co2", 0), L.get("pres", 0), L.get("ppo2", 0))
        self.n_cab_alerta = sum(1 for k in CABINA if L.get(k, 0) >= 2)

    def alto(self, k, n=1): return self.lado.get(k) == "alto" and self.L.get(k, 0) >= n
    def bajo(self, k, n=1): return self.lado.get(k) == "bajo" and self.L.get(k, 0) >= n
    def g(self, k): return -math.inf if self.v.get(k) is None else self.v[k]


# id: (condición, variables que fijan el nivel, nivel mínimo)
LOGICA_CUERPO = {
 "B01": (lambda c: c.bajo("glu"), ("glu",), 1), "B02": (lambda c: c.alto("glu"), ("glu",), 1),
 "B03": (lambda c: (c.alto("sis") or c.alto("dia")) and not (c.alto("sis", 3) or c.alto("dia", 3)), ("sis", "dia"), 1),
 "B04": (lambda c: c.alto("sis", 3) or c.alto("dia", 3), ("sis", "dia"), 3),
 "B05": (lambda c: c.bajo("sis") or c.bajo("dia"), ("sis", "dia"), 1),
 "B06": (lambda c: c.alto("fc") and not c.ej, ("fc",), 1), "B07": (lambda c: c.bajo("fc"), ("fc",), 1),
 "B08": (lambda c: c.alto("temp"), ("temp",), 1), "B09": (lambda c: c.bajo("temp"), ("temp",), 1),
 "B10": (lambda c: c.bajo("spo2"), ("spo2",), 1), "B11": (lambda c: c.bajo("hrv"), ("hrv",), 1),
 "B12": (lambda c: c.alto("temp") and c.alto("fc"), ("temp", "fc"), 2),
 "B13": (lambda c: c.g("temp") >= 38.5 and c.g("fc") >= 120, ("temp", "fc"), 2),
 "B14": (lambda c: c.bajo("sis") and c.alto("fc"), ("sis", "fc"), 1),
 "B15": (lambda c: (c.bajo("spo2") or c.alto("fc") or c.bajo("hrv")) and c.cab_resp >= 1, ("spo2", "fc", "co2", "pres", "ppo2"), 2),
 "B16": (lambda c: 100 <= c.g("fc") <= 125 and (c.alto("sis") or c.bajo("hrv")) and not c.alto("temp") and not c.bajo("spo2") and c.cab_resp == 0 and not c.ej, (), 1),
 "B17": (lambda c: c.v.get("sueno") is not None and c.v["sueno"] < 6 and c.bajo("hrv"), (), 1),
 "B18": (lambda c: c.ej and c.ej_elev and not c.ej_exceso, (), 1),
 "B19": (lambda c: c.bajo("sis", 2) and c.alto("fc", 2), ("sis", "fc"), 3),
 "B20": (lambda c: c.bajo("fc") and c.bajo("sis"), ("fc", "sis"), 2),
 "B21": (lambda c: bool(c.dudosas), (), 1),
 "B22": (lambda c: bool(c.if_anomalo) and c.max_cuerpo == 0 and c.max_cabina == 0 and not c.dudosas, (), 1),
 "B23": (lambda c: c.max_cuerpo == 0 and c.max_cabina == 0 and not c.if_anomalo and not c.dudosas and not c.ej_elev, (), 0)}
LOGICA_CABINA = {
 "K01": (lambda c: c.alto("co2"), ("co2",), 1),
 "K02": (lambda c: c.alto("co2") and (c.alto("fc") or c.bajo("hrv")), ("co2",), 2),
 "K03": (lambda c: c.bajo("pres") or c.bajo("ppo2"), ("pres", "ppo2"), 1),
 "K04": (lambda c: c.alto("tcab"), ("tcab",), 1), "K05": (lambda c: c.bajo("tcab"), ("tcab",), 1),
 "K06": (lambda c: c.alto("hum"), ("hum",), 1), "K07": (lambda c: c.bajo("hum"), ("hum",), 1),
 "K08": (lambda c: c.alto("ruido"), ("ruido",), 1), "K09": (lambda c: c.alto("rad"), ("rad",), 1),
 "K10": (lambda c: c.alto("co2") and (c.alto("tcab") or c.alto("hum")), ("co2", "tcab", "hum"), 2),
 "K11": (lambda c: any(k in CABINA or k == "co2" for k in c.dudosas) or any(k in CABINA for k in c.estimados), (), 1),
 "K12": (lambda c: c.max_cabina == 0 and not any(k in CABINA for k in c.dudosas) and not any(k in CABINA for k in c.estimados), (), 0),
 "K13": (lambda c: c.n_cab_alerta >= 2 or any(c.L.get(k, 0) >= 3 for k in CABINA), (), 3)}

_RANGOS = {"fc": (1, 250), "spo2": (50, 100.5), "temp": (30, 43), "glu": (20, 600), "hrv": (0, 500), "sis": (40, 280),
           "dia": (20, 180), "co2": (300, 50000), "pres": (30, 120), "tcab": (-20, 60), "hum": (0, 100), "ruido": (1, 140)}


def _dudosas(v):
    d = [k for k, (a, b) in _RANGOS.items() if v.get(k) is not None and not (a <= v[k] <= b)]
    if v.get("sis") is not None and v.get("dia") is not None and v["sis"] <= v["dia"]:
        d += ["sis", "dia"]
    return d


class Proy(dict):
    __getattr__ = dict.get


def proyectar(u, cur, pred, paso_s=3.0, pasos=1):
    """Compara el valor actual con el pronóstico. tipo: cruza | empeora | se_acerca | mejora | persiste | estable."""
    l0, lp, d = nivel(u, cur), nivel(u, pred), pred - cur
    ld = lado(u, pred)
    if ld is None:
        m = u["margen"]
        if d > 0 and u["hi"] and u["hi"][0] is not None and pred >= u["hi"][0] - m:
            ld = "alto"
        elif d < 0 and u["lo"] and u["lo"][0] is not None and pred < u["lo"][0] + m:
            ld = "bajo"
    hacia = (ld == "alto" and d > 0) or (ld == "bajo" and d < 0)
    if lp > l0: tipo = "cruza"
    elif lp < l0: tipo = "mejora"
    elif lp >= 1: tipo = "empeora" if hacia else ("mejora" if d != 0 else "persiste")
    elif ld and hacia: tipo = "se_acerca"
    else: tipo = "estable"
    activo = tipo in ("cruza", "empeora", "se_acerca")
    eta = None
    if activo and d != 0:
        lado_u = u["hi"] if ld == "alto" else u["lo"]
        objetivo = lado_u[l0] if lado_u and l0 < 3 else None
        pendiente = d / max(pasos, 1)
        if objetivo is not None and (objetivo - cur) * pendiente > 0:
            eta = round((objetivo - cur) / pendiente * paso_s)
    return Proy(l0=l0, lp=lp, delta=d, lado=ld, tipo=tipo, activo=activo, alto=activo and ld == "alto",
                bajo=activo and ld == "bajo", eta_s=eta)


LOGICA_PRED_CUERPO = {
 "P01": (lambda p: p["glu"].bajo, ("glu",)), "P02": (lambda p: p["glu"].alto, ("glu",)),
 "P03": (lambda p: p["sis"].alto or p["dia"].alto, ("sis", "dia")), "P04": (lambda p: p["sis"].bajo or p["dia"].bajo, ("sis", "dia")),
 "P05": (lambda p: p["fc"].alto, ("fc",)), "P06": (lambda p: p["fc"].bajo, ("fc",)),
 "P07": (lambda p: p["temp"].alto, ("temp",)), "P08": (lambda p: p["temp"].bajo, ("temp",)),
 "P09": (lambda p: p["spo2"].bajo, ("spo2",)), "P10": (lambda p: p["hrv"].bajo, ("hrv",)),
 "P11": (lambda p: p["fc"].alto and p["temp"].alto, ("fc", "temp")),
 "P12": (lambda p: p["fc"].alto and p["sis"].bajo, ("fc", "sis")),
 "P13": (lambda p: p["spo2"].bajo and p["fc"].alto, ("spo2", "fc")),
 "P14": (lambda p: p["fc"].alto and p["hrv"].bajo, ("fc", "hrv")),
 "P15": (lambda p: any(x.tipo == "mejora" for x in p.values()) and not any(x.activo for x in p.values()), ()),
 "P16": (lambda p: not any(x.activo or x.tipo == "mejora" or x.l0 for x in p.values()), ())}
LOGICA_PRED_CABINA = {
 "Q01": (lambda p: p["co2"].alto, ("co2",)), "Q02": (lambda p: p["pres"].bajo or p["ppo2"].bajo, ("pres", "ppo2")),
 "Q03": (lambda p: p["tcab"].activo, ("tcab",)), "Q04": (lambda p: p["hum"].activo, ("hum",)),
 "Q05": (lambda p: p["ruido"].alto, ("ruido",)), "Q06": (lambda p: p["rad"].alto, ("rad",)),
 "Q07": (lambda p: p["co2"].alto and p["tcab"].alto, ("co2", "tcab")),
 "Q08": (lambda p: p["co2"].alto and (p["fc"].alto or p["hrv"].bajo), ("co2", "fc", "hrv")),
 "Q09": (lambda p: any(x.tipo == "mejora" for x in p.values()) and not any(x.activo for x in p.values()), ()),
 "Q10": (lambda p: not any(x.activo or x.tipo == "mejora" or x.l0 for x in p.values()), ())}


def _rec(e, nivel_, **extra):
    r = {k: e[k] for k in ("id", "nombre", "casos", "accion", "pasos", "reducir", "escalar")}
    r.update(nivel=nivel_, nivel_nombre=NIVELES[nivel_], **extra)
    return r


def _filtrar(activos):
    quitar = {s for e, _ in activos for s in e["suprime"]}
    return [(e, n) for e, n in activos if e["id"] not in quitar]


class Evaluador:
    def __init__(self, umbrales=None, persistencia=2):
        self.u, self.persistencia, self._cuenta = umbrales or UMBRALES, persistencia, {}

    def _valores(self, d):
        v = {k: d.get(full) for k, full in ALIAS.items()}
        if v["ppo2"] is None and v["pres"] is not None:
            v["ppo2"] = v["pres"] * 0.2094
        return v

    def evaluar(self, valores, if_result=None, pron=None, actividad="rest", paso_s=3.0, estimados=()):
        v = self._valores(valores)
        veq = dict(v)
        if v["co2"] is not None and v["pres"] is not None:
            veq["co2"] = v["co2"] * v["pres"] / 101.3  # ppCO₂ equivalente a presión normal
        ej = str(actividad).lower() in EJERCICIO
        L = {k: nivel(self.u[k], veq[k]) for k in self.u if veq.get(k) is not None}
        ld = {k: lado(self.u[k], veq[k]) for k in L}
        ej_elev = ej and any(ld.get(k) == "alto" for k in LIM_EJ)
        ej_exceso = ej and any(veq.get(k) is not None and veq[k] >= LIM_EJ[k] for k in LIM_EJ)
        if ej:
            for k, lim in LIM_EJ.items():
                if veq.get(k) is not None and veq[k] < lim:
                    L[k], ld[k] = 0, None
        est = [k for k, full in ALIAS.items() if full in set(estimados) or k in set(estimados)]
        c = _Ctx(veq, L, ld, ej, (if_result or {}).get("anomaly"), _dudosas(veq), est, ej_elev, ej_exceso)
        max_reglas = max(c.max_cuerpo, c.max_cabina)
        clave, texto = _nota_if(max_reglas, if_result)
        z = sorted(((abs(veq[k] - REFERENCIA[k]) / SIGMA[k], k) for k in REFERENCIA if veq.get(k) is not None), reverse=True)[:3]
        res = {"if": {"clave": clave, "texto": texto, "contribuyentes": [{"variable": ALIAS[k], "z": round(x, 1)} for x, k in z]},
               "global": {"nivel": max_reglas, "nombre": NIVELES[max_reglas]}}
        res["cuerpo"] = {"nivel": c.max_cuerpo, "correctivo": self._corr(ESC_CUERPO, LOGICA_CUERPO, c),
                         "predictivo": []}
        res["cabina"] = {"nivel": c.max_cabina, "correctivo": self._corr(ESC_CABINA, LOGICA_CABINA, c), "predictivo": []}
        if pron:
            res["cuerpo"]["predictivo"], res["cabina"]["predictivo"] = self._pred(v, pron, paso_s, c)
        else:
            res["cuerpo"]["predictivo"] = res["cabina"]["predictivo"] = {"estado": "calentando"}
        return res

    def _corr(self, catalogo, logica, c):
        activos = []
        for e in catalogo:
            cond, vars_, minimo = logica[e["id"]]
            if cond(c):
                n = max([c.L.get(k, 0) for k in vars_] + [minimo])
                activos.append((e, min(n, 3)))
        activos = _filtrar(activos)
        ids = {e["id"] for e, _ in activos}
        self._cuenta = {i: n for i, n in self._cuenta.items() if i in ids or not i.startswith(catalogo[0]["id"][0])}
        out = []
        for e, n in sorted(activos, key=lambda t: (-t[1], t[0]["id"])):
            self._cuenta[e["id"]] = self._cuenta.get(e["id"], 0) + 1
            conf = n >= 3 or n == 0 or self._cuenta[e["id"]] >= self.persistencia
            out.append(_rec(e, n, confirmado=conf, pendiente=not conf,
                            si_if_anomalo=e["si_if_anomalo"] if c.if_anomalo else None))
        return out

    def _pred(self, v, pron, paso_s, c):
        pasos = len(pron) if isinstance(pron, list) else 1
        fin = self._valores(pron[-1] if isinstance(pron, list) else pron)
        P = {k: proyectar(self.u[k], v[k], fin[k], paso_s, pasos) for k in self.u if v.get(k) is not None and fin.get(k) is not None}
        neutro = Proy(l0=0, lp=0, delta=0, lado=None, tipo="estable", activo=False, alto=False, bajo=False, eta_s=None)
        Pk = {k: P.get(k, neutro) for k in self.u}
        sal = []
        for cat, log in ((ESC_PRED_CUERPO, LOGICA_PRED_CUERPO), (ESC_PRED_CABINA, LOGICA_PRED_CABINA)):
            activos = []
            for e in cat:
                cond, vars_ = log[e["id"]]
                if cond(Pk):
                    n = max([max(P[k].lp, 1 if P[k].activo else 0) for k in vars_ if k in P] + [0])
                    activos.append((e, n))
            out = []
            for e, n in sorted(_filtrar(activos), key=lambda t: (-t[1], t[0]["id"])):
                etas = [P[k].eta_s for k in log[e["id"]][1] if k in P and P[k].eta_s is not None]
                out.append(_rec(e, n, eta_s=min(etas) if etas else None,
                                si_if_anomalo=e["si_if_anomalo"] if c.if_anomalo else None))
            sal.append(out)
        return sal[0], sal[1]


if __name__ == "__main__":  # demo con los valores de la pantalla del usuario
    ej = {"fc (lpm)": 72.78, "pa_sis (mmHg)": 114.34, "pa_dia (mmHg)": 77.86, "spo2 (%)": 97.19, "temp (°C)": 39.03,
          "glucosa (mg/dL)": 95.98, "hrv (ms)": 67.93, "co2 (ppm)": 1000, "presión (kPa)": 101, "temp_cabina (°C)": 22.4,
          "humedad (%)": 45, "ruido (dBA)": 40, "radiación (mSv/día)": 0.5}
    r = Evaluador().evaluar(ej, {"anomaly": False, "score": 0.0278})
    print(r["global"], r["if"]["clave"], [(x["id"], x["nivel_nombre"]) for x in r["cuerpo"]["correctivo"]])
