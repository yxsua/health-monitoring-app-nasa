import pandas as pd
import numpy as np
import sqlite3
from collections import deque

EXCEL = "modelo_DatosAstronautas.xlsx"
DB = "astronautas.db"

VARIABLES = [
    "fc (lpm)", "pa_sis (mmHg)", "pa_dia (mmHg)",
    "spo2 (%)", "temp (°C)", "glucosa (mg/dL)",
    "hrv (ms)", "sueño (h)", "ánimo (1-5)",
    "ejercicio (min)", "radiación (mSv/día)",
    "co2 (ppm)", "temp_cabina (°C)",
    "humedad (%)", "ruido (dBA)",
    "presión (kPa)", "gravedad (g)"
]

# Formato:
# (alarma_baja, precaucion_baja,
#  normal_min, normal_max,
#  precaucion_alta, alarma_alta)

UMBRALES = {
    "fc (lpm)": (50, 60, 60, 100, 120, 140),
    "pa_sis (mmHg)": (80, 90, 90, 130, 160, 180),
    "pa_dia (mmHg)": (40, 60, 60, 85, 100, 120),
    "spo2 (%)": (80, 90, 95, 100, None, None),
    "temp (°C)": (34, 35, 36, 38, 39, 40),
    "glucosa (mg/dL)": (54, 70, 70, 140, 250, 300),
    "hrv (ms)": (15, 25, 25, 120, 150, 180),
    "sueño (h)": (2, 4, 6, 9, 12, 14),
    "ánimo (1-5)": (None, 2, 3, 5, None, None),
    "ejercicio (min)": (None, 5, 10, 120, 180, 240),
    "radiación (mSv/día)": (None, None, 0, 0.8, 1.5, 3),
    "co2 (ppm)": (None, None, 400, 2000, 3000, 5000),
    "temp_cabina (°C)": (10, 15, 18, 26, 30, 35),
    "humedad (%)": (10, 20, 30, 60, 70, 85),
    "ruido (dBA)": (None, None, 0, 70, 85, 100),
    "presión (kPa)": (80, 90, 95, 105, 110, 120),
    "gravedad (g)": (0, 0.02, 0.05, 0.15, 0.20, 0.30)
}

# (media, desviación) alrededor de la cual oscila cada variable en estado normal.
BASE = {
    "fc (lpm)": (70, 8),
    "pa_sis (mmHg)": (115, 7),
    "pa_dia (mmHg)": (75, 5),
    "spo2 (%)": (98, 0.5),
    "temp (°C)": (36.7, 0.15),
    "glucosa (mg/dL)": (95, 7),
    "hrv (ms)": (65, 8),
    "sueño (h)": (7, 0.5),
    "ánimo (1-5)": (4, 0.3),
    "ejercicio (min)": (30, 5),
    "radiación (mSv/día)": (0.5, 0.1),
    "co2 (ppm)": (1000, 100),
    "temp_cabina (°C)": (22, 0.5),
    "humedad (%)": (45, 3),
    "ruido (dBA)": (40, 3),
    "presión (kPa)": (101, 0.5),
    "gravedad (g)": (0.1, 0.005)
}

# ---------------------------------------------------------------------------
# Continuidad temporal
# ---------------------------------------------------------------------------

INTERVALO_S = 5        # segundos entre mediciones
VENTANA_S = 300        # ventana de control: 5 minutos
VENTANA_PASOS = VENTANA_S // INTERVALO_S

# Variación MÁXIMA permitida dentro de cualquier ventana de 5 minutos.
# Ejemplo: temp_cabina = 2 -> en 5 minutos nunca se mueve más de 2 °C
# (si está en 23, no puede pasar a 17: se queda dentro de ese margen).
# Ajusta estos valores a tu gusto.
TOLERANCIA_5MIN = {
    "fc (lpm)": 5,
    "pa_sis (mmHg)": 5,
    "pa_dia (mmHg)": 4,
    "spo2 (%)": 1,
    "temp (°C)": 0.2,
    "glucosa (mg/dL)": 5,
    "hrv (ms)": 5,
    "sueño (h)": 0.3,
    "ánimo (1-5)": 0.3,
    "ejercicio (min)": 5,
    "radiación (mSv/día)": 0.05,
    "co2 (ppm)": 100,
    "temp_cabina (°C)": 2,
    "humedad (%)": 3,
    "ruido (dBA)": 3,
    "presión (kPa)": 0.5,
    "gravedad (g)": 0.005
}

# Límites físicos absolutos (nunca se sale de aquí, aunque sea una alarma).
LIMITES_FISICOS = {
    "fc (lpm)": (20, 220),
    "pa_sis (mmHg)": (50, 260),
    "pa_dia (mmHg)": (30, 160),
    "spo2 (%)": (50, 100),
    "temp (°C)": (30, 43),
    "glucosa (mg/dL)": (20, 600),
    "hrv (ms)": (1, 300),
    "sueño (h)": (0, 24),
    "ánimo (1-5)": (1, 5),
    "ejercicio (min)": (0, 480),
    "radiación (mSv/día)": (0, 10),
    "co2 (ppm)": (300, 10000),
    "temp_cabina (°C)": (0, 50),
    "humedad (%)": (0, 100),
    "ruido (dBA)": (0, 140),
    "presión (kPa)": (50, 150),
    "gravedad (g)": (0, 1)
}

# Tiempo en el que la variable "pasea" lentamente alrededor de su base.
# Más grande = curvas más suaves y lentas.
TAU_LENTO_S = 1800

# Ruido de cada medición, como fracción de la tolerancia (muy pequeño = curvas suaves).
FACTOR_RUIDO = 0.03

# Tiempo que tarda una variable en llegar a precaución/alarma cuando tú la
# provocas (y en regresar a su base). Es una rampa suave, sin saltos.
# Para que tarde 5 minutos pon 300.
DURACION_RAMPA_S = 120
RAMPA_PASOS = max(1, DURACION_RAMPA_S // INTERVALO_S)

# Qué tanto sigue "paseando" la variable mientras está en alerta (0 a 1).
FACTOR_ALERTA = 0.4

PHI_LENTO = float(np.exp(-INTERVALO_S / TAU_LENTO_S))
INNOVACION_LENTA = float(np.sqrt(1 - PHI_LENTO ** 2))

# Cuánto se aleja la variable de su base en el paseo lento.
SIGMA_LENTA = {
    v: min(BASE[v][1], 0.3 * TOLERANCIA_5MIN[v])
    for v in VARIABLES
}

SIGMA_RUIDO = {
    v: FACTOR_RUIDO * TOLERANCIA_5MIN[v]
    for v in VARIABLES
}


def evaluar_variable(variable, valor):

    al, pl, nmin, nmax, ph, ah = UMBRALES[variable]

    # Alarmas
    if al is not None and valor < al:
        return "ALARMA"

    if ah is not None and valor >= ah:
        return "ALARMA"

    # Precauciones
    if pl is not None and valor < pl:
        return "PRECAUCION"

    if ph is not None and valor > ph:
        return "PRECAUCION"

    if nmin is not None and valor < nmin:
        return "PRECAUCION"

    if nmax is not None and valor > nmax:
        return "PRECAUCION"

    return "NORMAL"


def objetivo_alerta(variable, nivel, rng):
    """
    Valor hacia el que debe derivar la variable para entrar en una zona de
    PRECAUCION o ALARMA (el centro de esa zona). Devuelve None si la variable
    no tiene esa zona definida.
    """

    al, pl, nmin, nmax, ph, ah = UMBRALES[variable]
    minimo, maximo = LIMITES_FISICOS[variable]

    opciones = []

    if nivel == "PRECAUCION":

        # Zona de precaución baja: entre la alarma baja y el mínimo normal.
        if pl is not None and nmin is not None:
            inicio = al if al is not None else minimo
            opciones.append((inicio + nmin) / 2)

        # Zona de precaución alta: entre el máximo normal y la alarma alta.
        if ph is not None and nmax is not None:
            fin = ah if ah is not None else maximo
            opciones.append((nmax + fin) / 2)

    elif nivel == "ALARMA":

        if al is not None and pl is not None:
            opciones.append(al - (pl - al) / 2)

        if ah is not None and ph is not None:
            opciones.append(ah + (ah - ph) / 2)

    # Solo objetivos físicamente posibles.
    opciones = [o for o in opciones if minimo <= o <= maximo]

    if not opciones:
        return None

    return float(rng.choice(opciones))


class SimuladorFisiologico:
    """
    Genera mediciones consecutivas, suaves y coherentes.

    - En estado normal, cada variable "pasea" muy lentamente alrededor de su
      valor base y, dentro de cualquier ventana de 5 minutos, nunca varía
      más de TOLERANCIA_5MIN[variable].
    - Al activar una alerta, la variable avanza en una rampa suave (sin
      saltos ni zigzag) hacia la zona de precaución o alarma, y al quitarla
      regresa igual de suave a su base.
    """

    def __init__(self, semilla=None):

        self.rng = np.random.default_rng(semilla)

        # Componente lenta: pequeña desviación respecto a la base.
        self.lento = {
            v: float(self.rng.normal(0, SIGMA_LENTA[v]))
            for v in VARIABLES
        }

        # Valor "limpio" (sin ruido) de cada variable.
        self.centros = {
            v: float(BASE[v][0] + self.lento[v])
            for v in VARIABLES
        }

        self.valores = dict(self.centros)

        # Últimas mediciones (5 min) de cada variable, para controlar la tolerancia.
        self.ventanas = {
            v: deque(maxlen=VENTANA_PASOS)
            for v in VARIABLES
        }

        # variable -> valor objetivo mientras tiene una alerta activa.
        self.objetivos = {}

        # variable -> avance máximo por medición de la rampa en curso.
        self.velocidad = {}

    def activar_alerta(self, variable, nivel):
        """Devuelve False si la variable no tiene esa zona definida."""

        objetivo = objetivo_alerta(variable, nivel, self.rng)

        if objetivo is None:
            return False

        self.objetivos[variable] = objetivo

        distancia = abs(objetivo - self.centros[variable])

        self.velocidad[variable] = max(
            distancia / RAMPA_PASOS,
            0.02 * TOLERANCIA_5MIN[variable]
        )

        return True

    def desactivar_alerta(self, variable=None):
        """Quita la alerta de una variable (o de todas). Regresa suave a su base."""

        if variable is None:
            variables = list(self.objetivos)
        elif variable in self.objetivos:
            variables = [variable]
        else:
            variables = []

        for v in variables:

            del self.objetivos[v]

            base = BASE[v][0] + self.lento[v]

            self.velocidad[v] = max(
                abs(base - self.centros[v]) / RAMPA_PASOS,
                0.02 * TOLERANCIA_5MIN[v]
            )

    def siguiente(self):
        """Avanza una medición y devuelve {variable: valor}."""

        for variable in VARIABLES:

            # 1. Paseo lento alrededor de la base.
            self.lento[variable] = (
                PHI_LENTO * self.lento[variable]
                + INNOVACION_LENTA * SIGMA_LENTA[variable]
                * self.rng.normal()
            )

            en_alerta = variable in self.objetivos

            if en_alerta:
                meta = (
                    self.objetivos[variable]
                    + FACTOR_ALERTA * self.lento[variable]
                )
            else:
                meta = BASE[variable][0] + self.lento[variable]

            # 2. Valor limpio: rampa suave si hay transición, o seguimiento lento.
            if variable in self.velocidad:

                dif = meta - self.centros[variable]
                paso = self.velocidad[variable]

                if abs(dif) <= paso:
                    self.centros[variable] = meta
                    del self.velocidad[variable]
                else:
                    self.centros[variable] += float(np.sign(dif)) * paso

            else:
                self.centros[variable] = meta

            en_normal = (not en_alerta) and (variable not in self.velocidad)

            # 3. Ruido muy pequeño de medición.
            valor = self.centros[variable] + self.rng.normal(
                0, SIGMA_RUIDO[variable]
            )

            ventana = self.ventanas[variable]

            if en_normal:

                # Tolerancia: en cualquier ventana de 5 min, máximo
                # TOLERANCIA_5MIN entre el valor más alto y el más bajo.
                if ventana:

                    tolerancia = TOLERANCIA_5MIN[variable]

                    bajo = max(ventana) - tolerancia
                    alto = min(ventana) + tolerancia

                    if bajo <= alto:
                        valor = float(np.clip(valor, bajo, alto))

                # Quedarse dentro del rango normal.
                _, _, nmin, nmax, _, _ = UMBRALES[variable]

                bajo_n = nmin if nmin is not None else -np.inf
                alto_n = nmax if nmax is not None else np.inf

                if bajo_n <= self.valores[variable] <= alto_n:
                    valor = float(np.clip(valor, bajo_n, alto_n))

            minimo, maximo = LIMITES_FISICOS[variable]
            valor = float(np.clip(valor, minimo, maximo))

            if en_normal:
                ventana.append(valor)
            else:
                # Durante una alerta o una rampa la ventana no aplica.
                ventana.clear()

            self.valores[variable] = valor

        return dict(self.valores)


# Probabilidad, por medición y por variable, de que empiece un episodio de
# precaución/alarma en los datos de entrenamiento.
PROB_EPISODIO = 0.0001
DURACION_EPISODIO = (60, 240)      # en mediciones
PROB_ALARMA = 0.25                 # el resto de los episodios son PRECAUCION


def generar_datos(n=10000, astronauta=None, semilla=42):

    rng = np.random.default_rng(semilla + 1)
    simulador = SimuladorFisiologico(semilla)

    if astronauta is None:
        astronauta = {
            "id": "AST-001",
            "nombre": "Astronauta",
            "edad": 30,
            "mision": "MISION-01"
        }

    registros = []

    # variable -> mediciones que le quedan al episodio en curso.
    episodios = {}

    for i in range(n):

        # Inicio y fin de episodios de alerta.
        for variable in VARIABLES:

            if variable in episodios:

                episodios[variable] -= 1

                if episodios[variable] <= 0:
                    simulador.desactivar_alerta(variable)
                    del episodios[variable]

            elif rng.random() < PROB_EPISODIO:

                nivel = (
                    "ALARMA" if rng.random() < PROB_ALARMA
                    else "PRECAUCION"
                )

                if simulador.activar_alerta(variable, nivel):
                    episodios[variable] = int(rng.integers(
                        DURACION_EPISODIO[0],
                        DURACION_EPISODIO[1] + 1
                    ))

        valores = simulador.siguiente()

        registro = {
            "astronauta_id": astronauta["id"],
            "nombre": astronauta["nombre"],
            "edad": astronauta["edad"],
            "misión": astronauta["mision"],
            "timestamp": pd.Timestamp("2026-01-01")
                         + pd.Timedelta(seconds=INTERVALO_S * i)
        }

        estados = []

        for indice, variable in enumerate(VARIABLES):

            valor = valores[variable]

            # El estado se calcula con el valor real generado.
            estado = evaluar_variable(variable, valor)

            registro[variable] = valor
            registro[f"estado_{indice}"] = estado

            estados.append(estado)

        # Estado general: el de mayor severidad.
        if "ALARMA" in estados:
            registro["escenario"] = "critico"
        elif "PRECAUCION" in estados:
            registro["escenario"] = "precaucion"
        else:
            registro["escenario"] = "normal"

        registros.append(registro)

    df = pd.DataFrame(registros)

    df.to_csv("datos_entrenamiento.csv", index=False)

    with sqlite3.connect(DB) as conexion:

        df.to_sql(
            "registros",
            conexion,
            if_exists="replace",
            index=False
        )

    print(f"\nSe generaron {len(df)} registros.")
    print(f"Astronauta: {astronauta['nombre']}")
    print(f"Identificador: {astronauta['id']}")

    return df


if __name__ == "__main__":
    generar_datos()
