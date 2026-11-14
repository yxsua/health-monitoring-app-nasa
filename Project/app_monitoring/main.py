
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from collections import deque
import threading
import queue

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from generador_datos import (
    generar_datos,
    VARIABLES,
    evaluar_variable
)

from isolation_forest import entrenar as entrenar_if
from isolation_forest import detectar

from lstm_model import entrenar as entrenar_lstm
from lstm_model import predecir

from simulador_tiempo_real import iniciar


# ==========================================
# CONFIGURACION
# ==========================================

MAX_PUNTOS = 100

COLOR_NORMAL = "#16A36A"
COLOR_PRECAUCION = "#E5A000"
COLOR_ALARMA = "#D93636"

cola_datos = queue.Queue()
detener_evento = threading.Event()


# ==========================================
# REGISTRO DEL ASTRONAUTA
# ==========================================

def solicitar_datos_astronauta():

    print("\n======================================")
    print("          ASTRAHEALTH AI")
    print("       REGISTRO DEL ASTRONAUTA")
    print("======================================")

    astronauta = {}

    astronauta["id"] = input(
        "\nIdentificador del astronauta: "
    ).strip()

    astronauta["nombre"] = input(
        "Nombre del astronauta: "
    ).strip()

    astronauta["edad"] = int(input(
        "Edad del astronauta: "
    ))

    astronauta["mision"] = input(
        "Nombre de la misión: "
    ).strip()

    if not all([
        astronauta["id"],
        astronauta["nombre"],
        astronauta["mision"]
    ]) or astronauta["edad"] <= 0:

        raise ValueError(
            "Los datos del astronauta no son válidos."
        )

    return astronauta


# ==========================================
# ENTRENAMIENTO
# ==========================================

def preparar_modelos(astronauta):

    print("\nGENERANDO DATOS DEL ASTRONAUTA...")

    generar_datos(
        n=10000,
        astronauta=astronauta
    )

    print("\nENTRENANDO ISOLATION FOREST...")

    entrenar_if()

    print("\nENTRENANDO LSTM...")

    entrenar_lstm()

    print("\nTODOS LOS MODELOS FUERON ENTRENADOS.")


# ==========================================
# EVALUACION GENERAL
# ==========================================

def obtener_estado_general(estados):

    if "ALARMA" in estados.values():
        return "ALARMA"

    if "PRECAUCION" in estados.values():
        return "PRECAUCION"

    return "NORMAL"


# ==========================================
# PROCESAMIENTO EN SEGUNDO PLANO
# ==========================================

def procesar_datos(astronauta):

    historial = []

    try:

        for medicion in iniciar(astronauta):

            if detener_evento.is_set():
                break

            # Deteccion global
            resultado_if = detectar(medicion)

            # Guardar historial
            historial.append([
                float(medicion[v])
                for v in VARIABLES
            ])

            # Evaluacion individual
            estados = {}

            for variable in VARIABLES:

                estados[variable] = evaluar_variable(
                    variable,
                    float(medicion[variable])
                )

            # Prediccion LSTM
            predicciones = None

            if len(historial) >= 24:

                secuencia = historial[-24:]

                resultado_lstm = predecir(secuencia)

                predicciones = np.asarray(
                    resultado_lstm,
                    dtype=float
                ).flatten().tolist()

            estado_general = obtener_estado_general(
                estados
            )

            # Enviar datos a la interfaz
            cola_datos.put({
                "medicion": medicion,
                "estados": estados,
                "estado_general": estado_general,
                "resultado_if": resultado_if,
                "predicciones": predicciones
            })

    except Exception as error:

        cola_datos.put({
            "error": str(error)
        })


# ==========================================
# INTERFAZ GRAFICA
# ==========================================

class AstraHealth:

    def __init__(self, root, astronauta):

        self.root = root
        self.astronauta = astronauta

        self.root.title("ASTRAHEALTH AI - Monitoreo")
        self.root.geometry("1450x950")
        self.root.configure(bg="#101820")

        self.tiempo = 0

        self.historial_graficas = {
            variable: deque(maxlen=MAX_PUNTOS)
            for variable in VARIABLES
        }

        self.lineas = {}
        self.puntos_prediccion = {}

        self.crear_interfaz()

        # Iniciar procesamiento en otro hilo
        self.hilo = threading.Thread(
            target=procesar_datos,
            args=(astronauta,),
            daemon=True
        )

        self.hilo.start()

        self.root.after(100, self.actualizar_interfaz)

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.cerrar
        )

    # ======================================
    # CREAR INTERFAZ
    # ======================================

    def crear_interfaz(self):

        # ENCABEZADO
        encabezado = tk.Frame(
            self.root,
            bg="#172733",
            height=100
        )

        encabezado.pack(fill="x")

        tk.Label(
            encabezado,
            text="ASTRAHEALTH AI",
            font=("Arial", 25, "bold"),
            fg="white",
            bg="#172733"
        ).pack(anchor="w", padx=20, pady=(12, 0))

        tk.Label(
            encabezado,
            text=(
                f"Astronauta: {self.astronauta['nombre']}   |   "
                f"ID: {self.astronauta['id']}   |   "
                f"Misión: {self.astronauta['mision']}"
            ),
            font=("Arial", 11),
            fg="#B9CAD6",
            bg="#172733"
        ).pack(anchor="w", padx=22, pady=5)

        # PANEL DE ESTADO
        panel = tk.Frame(
            self.root,
            bg="#101820"
        )

        panel.pack(fill="x", padx=15, pady=12)

        self.lbl_estado = tk.Label(
            panel,
            text="ESTADO: ESPERANDO DATOS",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#52616B",
            padx=20,
            pady=12
        )

        self.lbl_estado.pack(
            side="left",
            padx=5
        )

        self.lbl_if = tk.Label(
            panel,
            text="Isolation Forest: Esperando",
            font=("Arial", 11),
            fg="white",
            bg="#101820"
        )

        self.lbl_if.pack(
            side="left",
            padx=20
        )

        self.lbl_contador = tk.Label(
            panel,
            text="Mediciones: 0",
            font=("Arial", 11),
            fg="white",
            bg="#101820"
        )

        self.lbl_contador.pack(
            side="right",
            padx=15
        )

        # PANEL DE GRAFICAS
        contenedor = tk.Frame(
            self.root,
            bg="#101820"
        )

        contenedor.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5
        )

        # FIGURA MATPLOTLIB
        self.figura = Figure(
            figsize=(15, 12),
            dpi=90
        )

        self.figura.suptitle(
            "MONITOREO DE VARIABLES FISIOLOGICAS",
            fontsize=16
        )

        self.axes = self.figura.subplots(
            6,
            3
        )

        self.axes = self.axes.flatten()

        for i, variable in enumerate(VARIABLES):

            ax = self.axes[i]

            ax.set_title(
                variable,
                fontsize=9,
                fontweight="bold"
            )

            ax.set_xlabel("Tiempo")
            ax.set_ylabel("Valor")

            ax.grid(True, alpha=0.3)

            linea, = ax.plot(
                [],
                [],
                linewidth=1.8,
                color=COLOR_NORMAL,
                label="Medicion"
            )

            prediccion = ax.scatter(
                [],
                [],
                color="#356AC3",
                marker="x",
                s=50,
                label="Prediccion LSTM"
            )

            self.lineas[variable] = linea

            self.puntos_prediccion[variable] = prediccion

        # Ocultar graficas sobrantes
        for i in range(len(VARIABLES), len(self.axes)):
            self.axes[i].set_visible(False)

        self.figura.tight_layout(
            rect=[0, 0, 1, 0.97]
        )

        self.canvas = FigureCanvasTkAgg(
            self.figura,
            master=contenedor
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True
        )

        # PIE DE INTERFAZ
        pie = tk.Frame(
            self.root,
            bg="#172733"
        )

        pie.pack(fill="x")

        tk.Label(
            pie,
            text=(
                "VERDE: NORMAL     "
                "AMARILLO: PRECAUCION     "
                "ROJO: ALARMA     "
                "AZUL: PREDICCION LSTM"
            ),
            font=("Arial", 10, "bold"),
            fg="white",
            bg="#172733",
            pady=10
        ).pack()

    # ======================================
    # ACTUALIZAR GRAFICAS
    # ======================================

    def actualizar_graficas(
        self,
        medicion,
        estados,
        predicciones
    ):

        for i, variable in enumerate(VARIABLES):

            valor = float(medicion[variable])

            self.historial_graficas[variable].append(
                valor
            )

            datos = list(
                self.historial_graficas[variable]
            )

            tiempos = list(
                range(
                    self.tiempo - len(datos) + 1,
                    self.tiempo + 1
                )
            )

            ax = self.axes[i]

            linea = self.lineas[variable]

            linea.set_data(
                tiempos,
                datos
            )

            estado = estados[variable]

            if estado == "ALARMA":

                linea.set_color(COLOR_ALARMA)

            elif estado == "PRECAUCION":

                linea.set_color(COLOR_PRECAUCION)

            else:

                linea.set_color(COLOR_NORMAL)

            ax.set_title(
                f"{variable} | {estado} | {valor:.2f}",
                fontsize=9,
                color=(
                    COLOR_ALARMA
                    if estado == "ALARMA"
                    else COLOR_PRECAUCION
                    if estado == "PRECAUCION"
                    else COLOR_NORMAL
                )
            )

            # Mostrar prediccion LSTM
            punto = self.puntos_prediccion[variable]

            if (
                predicciones is not None
                and len(predicciones) == len(VARIABLES)
            ):

                predicho = float(
                    predicciones[i]
                )

                punto.set_offsets([
                    [self.tiempo + 1, predicho]
                ])

            else:

                punto.set_offsets(
                    np.empty((0, 2))
                )

            ax.set_xlim(
                max(0, self.tiempo - MAX_PUNTOS),
                max(MAX_PUNTOS, self.tiempo + 2)
            )

            ax.relim()
            ax.autoscale_view(scalex=False)

        self.canvas.draw_idle()

    # ======================================
    # ACTUALIZAR INFORMACION
    # ======================================

    def actualizar_interfaz(self):

        try:

            while True:

                datos = cola_datos.get_nowait()

                if "error" in datos:

                    messagebox.showerror(
                        "Error de monitoreo",
                        datos["error"]
                    )

                    self.cerrar()
                    return

                self.tiempo += 1

                medicion = datos["medicion"]

                estados = datos["estados"]

                estado_general = datos[
                    "estado_general"
                ]

                resultado_if = datos[
                    "resultado_if"
                ]

                predicciones = datos[
                    "predicciones"
                ]

                # Estado general
                colores = {
                    "NORMAL": COLOR_NORMAL,
                    "PRECAUCION": COLOR_PRECAUCION,
                    "ALARMA": COLOR_ALARMA
                }

                self.lbl_estado.config(
                    text=f"ESTADO: {estado_general}",
                    bg=colores[estado_general]
                )

                # Isolation Forest
                self.lbl_if.config(
                    text=(
                        "Isolation Forest: "
                        f"{resultado_if['resultado']} | "
                        f"Puntuacion: "
                        f"{resultado_if['puntuacion']:.4f}"
                    )
                )

                self.lbl_contador.config(
                    text=f"Mediciones: {self.tiempo}"
                )

                # Actualizar las 17 graficas
                self.actualizar_graficas(
                    medicion,
                    estados,
                    predicciones
                )

        except queue.Empty:
            pass

        self.root.after(
            100,
            self.actualizar_interfaz
        )

    # ======================================
    # CERRAR INTERFAZ
    # ======================================

    def cerrar(self):

        detener_evento.set()

        self.root.destroy()


# ==========================================
# EJECUCION PRINCIPAL
# ==========================================

if __name__ == "__main__":

    try:

        astronauta = solicitar_datos_astronauta()

        preparar_modelos(astronauta)

        detener_evento.clear()

        root = tk.Tk()

        app = AstraHealth(
            root,
            astronauta
        )

        root.mainloop()

    except KeyboardInterrupt:

        detener_evento.set()

        print("\nASTRAHEALTH AI detenido.")

    except Exception as error:

        detener_evento.set()

        print("\nERROR EN ASTRAHEALTH AI:")
        print(error)
