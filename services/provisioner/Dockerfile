# ===========================================================
# Provisioner — Dockerfile
# ===========================================================
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ldap-utils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir ldap3 requests

COPY provision.py /provision.py

CMD ["python3", "-u", "/provision.py"]
