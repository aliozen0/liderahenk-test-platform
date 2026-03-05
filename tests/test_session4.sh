#!/usr/bin/env bash
# =============================================================
# LiderAhenk Test Ortamı — Oturum 4 Doğrulama Testleri
# =============================================================
# ACL Adapter katmanı ve sözleşme testleri doğrulama
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

pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
skip() { echo -e "  ${YELLOW}⏭️  SKIP${NC}: $1"; SKIP=$((SKIP + 1)); }
info() { echo -e "\n${YELLOW}▶ $1${NC}"; }
detail() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }

# --- Ön hazırlık ---
if [ ! -f .env ]; then
  cp .env.example .env
fi
source .env

# =============================================================
# TEST A: Servisler ayakta mı?
# =============================================================
info "TEST A: Servisler ayakta mı kontrol..."

HEALTH_CODE=$(curl -so /dev/null -w '%{http_code}' http://localhost:8082/actuator/health 2>&1) || true
if [ "$HEALTH_CODE" = "200" ] || [ "$HEALTH_CODE" = "401" ]; then
  pass "liderapi ayakta (HTTP ${HEALTH_CODE})"
else
  fail "liderapi yanıt vermedi (HTTP ${HEALTH_CODE:-timeout})"
fi

# =============================================================
# TEST B: Auth mekanizması teyidi
# =============================================================
info "TEST B: /api/auth/signin endpoint teyidi..."

AUTH_CODE=$(curl -so /dev/null -w '%{http_code}' -X POST http://localhost:8082/api/auth/signin \
  -H 'Content-Type: application/json' \
  -d '{"username":"test","password":"test"}' 2>&1) || true
if [ "$AUTH_CODE" != "404" ]; then
  pass "POST /api/auth/signin mevcut (HTTP ${AUTH_CODE})"
  detail "Auth tipi: JWT (jjwt-0.13.0, LDAP-backed)"
else
  fail "POST /api/auth/signin bulunamadı (404)"
fi

# =============================================================
# TEST C: Adapter import testleri
# =============================================================
info "TEST C: Adapter import testleri..."

for adapter in "adapters.lider_api_adapter:LiderApiAdapter" \
               "adapters.xmpp_message_adapter:XmppMessageAdapter" \
               "adapters.ldap_schema_adapter:LdapSchemaAdapter"; do
  MODULE=$(echo "$adapter" | cut -d: -f1)
  CLASS=$(echo "$adapter" | cut -d: -f2)
  if PYTHONPATH=. python3 -c "from ${MODULE} import ${CLASS}; print('OK')" 2>/dev/null; then
    pass "${CLASS} import başarılı"
  else
    fail "${CLASS} import başarısız"
    PYTHONPATH=. python3 -c "from ${MODULE} import ${CLASS}" 2>&1 | head -5
  fi
done

# =============================================================
# TEST D: LDAP adapter direkt test
# =============================================================
info "TEST D: LDAP adapter direkt test..."

LDAP_RESULT=$(PYTHONPATH=. python3 -c "
from adapters.ldap_schema_adapter import LdapSchemaAdapter
a = LdapSchemaAdapter('localhost', ${LDAP_PORT}, '${LDAP_BASE_DN}',
    'cn=${LDAP_ADMIN_USERNAME},${LDAP_BASE_DN}', '${LDAP_ADMIN_PASSWORD}')
print('healthy:', a.connection_healthy())
print('agent_count:', a.get_agent_count())
print('ahenk-001:', a.agent_exists('ahenk-001'))
" 2>&1) || true

if echo "$LDAP_RESULT" | grep -q "healthy: True"; then
  pass "LdapSchemaAdapter bağlantı sağlıklı"
else
  fail "LdapSchemaAdapter bağlantı başarısız"
  detail "$LDAP_RESULT"
fi

LDAP_COUNT=$(echo "$LDAP_RESULT" | grep "agent_count:" | awk '{print $2}')
if [ "$LDAP_COUNT" = "$AHENK_COUNT" ] 2>/dev/null; then
  pass "LDAP'ta ${LDAP_COUNT} ajan (beklenen: ${AHENK_COUNT})"
else
  fail "LDAP ajan sayısı: ${LDAP_COUNT:-bilinmiyor} (beklenen: ${AHENK_COUNT})"
fi

if echo "$LDAP_RESULT" | grep -q "ahenk-001: True"; then
  pass "ahenk-001 LDAP'ta mevcut"
else
  fail "ahenk-001 LDAP'ta bulunamadı"
fi

# =============================================================
# TEST E: XMPP adapter direkt test
# =============================================================
info "TEST E: XMPP adapter direkt test..."

XMPP_RESULT=$(PYTHONPATH=. python3 -c "
from adapters.xmpp_message_adapter import XmppMessageAdapter
x = XmppMessageAdapter('http://localhost:15280/api',
    domain='${XMPP_DOMAIN}')
print('healthy:', x.api_healthy())
print('registered:', x.get_registered_count())
print('lider_sunucu:', x.is_user_registered('lider_sunucu'))
print('ahenk-001:', x.is_user_registered('ahenk-001'))
" 2>&1) || true

if echo "$XMPP_RESULT" | grep -q "healthy: True"; then
  pass "XmppMessageAdapter API sağlıklı"
else
  fail "XmppMessageAdapter API başarısız"
  detail "$XMPP_RESULT"
fi

if echo "$XMPP_RESULT" | grep -q "lider_sunucu: True"; then
  pass "lider_sunucu XMPP'te kayıtlı"
else
  fail "lider_sunucu XMPP'te bulunamadı"
fi

# =============================================================
# TEST F: pytest sözleşme testleri
# =============================================================
info "TEST F: pytest sözleşme testleri koşturuluyor..."

# Dependencies kur
pip install -r requirements-test.txt -q 2>/dev/null

PYTEST_OUTPUT=$(PYTHONPATH=. python3 -m pytest contracts/ -v --timeout=30 --tb=short 2>&1)
PYTEST_EXIT=$?

echo "$PYTEST_OUTPUT" | tail -20

PASSED=$(echo "$PYTEST_OUTPUT" | grep -oP '\d+ passed' | head -1 | grep -oP '\d+' || echo "0")
FAILED=$(echo "$PYTEST_OUTPUT" | grep -oP '\d+ failed' | head -1 | grep -oP '\d+' || echo "0")

if [ "$PYTEST_EXIT" -eq 0 ]; then
  pass "pytest: TÜM ${PASSED} test PASS"
else
  if [ "$PASSED" -gt 0 ]; then
    fail "pytest: ${PASSED} PASS, ${FAILED} FAIL"
  else
    fail "pytest çalıştırılamadı"
  fi
fi

# =============================================================
# TEST G: Adapter dosyaları mevcut mu?
# =============================================================
info "TEST G: Dosya yapısı kontrolü..."

EXPECTED_FILES=(
  "adapters/__init__.py"
  "adapters/lider_api_adapter.py"
  "adapters/xmpp_message_adapter.py"
  "adapters/ldap_schema_adapter.py"
  "contracts/conftest.py"
  "contracts/test_rest_contract.py"
  "contracts/test_ldap_contract.py"
  "contracts/test_xmpp_contract.py"
  "requirements-test.txt"
)

ALL_PRESENT=true
for f in "${EXPECTED_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    fail "Dosya eksik: $f"
    ALL_PRESENT=false
  fi
done

if [ "$ALL_PRESENT" = true ]; then
  pass "Tüm ${#EXPECTED_FILES[@]} dosya mevcut"
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
  echo -e "${GREEN}🎉 TÜM TESTLER BAŞARILI!${NC}"
  exit 0
else
  echo -e "${RED}⚠️  BAZI TESTLER BAŞARISIZ!${NC}"
  exit 1
fi
