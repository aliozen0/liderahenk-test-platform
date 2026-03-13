#!/bin/bash
# ===========================================================
# Ahenk Agent — Entrypoint
# ===========================================================
set -e

# Thundering herd önleme — rastgele gecikme
JITTER=$(( RANDOM % ${JITTER_MAX_SECONDS:-30} ))
echo "[ahenk] Jitter bekleme: ${JITTER}sn"
sleep ${JITTER}

# AGENT_INDEX: env → hostname token → Docker label → fallback 001
if [ -z "${AGENT_INDEX}" ]; then
  CONTAINER_NUM=$(hostname | tr '-' '\n' | grep -E '^[0-9]+$' | tail -1 || true)
  if [ -z "${CONTAINER_NUM}" ] && [ -S /var/run/docker.sock ]; then
    CONTAINER_NUM=$(
      python3 - <<'PY'
import json
import os
import socket
import sys

container_id = os.environ.get("HOSTNAME", "").strip()
sock_path = "/var/run/docker.sock"
if not container_id or not os.path.exists(sock_path):
    sys.exit(0)

request = (
    f"GET /containers/{container_id}/json HTTP/1.0\r\n"
    "Host: localhost\r\n"
    "\r\n"
)

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(sock_path)
sock.sendall(request.encode())

chunks = []
while True:
    chunk = sock.recv(65536)
    if not chunk:
        break
    chunks.append(chunk)
sock.close()

response = b"".join(chunks)
if b"\r\n\r\n" not in response:
    sys.exit(0)

body = response.split(b"\r\n\r\n", 1)[1]
try:
    data = json.loads(body.decode())
except Exception:
    sys.exit(0)

labels = data.get("Config", {}).get("Labels", {})
print(labels.get("com.docker.compose.container-number", ""))
PY
    )
  fi
  if [ -n "$CONTAINER_NUM" ]; then
    AGENT_INDEX=$((10#$CONTAINER_NUM))
  else
    AGENT_INDEX="1"
  fi
fi
export AGENT_INDEX
AGENT_ID=$(printf 'ahenk-%03d' "${AGENT_INDEX}")
printf 'AGENT_INDEX=%s\nAGENT_ID=%s\n' "${AGENT_INDEX}" "${AGENT_ID}" > /etc/ahenk/agent.env
chown ahenk:ahenk /etc/ahenk/agent.env 2>/dev/null || true

# ahenk.conf dinamik oluştur
mkdir -p /etc/ahenk 2>/dev/null || true
cat > /etc/ahenk/ahenk.conf << EOF
[CONNECTION]
host=${XMPP_HOST}
port=5222
domain=${XMPP_DOMAIN}
username=${AGENT_ID}

[LDAP]
host=${LDAP_HOST}
port=${LDAP_PORT}
base_dn=${LDAP_BASE_DN}
EOF

# Log stdout'a
export AHENK_LOG_OUTPUT=stdout

echo "[${AGENT_ID}] Başlatılıyor..."

# Eğer ahenk.py mevcutsa çalıştır; değilse simüle et
if [ -f /app/ahenk.py ]; then
  exec runuser -u ahenk -m -- python3 /app/ahenk.py
else
  echo "[${AGENT_ID}] ahenk.py bulunamadı — simülasyon modunda"
  echo "[${AGENT_ID}] Config: /etc/ahenk/ahenk.conf"
  cat /etc/ahenk/ahenk.conf
  # Konteyneri canlı tut (ölçek testleri için)
  echo "[${AGENT_ID}] Bekleme modunda..."
  exec runuser -u ahenk -m -- tail -f /dev/null
fi
