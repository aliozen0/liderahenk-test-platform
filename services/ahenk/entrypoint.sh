#!/bin/bash
# ===========================================================
# Ahenk Agent — Entrypoint
# ===========================================================
set -e

# Thundering herd önleme — rastgele gecikme
JITTER=$(( RANDOM % ${JITTER_MAX_SECONDS:-30} ))
echo "[ahenk] Jitter bekleme: ${JITTER}sn"
sleep ${JITTER}

# AGENT_INDEX zorunlu
if [ -z "${AGENT_INDEX}" ]; then
  echo "HATA: AGENT_INDEX tanımlı değil" && exit 1
fi
AGENT_ID=$(printf 'ahenk-%03d' "${AGENT_INDEX}")

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
  exec python3 /app/ahenk.py
else
  echo "[${AGENT_ID}] ahenk.py bulunamadı — simülasyon modunda"
  echo "[${AGENT_ID}] Config: /etc/ahenk/ahenk.conf"
  cat /etc/ahenk/ahenk.conf
  # Konteyneri canlı tut (ölçek testleri için)
  echo "[${AGENT_ID}] Bekleme modunda..."
  exec tail -f /dev/null
fi
