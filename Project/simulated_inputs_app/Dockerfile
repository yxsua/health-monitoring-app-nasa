FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY Project/simulated_inputs_app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY Project/simulated_inputs_app/api.py ./Project/simulated_inputs_app/api.py
COPY Project/simulated_inputs_app/simulador_tiempo_real.py ./Project/simulated_inputs_app/simulador_tiempo_real.py
COPY Docs/Challenge/simulated-astronaut-inputs.schema.json ./Docs/Challenge/simulated-astronaut-inputs.schema.json
COPY Docs/Challenge/simulated-astronaut-inputs.openapi.json ./Docs/Challenge/simulated-astronaut-inputs.openapi.json

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "Project.simulated_inputs_app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
