FROM python:3.12-slim

RUN pip install --no-cache-dir ldap3 requests

WORKDIR /app

COPY adapters /app/adapters
COPY platform/services/registration-orchestrator /app/platform/services/registration-orchestrator

ENTRYPOINT ["python3", "/app/platform/services/registration-orchestrator/orchestrator.py"]
