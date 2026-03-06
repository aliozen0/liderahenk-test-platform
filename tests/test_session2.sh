#!/usr/bin/env bash
# =============================================================
# LiderAhenk Test Ortamı — Oturum 2 Doğrulama Testleri
# =============================================================
set -euo pipefail

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
PROJECT_NAME="liderahenk-test"
COMPOSE_CORE="docker compose --env-file .env -f compose/compose.core.yml -p ${PROJECT_NAME}"
COMPOSE_LIDER="docker compose --env-file .env -f compose/compose.core.yml -f compose/compose.lider.yml -p ${PROJECT_NAME}"

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
info() { echo -e "\n${YELLOW}▶ $1${NC}"; }
detail() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }

# --- Ön hazırlık: .env dosyası ---
if [ ! -f .env ]; then
  cp .env.example .env
fi
source .env

# =============================================================
# TEST A: bitnamilegacy LDAP port teyidi
# =============================================================
info "TEST A: bitnamilegacy LDAP port teyidi..."

# Çekirdek servislerin çalıştığından emin ol
${COMPOSE_CORE} up -d 2>&1 | tail -3

LDAP_CID=$(${COMPOSE_CORE} ps -q ldap | head -1)
if [ -n "$LDAP_CID" ]; then
  CONTAINER_LDAP_PORT=$(docker exec "$LDAP_CID" env | grep LDAP_PORT_NUMBER | cut -d= -f2)
  if [ "$CONTAINER_LDAP_PORT" = "$LDAP_PORT" ]; then
    pass "LDAP port .env'de doğru: ${LDAP_PORT}"
  else
    fail "LDAP port uyumsuz! Container: ${CONTAINER_LDAP_PORT}, .env: ${LDAP_PORT}"
  fi
else
  fail "LDAP konteyneri bulunamadı"
fi

# =============================================================
# TEST B: make build-lider → exit code 0
# =============================================================
info "TEST B: Lider imajları build ediliyor (make build-lider)..."
detail "Bu ilk build'de uzun sürebilir (Maven + Node indirmeleri)..."

BUILD_LOG=$(mktemp)
if make build-lider > "$BUILD_LOG" 2>&1; then
  pass "make build-lider başarılı (exit code 0)"
else
  BUILD_EXIT=$?
  fail "make build-lider başarısız (exit code: ${BUILD_EXIT})"

  # Hata analizi
  echo ""
  echo -e "  ${RED}--- BUILD HATA ANALİZİ ---${NC}"

  if grep -qi "mvn\|maven\|pom.xml\|BUILD FAILURE" "$BUILD_LOG"; then
    echo -e "  ${RED}Maven build hatası algılandı:${NC}"
    grep -A5 "BUILD FAILURE\|ERROR\|FATAL" "$BUILD_LOG" | head -20
    echo ""
    echo -e "  ${CYAN}Spring Boot / Java uyumu kontrol ediliyor...${NC}"
  fi

  if grep -qi "yarn\|npm\|node\|ERR!" "$BUILD_LOG"; then
    echo -e "  ${RED}Node/Yarn build hatası algılandı:${NC}"
    grep -A3 "error\|ERR!\|FAIL" "$BUILD_LOG" | head -20
  fi

  if grep -qi "lider.*not found\|Unable to locate package\|repo.liderahenk" "$BUILD_LOG"; then
    echo -e "  ${RED}Pardus repo / paket hatası algılandı:${NC}"
    grep -A3 "not found\|Unable to locate\|404\|repo.liderahenk" "$BUILD_LOG" | head -20
    echo ""
    echo -e "  ${CYAN}Repo erişilebilirlik testi:${NC}"
    curl -sI https://repo.liderahenk.org.tr 2>&1 | head -3
  fi

  if grep -qi "karaf\|systemd\|systemctl" "$BUILD_LOG"; then
    echo -e "  ${RED}Karaf/systemd bağımlılık hatası algılandı${NC}"
  fi

  echo -e "  ${RED}--- BUILD LOG (son 30 satır) ---${NC}"
  tail -30 "$BUILD_LOG"
  echo -e "  ${RED}--- BUILD LOG SONU ---${NC}"
fi
rm -f "$BUILD_LOG"

# =============================================================
# TEST C: make dev-lider → 3 servis Up/healthy
# =============================================================
info "TEST C: Lider servisleri başlatılıyor (make dev-lider)..."

make dev-lider 2>&1 | tail -10

# Healthcheck bekleme (lider-core yavaş başlar)
LIDER_SERVICES=("lider-core" "liderapi" "lider-ui")
TIMEOUT=180
info "Healthcheck bekleniyor (max ${TIMEOUT}s)..."

for svc in "${LIDER_SERVICES[@]}"; do
  elapsed=0
  while true; do
    cid=$(${COMPOSE_LIDER} ps -q "${svc}" 2>/dev/null | head -1)
    if [ -n "$cid" ]; then
      status=$(docker inspect --format='{{.State.Status}}' "$cid" 2>/dev/null || echo "none")
      health=$(docker inspect --format='{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "none")
      if [ "$health" = "healthy" ] || ([ "$status" = "running" ] && [ "$health" = "none" ]); then
        break
      fi
    fi
    sleep 5
    elapsed=$((elapsed + 5))
    if [ $elapsed -ge $TIMEOUT ]; then
      echo "  ⏰ ${svc} ${TIMEOUT}s içinde hazır olmadı"
      break
    fi
  done
done

PS_OUTPUT=$(${COMPOSE_LIDER} ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null)
echo "$PS_OUTPUT"

for svc in "${LIDER_SERVICES[@]}"; do
  if echo "$PS_OUTPUT" | grep -qi "${svc}.*healthy\|${svc}.*Up"; then
    pass "Servis '${svc}' çalışıyor"
  else
    fail "Servis '${svc}' çalışmıyor veya healthy değil"
    detail "Loglar:"
    ${COMPOSE_LIDER} logs --tail 10 "${svc}" 2>&1 | head -15
  fi
done

# =============================================================
# TEST D: liderapi health endpoint
# =============================================================
info "TEST D: liderapi health endpoint kontrolü..."
HEALTH_CODE=$(curl -so /dev/null -w '%{http_code}' http://localhost:8082/actuator/health 2>&1) || true
if [ "$HEALTH_CODE" = "200" ] || [ "$HEALTH_CODE" = "401" ]; then
  pass "liderapi /actuator/health → HTTP ${HEALTH_CODE} (uygulama çalışıyor)"
else
  fail "liderapi /actuator/health yanıt vermedi (HTTP ${HEALTH_CODE})"
  detail "Yanıt: ${HEALTH_RESPONSE:-boş}"
fi

# =============================================================
# TEST E: lider-ui HTTP 200
# =============================================================
info "TEST E: lider-ui HTTP 200 kontrolü..."
UI_HTTP_CODE=$(curl -so /dev/null -w "%{http_code}" http://localhost:3001 2>/dev/null) || true
if [ "$UI_HTTP_CODE" = "200" ]; then
  pass "lider-ui HTTP 200 döndü"
else
  fail "lider-ui HTTP ${UI_HTTP_CODE:-timeout} döndü (beklenen: 200)"
fi

# =============================================================
# TEST F: lider-core loglarında ERROR/EXCEPTION yok
# =============================================================
info "TEST F: lider-core hata log kontrolü..."
LIDERCORE_CID=$(${COMPOSE_LIDER} ps -q lider-core 2>/dev/null | head -1)
if [ -n "$LIDERCORE_CID" ]; then
  ERROR_LINES=$(docker logs "$LIDERCORE_CID" 2>&1 | grep -ci "ERROR\|EXCEPTION" || true)
  if [ "$ERROR_LINES" -eq 0 ] 2>/dev/null; then
    pass "lider-core loglarında ERROR/EXCEPTION yok"
  else
    fail "lider-core loglarında ${ERROR_LINES} hata satırı bulundu"
    detail "İlk 5 hata:"
    docker logs "$LIDERCORE_CID" 2>&1 | grep -i "ERROR\|EXCEPTION" | head -5
  fi
else
  fail "lider-core konteyneri bulunamadı"
fi

# =============================================================
# TEST G: liderapi → liderahenk_external ağında mı?
# =============================================================
info "TEST G: liderapi ağ kontrolü..."
LIDERAPI_CID=$(${COMPOSE_LIDER} ps -q liderapi 2>/dev/null | head -1)
if [ -n "$LIDERAPI_CID" ]; then
  NETWORKS=$(docker inspect --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$LIDERAPI_CID" 2>/dev/null)
  if echo "$NETWORKS" | grep -q "liderahenk_external"; then
    pass "liderapi liderahenk_external ağında"
  else
    fail "liderapi liderahenk_external ağında değil (ağlar: ${NETWORKS})"
  fi
else
  fail "liderapi konteyneri bulunamadı"
fi

# =============================================================
# TEST H: mariadb PortBindings boş mu?
# =============================================================
info "TEST H: mariadb dış port kontrolü (tekrar)..."
MARIADB_CID=$(${COMPOSE_CORE} ps -q mariadb 2>/dev/null | head -1)
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
# TEST I: lider-core sadece liderahenk_core ağında
# =============================================================
info "TEST I: lider-core ağ izolasyonu kontrolü..."
LIDERCORE_CID=$(${COMPOSE_LIDER} ps -q lider-core 2>/dev/null | head -1)
if [ -n "$LIDERCORE_CID" ]; then
  NETWORKS=$(docker inspect --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$LIDERCORE_CID" 2>/dev/null)
  IN_CORE=false
  IN_EXTERNAL=false
  echo "$NETWORKS" | grep -q "liderahenk_core" && IN_CORE=true
  echo "$NETWORKS" | grep -q "liderahenk_external" && IN_EXTERNAL=true

  if [ "$IN_CORE" = true ] && [ "$IN_EXTERNAL" = false ]; then
    pass "lider-core sadece liderahenk_core ağında (izolasyon doğru)"
  else
    fail "lider-core ağ izolasyonu yanlış (ağlar: ${NETWORKS})"
  fi
else
  fail "lider-core konteyneri bulunamadı"
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
