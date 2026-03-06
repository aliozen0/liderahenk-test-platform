#!/usr/bin/env bash
# =============================================================
# LiderAhenk Test Ortamı — Oturum 6 Doğrulama Testleri
# =============================================================
set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS=0; FAIL=0; SKIP=0
pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
skip() { echo -e "  ${YELLOW}⏭️  SKIP${NC}: $1"; SKIP=$((SKIP + 1)); }
info() { echo -e "\n${YELLOW}▶ $1${NC}"; }

source .env 2>/dev/null || true

# =============================================================
# A) make health → 3 servis sağlık bilgisi
# =============================================================
info "TEST A: make health → 3 servis bilgisi"
HEALTH_OUT=$(timeout 20 make health -s 2>&1) || true
LIDER_OK=$(echo "$HEALTH_OUT" | grep -cE "status|UP|liderapi" || true)
LDAP_OK=$(echo "$HEALTH_OUT" | grep -cE "numEntries|LDAP|ajan" || true)
if [ "$LIDER_OK" -gt 0 ] || [ "$LDAP_OK" -gt 0 ]; then
  pass "make health: servis bilgisi gösterildi"
else
  fail "make health eksik çıktı"
fi

# =============================================================
# B) make token → eyJ... ile başlayan token
# =============================================================
info "TEST B: make token → JWT token"
TOKEN=$(make token -s 2>&1) || true
if echo "$TOKEN" | grep -q "^eyJ"; then
  pass "make token: ${TOKEN:0:30}..."
else
  fail "make token: token alınamadı"
  echo "  Output: $TOKEN"
fi

# =============================================================
# C) make agents
# =============================================================
info "TEST C: make agents (authenticated API)"
AGENTS_OUT=$(make agents -s 2>&1) || true
if echo "$AGENTS_OUT" | grep -qiE "\[|\{|POST|endpoint"; then
  pass "make agents: çıktı döndü"
else
  fail "make agents: beklenmeyen çıktı"
fi

# =============================================================
# D) make run-scenario S=registration_test.yml
# =============================================================
info "TEST D: make run-scenario S=registration_test.yml"
REG_OUT=$(make run-scenario S=registration_test.yml 2>&1) || true
REG_RESULT=$(echo "$REG_OUT" | grep -c "PASS" || true)
REG_FAIL=$(echo "$REG_OUT" | grep -c "FAIL" || true)
if [ "$REG_RESULT" -gt 0 ] && echo "$REG_OUT" | grep -q "Sonuç.*PASS"; then
  pass "registration_test: PASS"
else
  fail "registration_test: FAIL"
  echo "$REG_OUT" | grep -E "✅|❌|Sonuç" | head -10
fi

# =============================================================
# E) make run-scenario S=basic_task.yml
# =============================================================
info "TEST E: make run-scenario S=basic_task.yml"
BASIC_OUT=$(make run-scenario S=basic_task.yml 2>&1) || true
if echo "$BASIC_OUT" | grep -q "Sonuç.*PASS"; then
  pass "basic_task: PASS"
else
  fail "basic_task: FAIL"
  echo "$BASIC_OUT" | grep -E "✅|❌|Sonuç" | head -10
fi

# =============================================================
# F) python3 orchestrator/cli.py --list
# =============================================================
info "TEST F: orchestrator/cli.py --list"
LIST_OUT=$(PYTHONPATH=. python3 orchestrator/cli.py --list 2>&1) || true
SCENARIO_COUNT=$(echo "$LIST_OUT" | grep -c "\.yml$" || true)
if [ "$SCENARIO_COUNT" -ge 3 ]; then
  pass "cli --list: $SCENARIO_COUNT senaryo listelendi"
else
  fail "cli --list: beklenen >=3, bulunan $SCENARIO_COUNT"
fi

# =============================================================
# G) make test-integration
# =============================================================
info "TEST G: make test-integration (pytest)"
INT_OUT=$(make test-integration 2>&1) || true
INT_PASSED=$(echo "$INT_OUT" | grep -oP '\d+ passed' | head -1 | grep -oP '\d+' || echo "0")
INT_FAILED=$(echo "$INT_OUT" | grep -oP '\d+ failed' | head -1 | grep -oP '\d+' || echo "0")
if echo "$INT_OUT" | grep -qP '\d+ passed' && [ "${INT_FAILED:-0}" -eq 0 ]; then
  pass "pytest integration: ${INT_PASSED} test PASS"
else
  fail "pytest integration: ${INT_PASSED} PASS, ${INT_FAILED} FAIL"
  echo "$INT_OUT" | grep -E "PASSED|FAILED|ERROR" | head -15
fi

# =============================================================
# H) Sözleşme testleri hâlâ geçiyor
# =============================================================
info "TEST H: Sözleşme testleri (geriye uyumluluk)"
CONTRACT_OUT=$(PYTHONPATH=. python3 -m pytest contracts/ -v --timeout=30 --tb=line 2>&1)
CONTRACT_PASSED=$(echo "$CONTRACT_OUT" | grep -oP '\d+ passed' | head -1 | grep -oP '\d+' || echo "0")
CONTRACT_FAILED=$(echo "$CONTRACT_OUT" | grep -oP '\d+ failed' | head -1 | grep -oP '\d+' || echo "0")
if [ "${CONTRACT_FAILED:-0}" -eq 0 ] && [ "${CONTRACT_PASSED:-0}" -ge 28 ]; then
  pass "pytest contract: ${CONTRACT_PASSED} test PASS"
else
  fail "pytest contract: ${CONTRACT_PASSED} PASS, ${CONTRACT_FAILED} FAIL"
fi

# =============================================================
# I) Dosya yapısı kontrolü
# =============================================================
info "TEST I: Dosya yapısı kontrolü"
EXPECTED=(
  "orchestrator/__init__.py"
  "orchestrator/main.py"
  "orchestrator/cli.py"
  "orchestrator/scenarios/registration_test.yml"
  "orchestrator/scenarios/basic_task.yml"
  "orchestrator/scenarios/scale_test.yml"
  "tests/test_integration.py"
  "tests/test_scale.py"
)
ALL_OK=true
for f in "${EXPECTED[@]}"; do
  if [ ! -f "$f" ]; then
    fail "Dosya eksik: $f"
    ALL_OK=false
  fi
done
if [ "$ALL_OK" = true ]; then
  pass "Tüm ${#EXPECTED[@]} dosya mevcut"
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
