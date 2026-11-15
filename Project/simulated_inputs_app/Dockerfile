FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SIMULATION_HISTORY_DB=/data/analysis.sqlite3

WORKDIR /app
ARG INSTALL_ML_RUNTIME=true
COPY Project/simulated_inputs_app/requirements.txt /tmp/requirements.txt
COPY Project/simulated_inputs_app/requirements-ml.txt /tmp/requirements-ml.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && if [ "$INSTALL_ML_RUNTIME" = "true" ]; then pip install --no-cache-dir -r /tmp/requirements-ml.txt; fi \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown 10001:10001 /data

COPY Project/simulated_inputs_app/api.py ./Project/simulated_inputs_app/api.py
COPY Project/simulated_inputs_app/analysis_engine.py ./Project/simulated_inputs_app/analysis_engine.py
COPY Project/simulated_inputs_app/model_config.py ./Project/simulated_inputs_app/model_config.py
COPY Project/simulated_inputs_app/alert_engine.py ./Project/simulated_inputs_app/alert_engine.py
COPY Project/simulated_inputs_app/simulador_tiempo_real.py ./Project/simulated_inputs_app/simulador_tiempo_real.py
COPY Project/simulated_inputs_app/analysis-response.schema.json ./Project/simulated_inputs_app/analysis-response.schema.json
COPY Docs/Challenge/simulated-astronaut-inputs.schema.json ./Docs/Challenge/simulated-astronaut-inputs.schema.json
COPY Docs/Challenge/simulated-astronaut-inputs.openapi.json ./Docs/Challenge/simulated-astronaut-inputs.openapi.json

USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "Project.simulated_inputs_app.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
