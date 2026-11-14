# Software de monitorización de la salud para astronautas

**Hackathon NASA 2026**

---

## El problema real

En una misión larga (Luna, Marte) no hay hospital ni respuesta en tiempo real: la comunicación con la Tierra puede tardar hasta ~20 minutos en cada sentido en Marte. El software tiene que ser **autónomo**: detectar, interpretar y recomendar sin depender del control de misión.

---

## Qué debería monitorear

- **Cardiovascular:** frecuencia cardiaca, variabilidad (HRV), presión arterial, SpO₂. En microgravedad los fluidos se desplazan hacia la cabeza y el corazón se adapta.
- **Musculoesquelético:** pérdida de masa ósea y muscular, carga de ejercicio diario.
- **Sueño y ritmo circadiano:** clave para el rendimiento y los errores operativos.
- **Estrés y salud mental:** HRV, patrones de actividad, aislamiento y confinamiento.
- **Entorno:** radiación acumulada, CO₂, temperatura, presión de la cabina.
- **Visión:** el síndrome neuro-ocular asociado al vuelo espacial (SANS) es un riesgo conocido.

---

## Arquitectura de software sugerida

1. **Captura de datos:** wearables y sensores no invasivos (en el hackathon se pueden simular los datos).
2. **Procesamiento local (edge):** corre a bordo, sin internet.
3. **Línea base individual:** cada astronauta se compara contra *sí mismo*, no contra un promedio.
4. **Detección de anomalías:** reglas clínicas más un modelo simple de ML (por ejemplo, Isolation Forest o detección de desviaciones).
5. **Alertas por niveles:** informativa, precaución y crítica, con una acción recomendada.
6. **Dashboard:** uno para el astronauta (simple y claro) y otro para el médico en Tierra (tendencias y detalle).
7. **Sincronización diferida:** envío de datos comprimidos cuando haya enlace.

---

## Qué hace ganador a un proyecto

- Un **MVP funcional** con datos simulados y un dashboard claro.
- Que sea **predictivo**, no solo reactivo (por ejemplo, avisar que el riesgo sube en 48 h).
- Que contemple la **privacidad** de los datos médicos y la **tolerancia a fallas**.
- Un buen **pitch**: problema, solución, demo y por qué importa para Marte.

---

## Pendiente por definir

- Etapa actual del proyecto.
- Tecnología a usar (Python, web, app móvil, Arduino/sensores).
