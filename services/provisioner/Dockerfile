# ===========================================================
# Provisioner — Dockerfile
# ===========================================================
FROM python:3.12-slim

RUN pip install --no-cache-dir ldap3 requests

COPY provision.py /provision.py

CMD ["python3", "-u", "/provision.py"]
