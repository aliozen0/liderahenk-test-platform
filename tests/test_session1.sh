#!/usr/bin/env bash
# =============================================================
# LiderAhenk Test Ortamı — Oturum 1 Doğrulama Testleri
# =============================================================
set -euo pipefail

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
PROJECT_NAME="liderahenk-test"
COMPOSE_CMD="docker compose -f compose/compose.core.yml -p ${PROJECT_NAME}"

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
info() { echo -e "${YELLOW}▶ $1${NC}"; }

# --- Ön hazırlık: .env dosyası ---
if [ ! -f .env ]; then
  info ".env dosyası bulunamadı, .env.example kopyalanıyor..."
  cp .env.example .env
fi

# =============================================================
# TEST A: make dev-core → konteynerler çalışıyor mu?
# =============================================================
info "TEST A: Çekirdek servisler başlatılıyor (make dev-core)..."
make dev-core

info "Healthcheck'ler bekleniyor (max 120s)..."
SERVICES=("mariadb" "ldap" "ejabberd")
TIMEOUT=120
for svc in "${SERVICES[@]}"; do
  elapsed=0
  while true; do
    # Konteyner ID'sini bul
    cid=$(${COMPOSE_CMD} ps -q "${svc}" 2>/dev/null | head -1)
    if [ -n "$cid" ]; then
      health=$(docker inspect --format='{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "none")
      if [ "$health" = "healthy" ]; then
        break
      fi
    fi
    sleep 5
    elapsed=$((elapsed + 5))
    if [ $elapsed -ge $TIMEOUT ]; then
      echo "  ⏰ ${svc} ${TIMEOUT}s içinde healthy olmadı"
      break
    fi
  done
done

# ps kontrolü
PS_OUTPUT=$(${COMPOSE_CMD} ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null)
echo "$PS_OUTPUT"

all_up=true
for svc in "${SERVICES[@]}"; do
  if echo "$PS_OUTPUT" | grep -qi "${svc}.*healthy\|${svc}.*Up"; then
    pass "Servis '${svc}' çalışıyor"
  else
    fail "Servis '${svc}' çalışmıyor veya healthy değil"
    all_up=false
  fi
done

# =============================================================
# TEST B: ldapsearch ile LDAP bağlantı testi
# =============================================================
info "TEST B: LDAP bağlantı testi (ldapsearch)..."
# LDAP konteynerinin içinden çalıştır
LDAP_CID=$(${COMPOSE_CMD} ps -q ldap | head -1)
if [ -n "$LDAP_CID" ]; then
  # .env'den değerleri al
  source .env
  LDAP_SEARCH_RESULT=$(docker exec "$LDAP_CID" \
    ldapsearch -x \
    -H "ldap://localhost:${LDAP_PORT}" \
    -b "${LDAP_BASE_DN}" \
    -D "cn=${LDAP_ADMIN_USERNAME},${LDAP_ROOT}" \
    -w "${LDAP_ADMIN_PASSWORD}" \
    "(objectclass=*)" dn 2>&1) || true
  if echo "$LDAP_SEARCH_RESULT" | grep -qi "result: 0\|dn:"; then
    pass "ldapsearch LDAP bağlantısı başarılı"
  else
    fail "ldapsearch LDAP bağlantısı başarısız"
    echo "    Çıktı: $LDAP_SEARCH_RESULT"
  fi
else
  fail "LDAP konteyneri bulunamadı"
fi

# =============================================================
# TEST C: ejabberdctl status testi
# =============================================================
info "TEST C: ejabberdctl status testi..."
EJABBERD_CID=$(${COMPOSE_CMD} ps -q ejabberd | head -1)
if [ -n "$EJABBERD_CID" ]; then
  EJABBERD_STATUS=$(docker exec "$EJABBERD_CID" /home/ejabberd/bin/ejabberdctl status 2>&1) || true
  if echo "$EJABBERD_STATUS" | grep -qi "started\|is running\|ejabberd"; then
    pass "ejabberdctl status başarılı"
  else
    fail "ejabberdctl status başarısız"
    echo "    Çıktı: $EJABBERD_STATUS"
  fi
else
  fail "ejabberd konteyneri bulunamadı"
fi

# =============================================================
# TEST D: mariadb dışa port açmamış mı?
# =============================================================
info "TEST D: mariadb dış port kontrolü..."
MARIADB_CID=$(${COMPOSE_CMD} ps -q mariadb | head -1)
if [ -n "$MARIADB_CID" ]; then
  PUBLISHED_PORTS=$(docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{if $conf}}{{$p}}={{(index $conf 0).HostPort}} {{end}}{{end}}' "$MARIADB_CID" 2>/dev/null)
  if [ -z "$PUBLISHED_PORTS" ]; then
    pass "mariadb dışa port yayımlamıyor"
  else
    fail "mariadb dışa port yayımlıyor: $PUBLISHED_PORTS"
  fi
else
  fail "mariadb konteyneri bulunamadı"
fi

# =============================================================
# TEST E: 4 ağ segmenti mevcut mu?
# =============================================================
info "TEST E: Ağ segmentleri kontrol ediliyor..."
EXPECTED_NETWORKS=("liderahenk_core" "liderahenk_agents" "liderahenk_obs" "liderahenk_external")
for net in "${EXPECTED_NETWORKS[@]}"; do
  FULL_NET="${PROJECT_NAME}_${net}"
  if docker network inspect "$FULL_NET" &>/dev/null; then
    pass "Ağ '${net}' mevcut"
  else
    fail "Ağ '${net}' bulunamadı (aranılan: ${FULL_NET})"
  fi
done

# --- liderahenk_core internal mi? ---
CORE_NET="${PROJECT_NAME}_liderahenk_core"
IS_INTERNAL=$(docker network inspect "$CORE_NET" --format='{{.Internal}}' 2>/dev/null || echo "false")
if [ "$IS_INTERNAL" = "true" ]; then
  pass "liderahenk_core ağı internal: true"
else
  fail "liderahenk_core ağı internal değil (beklenen: true, bulunan: $IS_INTERNAL)"
fi

# =============================================================
# SONUÇ
# =============================================================
echo ""
echo "==========================================="
echo -e "  TOPLAM: $((PASS + FAIL)) test"
echo -e "  ${GREEN}PASS: ${PASS}${NC}"
echo -e "  ${RED}FAIL: ${FAIL}${NC}"
echo "==========================================="

if [ $FAIL -eq 0 ]; then
  echo -e "${GREEN}🎉 TÜM TESTLER BAŞARILI!${NC}"
  exit 0
else
  echo -e "${RED}⚠️  BAZI TESTLER BAŞARISIZ!${NC}"
  exit 1
fi
