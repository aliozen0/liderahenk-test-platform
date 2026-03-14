#!/bin/bash
# ===========================================================
# Ahenk Agent — Entrypoint
# ===========================================================
set -euo pipefail

JITTER=$(( RANDOM % ${JITTER_MAX_SECONDS:-30} ))
echo "[ahenk] Jitter bekleme: ${JITTER}sn"
sleep "${JITTER}"

if [ -z "${AGENT_INDEX:-}" ]; then
  if [ -S /var/run/docker.sock ]; then
    RANKED_INDEX=$(
      python3 - <<'PY'
import json
import os
import socket
import sys
import urllib.parse

container_id = os.environ.get("HOSTNAME", "").strip()
sock_path = "/var/run/docker.sock"
if not container_id or not os.path.exists(sock_path):
    sys.exit(0)

project = os.environ.get("COMPOSE_PROJECT_NAME", "liderahenk-test")
filters = {
    "label": [
        f"com.docker.compose.project={project}",
        "com.docker.compose.service=ahenk",
        "com.docker.compose.oneoff=False",
    ]
}
query = urllib.parse.quote(json.dumps(filters))
request = (
    f"GET /containers/json?all=1&filters={query} HTTP/1.0\r\n"
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
    containers = json.loads(body.decode())
except Exception:
    sys.exit(0)

def container_number(item):
    labels = item.get("Labels", {}) or {}
    raw = labels.get("com.docker.compose.container-number", "0")
    try:
        return int(raw)
    except Exception:
        return 0

containers = sorted(containers, key=container_number)
for idx, item in enumerate(containers, start=1):
    item_id = (item.get("Id") or "").strip()
    if item_id.startswith(container_id):
        print(idx)
        break
PY
    )
    if [ -n "${RANKED_INDEX}" ]; then
      AGENT_INDEX="${RANKED_INDEX}"
    fi
  fi
  if [ -z "${AGENT_INDEX:-}" ]; then
    CONTAINER_NUM=$(hostname | tr '-' '\n' | grep -E '^[0-9]+$' | tail -1 || true)
    if [ -n "${CONTAINER_NUM}" ]; then
      AGENT_INDEX=$((10#$CONTAINER_NUM))
    else
      AGENT_INDEX="1"
    fi
  fi
fi

AGENT_ID=$(printf 'ahenk-%03d' "${AGENT_INDEX}")
AGENT_HOSTNAME="${AGENT_ID}-host"
AGENT_XMPP_PASS="${XMPP_AGENT_PASS:-${XMPP_ADMIN_PASS:-}}"
AHENK_VERSION="${AHENK_VERSION:-2.0.1}"
CONTAINER_MODE="${CONTAINER_MODE:-1}"
DEBUG_MODE="${DEBUG_MODE:-0}"
AHENK_RUN_AS_ROOT="${AHENK_RUN_AS_ROOT:-1}"
NETWORK_PORT_RULE_MODE="${NETWORK_PORT_RULE_MODE:-shadow}"

if [ -z "${AGENT_XMPP_PASS}" ]; then
  echo "[${AGENT_ID}] HATA: XMPP agent parolası boş"
  exit 1
fi

export AGENT_INDEX
export AGENT_ID
export AGENT_HOSTNAME
export AGENT_XMPP_PASS
export AHENK_VERSION
export CONTAINER_MODE
export DEBUG_MODE
export AHENK_RUN_AS_ROOT
export NETWORK_PORT_RULE_MODE
export PYTHONUNBUFFERED=1
export PYTHONPATH="/opt/ahenk-patches:/app/ahenk/src${PYTHONPATH:+:${PYTHONPATH}}"

mkdir -p /etc/ahenk/config.d /etc/network /var/db /app/allowed-plugins

cat > /etc/ahenk/agent.env <<EOF
AGENT_INDEX=${AGENT_INDEX}
AGENT_ID=${AGENT_ID}
AGENT_HOSTNAME=${AGENT_HOSTNAME}
AGENT_XMPP_PASS=${AGENT_XMPP_PASS}
CONTAINER_MODE=${CONTAINER_MODE}
DEBUG_MODE=${DEBUG_MODE}
AHENK_RUN_AS_ROOT=${AHENK_RUN_AS_ROOT}
EOF

cat > /etc/network/interfaces <<'EOF'
auto lo
iface lo inet loopback
EOF

printf '%s\n' "${AGENT_HOSTNAME}" > /etc/hostname

if [ ! -f /var/db/network-policy.json ]; then
  cat > /var/db/network-policy.json <<'EOF'
{"blocked":{"input":[],"output":[]}}
EOF
fi

cat > /etc/ahenk/log.conf <<'EOF'
[formatters]
keys=default

[formatter_default]
format=%(asctime)s %(name)-12s %(levelname)-8s %(message)s
class=logging.Formatter

[handlers]
keys=console

[handler_console]
class=StreamHandler
level=DEBUG
formatter=default
args=(sys.stdout,)

[loggers]
keys=root

[logger_root]
level=DEBUG
handlers=console
EOF

cat > /etc/ahenk/ahenk.conf <<EOF
[BASE]
logconfigurationfilepath = /etc/ahenk/log.conf
dbpath = /var/db/ahenk.db

[PLUGIN]
pluginfolderpath = /app/allowed-plugins/
mainmodulename = main

[CONNECTION]
uid =
password =
host = ${XMPP_HOST:-ejabberd}
port = 5222
use_tls = false
receiverjid = lider_sunucu
receiverresource = ${XMPP_RESOURCE:-LiderAPI}
servicename = ${XMPP_DOMAIN:-liderahenk.org}
receivefileparam = /tmp/

[SESSION]
agreement_timeout = 30
registration_timeout = 30
get_policy_timeout = 30

[MACHINE]
type = default
agreement = 0
user_disabled = false
EOF

rm -rf /app/allowed-plugins/*
mkdir -p \
  /app/allowed-plugins/script \
  /app/allowed-plugins/file-management \
  /app/allowed-plugins/resource-usage \
  /app/allowed-plugins/package-manager \
  /app/allowed-plugins/local-user \
  /app/allowed-plugins/network-manager

cp -a /app/ahenk/src/plugins/script/. /app/allowed-plugins/script/
cp -a /app/ahenk/src/plugins/file-management/. /app/allowed-plugins/file-management/
cp -a /app/ahenk/src/plugins/resource-usage/. /app/allowed-plugins/resource-usage/
cp -a /app/ahenk/src/plugins/package-manager/. /app/allowed-plugins/package-manager/
cp -a /app/ahenk/src/plugins/local-user/. /app/allowed-plugins/local-user/
cp -a /app/ahenk/src/plugins/network-manager/. /app/allowed-plugins/network-manager/

chown -R ahenk:ahenk /etc/ahenk /var/db /app/allowed-plugins /app /opt/ahenk-patches

echo "[${AGENT_ID}] Başlatılıyor"
echo "[${AGENT_ID}] Hostname kontratı: ${AGENT_HOSTNAME}"
echo "[${AGENT_ID}] Plugin allowlist hazırlandı"

run_agent() {
  if [ "${AHENK_RUN_AS_ROOT}" = "1" ]; then
    exec python3 "$@"
  fi
  exec runuser -u ahenk -m -- python3 "$@"
}

if [ "${DEBUG_MODE}" = "1" ]; then
  echo "[${AGENT_ID}] DEBUG_MODE=1 -> dummy_ahenk.py"
  run_agent /app/dummy_ahenk.py
fi

echo "[${AGENT_ID}] Upstream Ahenk foreground modda başlatılıyor"
run_agent /app/ahenk/src/ahenkd.py start "${XMPP_HOST:-ejabberd}" "${LIDER_USER:-lider-admin}" "${LIDER_PASS:-secret}"
