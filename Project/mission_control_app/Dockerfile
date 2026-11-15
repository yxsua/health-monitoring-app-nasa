FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY Project/mission_control_app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data \
    && chown 10001:10001 /data

COPY Project/mission_control_app/__init__.py ./Project/mission_control_app/__init__.py
COPY Project/mission_control_app/api.py ./Project/mission_control_app/api.py
COPY Project/mission_control_app/auth.py ./Project/mission_control_app/auth.py
COPY Project/mission_control_app/models.py ./Project/mission_control_app/models.py
COPY Project/mission_control_app/sender.py ./Project/mission_control_app/sender.py
COPY Project/mission_control_app/storage.py ./Project/mission_control_app/storage.py

USER 10001:10001
EXPOSE 8003
CMD ["uvicorn", "Project.mission_control_app.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8003", "--workers", "1"]
