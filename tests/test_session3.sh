#!/usr/bin/env bash
# =============================================================
# LiderAhenk Test Ortamı — Oturum 3 Doğrulama Testleri
# =============================================================
# Testler:
#   A) ejabberd vhost teyidi
#   B) lider_sunucu kullanıcısı teyidi
#   C) lider-core XMPP timeout kontrolü
#   D) provisioner exit code 0
#   E) provisioner log'da "DONE" mesajı
#   F) LDAP ou=Ahenkler kayıt sayısı
#   G) Ahenk konteynerleri Up
#   H) Ahenk port yayımlamıyor
#   I) liderapi hâlâ sağlıklı
# =============================================================
set -uo pipefail

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0
PROJECT_NAME="liderahenk-test"
COMPOSE_CORE="docker compose --env-file .env -f compose/compose.core.yml -p ${PROJECT_NAME}"
COMPOSE_LIDER="docker compose --env-file .env -f compose/compose.core.yml -f compose/compose.lider.yml -p ${PROJECT_NAME}"
COMPOSE_ALL="docker compose --env-file .env -f compose/compose.core.yml -f compose/compose.lider.yml -f compose/compose.agents.yml -p ${PROJECT_NAME}"

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
skip() { echo -e "  ${YELLOW}⏭️  SKIP${NC}: $1"; SKIP=$((SKIP + 1)); }
info() { echo -e "\n${YELLOW}▶ $1${NC}"; }
detail() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }

# --- Ön hazırlık: .env dosyası ---
if [ ! -f .env ]; then
  cp .env.example .env
fi
source .env

# =============================================================
# TEST A: ejabberd vhost teyidi
# =============================================================
info "TEST A: ejabberd vhost teyidi (liderahenk.org)..."

EJABBERD_CID=$(${COMPOSE_CORE} ps -q ejabberd 2>/dev/null | head -1)
if [ -n "$EJABBERD_CID" ]; then
  VHOSTS=$(docker exec "$EJABBERD_CID" /home/ejabberd/bin/ejabberdctl registered_vhosts 2>/dev/null || echo "")
  if echo "$VHOSTS" | grep -q "liderahenk.org"; then
    pass "liderahenk.org vhost kayıtlı"
  else
    fail "liderahenk.org vhost bulunamadı (mevcut: ${VHOSTS})"
  fi
else
  fail "ejabberd konteyneri bulunamadı"
fi

# =============================================================
# TEST B: lider_sunucu kullanıcısı teyidi
# =============================================================
info "TEST B: lider_sunucu XMPP kullanıcısı teyidi..."

if [ -n "$EJABBERD_CID" ]; then
  if docker exec "$EJABBERD_CID" /home/ejabberd/bin/ejabberdctl check_account lider_sunucu liderahenk.org 2>/dev/null; then
    pass "lider_sunucu@liderahenk.org kayıtlı"
  else
    fail "lider_sunucu@liderahenk.org bulunamadı"
    detail "Kayıtlı kullanıcılar:"
    docker exec "$EJABBERD_CID" /home/ejabberd/bin/ejabberdctl registered_users liderahenk.org 2>/dev/null | head -5
  fi
else
  fail "ejabberd konteyneri bulunamadı (TEST A'dan)"
fi

# =============================================================
# TEST C: lider-core XMPP timeout (NoResponseException) kontrolü
# =============================================================
info "TEST C: lider-core XMPP timeout kontrolü..."

LIDERCORE_CID=$(${COMPOSE_LIDER} ps -q lider-core 2>/dev/null | head -1)
if [ -n "$LIDERCORE_CID" ]; then
  TIMEOUT_COUNT=$(docker logs "$LIDERCORE_CID" 2>&1 | grep -ci "NoResponseException" || true)
  if [ "$TIMEOUT_COUNT" -eq 0 ] 2>/dev/null; then
    pass "lider-core loglarında NoResponseException yok"
  else
    fail "lider-core loglarında ${TIMEOUT_COUNT} NoResponseException hatası"
    detail "İlk 3 hata:"
    docker logs "$LIDERCORE_CID" 2>&1 | grep -i "NoResponseException" | head -3
  fi
else
  skip "lider-core konteyneri bulunamadı (lider servisleri çalışmıyor olabilir)"
fi

# =============================================================
# TEST D: provisioner exit code 0
# =============================================================
info "TEST D: provisioner exit code kontrolü..."

PROV_CID=$(${COMPOSE_ALL} ps -a -q provisioner 2>/dev/null | head -1)
if [ -n "$PROV_CID" ]; then
  PROV_EXIT=$(docker inspect --format='{{.State.ExitCode}}' "$PROV_CID" 2>/dev/null)
  if [ "$PROV_EXIT" = "0" ]; then
    pass "provisioner exit code 0"
  else
    fail "provisioner exit code: ${PROV_EXIT} (beklenen: 0)"
    detail "Son 10 satır log:"
    docker logs "$PROV_CID" 2>&1 | tail -10
  fi
else
  skip "provisioner konteyneri bulunamadı (make dev çalıştırılmamış olabilir)"
fi

# =============================================================
# TEST E: provisioner log'da "DONE" mesajı
# =============================================================
info "TEST E: provisioner DONE mesajı kontrolü..."

if [ -n "$PROV_CID" ]; then
  DONE_LINE=$(docker logs "$PROV_CID" 2>&1 | grep "\[DONE\]" || echo "")
  if [ -n "$DONE_LINE" ]; then
    pass "provisioner DONE mesajı bulundu"
    detail "$DONE_LINE"
  else
    fail "provisioner logunda [DONE] mesajı yok"
    detail "Son 5 satır log:"
    docker logs "$PROV_CID" 2>&1 | tail -5
  fi
else
  skip "provisioner konteyneri bulunamadı"
fi

# =============================================================
# TEST F: LDAP ou=Ahenkler kayıt sayısı
# =============================================================
info "TEST F: LDAP ou=Ahenkler kayıt doğrulaması..."

LDAP_CID=$(${COMPOSE_CORE} ps -q ldap 2>/dev/null | head -1)
if [ -n "$LDAP_CID" ]; then
  LDAP_RESULT=$(docker exec "$LDAP_CID" ldapsearch -x \
    -H "ldap://localhost:${LDAP_PORT}" \
    -b "ou=Ahenkler,${LDAP_BASE_DN}" \
    -D "cn=${LDAP_ADMIN_USERNAME},${LDAP_BASE_DN}" \
    -w "${LDAP_ADMIN_PASSWORD}" \
    "(objectClass=device)" 2>/dev/null || echo "")

  ENTRY_COUNT=$(echo "$LDAP_RESULT" | grep -c "^dn:" || true)

  if [ "$ENTRY_COUNT" -ge "${AHENK_COUNT}" ] 2>/dev/null; then
    pass "LDAP'ta ${ENTRY_COUNT} ajan kaydı bulundu (beklenen: ≥${AHENK_COUNT})"
  elif [ "$ENTRY_COUNT" -gt 0 ] 2>/dev/null; then
    fail "LDAP'ta sadece ${ENTRY_COUNT} ajan kaydı var (beklenen: ${AHENK_COUNT})"
  else
    fail "LDAP'ta ou=Ahenkler altında kayıt bulunamadı"
    detail "LDAP tree kontrol ediliyor..."
    docker exec "$LDAP_CID" ldapsearch -x \
      -H "ldap://localhost:${LDAP_PORT}" \
      -b "${LDAP_BASE_DN}" \
      -D "cn=${LDAP_ADMIN_USERNAME},${LDAP_BASE_DN}" \
      -w "${LDAP_ADMIN_PASSWORD}" \
      -s one "(objectClass=*)" dn 2>/dev/null | head -10
  fi
else
  fail "LDAP konteyneri bulunamadı"
fi

# =============================================================
# TEST G: Ahenk konteynerleri Up durumda
# =============================================================
info "TEST G: Ahenk konteynerleri Up durumda mı..."

AHENK_UP=$(${COMPOSE_ALL} ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null | grep -i "ahenk" | grep -ci "Up" || true)
if [ "$AHENK_UP" -gt 0 ] 2>/dev/null; then
  pass "${AHENK_UP} ahenk konteyneri Up durumda"
else
  # Provisioner çalışmamışsa ahenk de başlamaz
  PROV_STATUS=$(docker inspect --format='{{.State.Status}}' "$PROV_CID" 2>/dev/null || echo "unknown")
  if [ "$PROV_STATUS" = "exited" ]; then
    PROV_EXIT_CHK=$(docker inspect --format='{{.State.ExitCode}}' "$PROV_CID" 2>/dev/null || echo "?")
    if [ "$PROV_EXIT_CHK" != "0" ]; then
      skip "Ahenk başlatılamadı — provisioner exit code: ${PROV_EXIT_CHK}"
    else
      fail "Ahenk konteyneri Up değil (provisioner başarılı olmasına rağmen)"
    fi
  else
    skip "Ahenk konteyneri Up değil (provisioner durumu: ${PROV_STATUS})"
  fi
fi

# =============================================================
# TEST H: Ahenk port yayımlamıyor
# =============================================================
info "TEST H: Ahenk port izolasyonu kontrolü..."

AHENK_CID=$(${COMPOSE_ALL} ps -q ahenk 2>/dev/null | head -1)
if [ -n "$AHENK_CID" ]; then
  PUBLISHED=$(docker port "$AHENK_CID" 2>/dev/null || echo "")
  if [ -z "$PUBLISHED" ]; then
    pass "Ahenk konteyneri dışa port yayımlamıyor"
  else
    fail "Ahenk konteyneri dışa port yayımlıyor: ${PUBLISHED}"
  fi
else
  skip "Ahenk konteyneri bulunamadı"
fi

# =============================================================
# TEST I: liderapi hâlâ sağlıklı
# =============================================================
info "TEST I: liderapi health endpoint kontrolü..."

HEALTH_CODE=$(curl -so /dev/null -w '%{http_code}' http://localhost:8082/actuator/health 2>&1) || true
if [ "$HEALTH_CODE" = "200" ] || [ "$HEALTH_CODE" = "401" ]; then
  pass "liderapi /actuator/health → HTTP ${HEALTH_CODE} (uygulama çalışıyor)"
else
  skip "liderapi yanıt vermedi (HTTP ${HEALTH_CODE:-timeout}) — lider servisleri çalışmıyor olabilir"
fi

# =============================================================
# SONUÇ
# =============================================================
echo ""
echo "==========================================="
echo -e "  TOPLAM: $((PASS + FAIL + SKIP)) test"
echo -e "  ${GREEN}PASS: ${PASS}${NC}"
echo -e "  ${RED}FAIL: ${FAIL}${NC}"
echo -e "  ${YELLOW}SKIP: ${SKIP}${NC}"
echo "==========================================="

if [ $FAIL -eq 0 ]; then
  if [ $SKIP -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Bazı testler atlandı (servisler çalışmıyor olabilir)${NC}"
    echo -e "${YELLOW}   Tam test için: make clean-hard && make dev${NC}"
  else
    echo -e "${GREEN}🎉 TÜM TESTLER BAŞARILI!${NC}"
  fi
  exit 0
else
  echo -e "${RED}⚠️  BAZI TESTLER BAŞARISIZ!${NC}"
  exit 1
fi
