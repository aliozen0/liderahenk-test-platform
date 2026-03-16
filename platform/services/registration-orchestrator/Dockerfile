FROM python:3.12-slim

RUN pip install --no-cache-dir ldap3 pymysql pyyaml requests

WORKDIR /app
ENV PYTHONPATH=/app

COPY adapters /app/adapters
COPY platform/contracts /app/platform/contracts
COPY platform/services/registration-orchestrator /app/platform/services/registration-orchestrator
COPY platform_runtime /app/platform_runtime

ENTRYPOINT ["python3", "/app/platform/services/registration-orchestrator/orchestrator.py"]
