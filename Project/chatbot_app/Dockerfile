FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY Project/chatbot_app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown 10001:10001 /data

COPY Project/chatbot_app/__init__.py ./Project/chatbot_app/__init__.py
COPY Project/chatbot_app/api.py ./Project/chatbot_app/api.py
COPY Project/chatbot_app/assessments.py ./Project/chatbot_app/assessments.py
COPY Project/chatbot_app/auth.py ./Project/chatbot_app/auth.py
COPY Project/chatbot_app/models.py ./Project/chatbot_app/models.py
COPY Project/chatbot_app/checkin_policy.py ./Project/chatbot_app/checkin_policy.py
COPY Project/chatbot_app/model_adapter.py ./Project/chatbot_app/model_adapter.py
COPY Project/chatbot_app/benchmark_local_model.py ./Project/chatbot_app/benchmark_local_model.py
COPY Project/chatbot_app/storage.py ./Project/chatbot_app/storage.py
COPY Project/recommendations_app/__init__.py ./Project/recommendations_app/__init__.py
COPY Project/recommendations_app/engine.py ./Project/recommendations_app/engine.py

USER 10001:10001
EXPOSE 8002
CMD ["uvicorn", "Project.chatbot_app.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
