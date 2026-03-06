#!/usr/bin/env bash
# =============================================================
# LiderAhenk Test Ortamı — Oturum 5 Doğrulama Testleri
# =============================================================
# LDAP şema + admin kullanıcı + gözlemlenebilirlik stack
# =============================================================
set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
PASS=0; FAIL=0; SKIP=0
pass() { echo -e "  ${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
skip() { echo -e "  ${YELLOW}⏭️  SKIP${NC}: $1"; SKIP=$((SKIP + 1)); }
info() { echo -e "\n${YELLOW}▶ $1${NC}"; }
detail() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }

source .env 2>/dev/null || true

# =============================================================
# A) pardusAccount objectClass LDAP'ta tanımlı mı?
# =============================================================
info "TEST A: pardusAccount objectClass tanımlı mı?"
SCHEMA_CHECK=$(ldapsearch -x -H ldap://localhost:1389 \
  -D "cn=$LDAP_ADMIN_USERNAME,$LDAP_BASE_DN" -w "$LDAP_ADMIN_PASSWORD" \
  -b "$LDAP_BASE_DN" "(objectClass=pardusAccount)" dn 2>&1) || true
# Şema tanımlı ise hata vermez (boş sonuç bile olabilir)
if echo "$SCHEMA_CHECK" | grep -q "Undefined objectClass\|undefined"; then
  fail "pardusAccount objectClass tanımsız — şema yüklenmedi"
else
  pass "pardusAccount objectClass tanımlı"
fi

# =============================================================
# B) lider-admin kullanıcısı oluşturuldu mu?
# =============================================================
info "TEST B: lider-admin kullanıcısı mevcut mu?"
ADMIN_CHECK=$(ldapsearch -x -H ldap://localhost:1389 \
  -D "cn=$LDAP_ADMIN_USERNAME,$LDAP_BASE_DN" -w "$LDAP_ADMIN_PASSWORD" \
  -b "$LDAP_BASE_DN" "(uid=lider-admin)" liderPrivilege 2>&1) || true
if echo "$ADMIN_CHECK" | grep -q "liderPrivilege"; then
  pass "lider-admin kullanıcısı mevcut ve liderPrivilege var"
  detail "$(echo "$ADMIN_CHECK" | grep liderPrivilege)"
else
  fail "lider-admin bulunamadı veya liderPrivilege eksik"
  detail "$ADMIN_CHECK"
fi

# =============================================================
# C) JWT auth — token alınabiliyor mu?
# =============================================================
info "TEST C: JWT auth — /api/auth/signin ile token alınableyor mu?"
LOGIN_RESP=$(curl -s -X POST http://localhost:8082/api/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"username":"lider-admin","password":"secret"}' 2>&1) || true
TOKEN=$(echo "$LOGIN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null) || true
if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
  pass "JWT token alındı: ${TOKEN:0:30}..."
else
  fail "JWT token alınamadı"
  detail "$LOGIN_RESP"
fi

# =============================================================
# D) Token ile authenticated API çağrısı
# =============================================================
info "TEST D: Authenticated API çağrısı (token kabul ediliyor mu?)"
if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
  # liderapi endpoint'leri genellikle POST — 404 = endpoint bulunamadı ama auth geçti
  # 401/403 = token reddedildi
  COMP_CODE=$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer $TOKEN" \
    http://localhost:8082/api/computers 2>&1) || true
  if [ "$COMP_CODE" = "401" ] || [ "$COMP_CODE" = "403" ]; then
    fail "Token reddedildi (HTTP $COMP_CODE)"
  else
    pass "Token kabul edildi (HTTP $COMP_CODE — endpoint POST tabanlı olabilir)"
  fi
else
  skip "Token yok — authenticated test atlanıyor"
fi

# =============================================================
# E) Prometheus erişilebilir
# =============================================================
info "TEST E: Prometheus 9090"
PROM_CODE=$(curl -so /dev/null -w '%{http_code}' http://localhost:9090/-/healthy 2>&1) || true
if [ "$PROM_CODE" = "200" ]; then
  pass "Prometheus erişilebilir (HTTP 200)"
else
  fail "Prometheus yanıt vermedi (HTTP ${PROM_CODE:-timeout})"
fi

# =============================================================
# F) Grafana erişilebilir
# =============================================================
info "TEST F: Grafana 3000"
GRAF_RESP=$(curl -s http://localhost:3000/api/health 2>&1) || true
if echo "$GRAF_RESP" | grep -q "ok"; then
  pass "Grafana erişilebilir"
else
  fail "Grafana yanıt vermedi"
  detail "$GRAF_RESP"
fi

# =============================================================
# G) Loki erişilebilir
# =============================================================
info "TEST G: Loki 3100"
LOKI_RESP=$(curl -s http://localhost:3100/ready 2>&1) || true
if echo "$LOKI_RESP" | grep -qi "ready"; then
  pass "Loki hazır"
else
  fail "Loki hazır değil"
  detail "$LOKI_RESP"
fi

# =============================================================
# H) Prometheus alert kuralları
# =============================================================
info "TEST H: Alert kuralları yüklendi mi?"
ALERT_RESP=$(curl -s http://localhost:9090/api/v1/rules 2>&1) || true
RULE_COUNT=$(echo "$ALERT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(len(g['rules']) for g in d['data']['groups']))" 2>/dev/null) || true
if [ -n "$RULE_COUNT" ] && [ "$RULE_COUNT" -gt 0 ] 2>/dev/null; then
  pass "Prometheus: ${RULE_COUNT} alert kuralı yüklü"
else
  fail "Alert kuralları bulunamadı"
fi

# =============================================================
# I) Önceki sözleşme testleri hâlâ PASS
# =============================================================
info "TEST I: Önceki sözleşme testleri (pytest)"
PYTEST_OUT=$(PYTHONPATH=. python3 -m pytest contracts/ -v --timeout=30 --tb=line 2>&1)
PYTEST_EXIT=$?
PYTEST_PASSED=$(echo "$PYTEST_OUT" | grep -oP '\d+ passed' | head -1 | grep -oP '\d+' || echo "0")
PYTEST_FAILED=$(echo "$PYTEST_OUT" | grep -oP '\d+ failed' | head -1 | grep -oP '\d+' || echo "0")
if [ "$PYTEST_EXIT" -eq 0 ]; then
  pass "pytest: ${PYTEST_PASSED} test PASS (geriye uyumluluk OK)"
else
  fail "pytest: ${PYTEST_PASSED} PASS, ${PYTEST_FAILED} FAIL"
fi

# =============================================================
# J) Dosya yapısı kontrolü
# =============================================================
info "TEST J: Dosya yapısı kontrolü"
EXPECTED=(
  "services/ldap/schema/liderahenk.ldif"
  "services/ldap/seed/admin-user.ldif"
  "observability/prometheus/prometheus.yml"
  "observability/prometheus/alerts.yml"
  "observability/loki/loki-config.yml"
  "observability/grafana/dashboards/liderahenk-slo.json"
  "observability/grafana/provisioning/datasources/prometheus.yml"
  "observability/grafana/provisioning/datasources/loki.yml"
  "observability/grafana/provisioning/dashboards/dashboard.yml"
  "observability/otel/otel-config.yml"
  "compose/compose.obs.yml"
  "compose/compose.tracing.yml"
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
