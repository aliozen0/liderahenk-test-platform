#!/usr/bin/env bash
# ==============================================================
#  LiderAhenk API Veri Doğrulama Testi
#  200 dönmesi yetmez — veriler gerçek ve tutarlı mı?
#  Kullanım: make test-api-data
# ==============================================================
set -uo pipefail

API_URL="${1:-http://localhost:8082}"
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0; RESULTS=""

# ── Token ─────────────────────────────────────────────────────
TOKEN=$(curl -s -X POST "$API_URL/api/auth/signin" \
  -H "Content-Type: application/json" \
  -d '{"username":"lider-admin","password":"secret"}' 2>/dev/null \
  | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('token',''))" 2>/dev/null)

if [ -z "$TOKEN" ] || [ ${#TOKEN} -lt 20 ]; then
  echo -e "${RED}FAIL — Login başarısız${NC}"
  exit 1
fi

# ── Helpers ───────────────────────────────────────────────────
api_json() {
  curl -s -X "$1" "$API_URL$2" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    ${3:+-d "$3"} 2>/dev/null
}
api_form() {
  curl -s -X POST "$API_URL$1" \
    -H "Authorization: Bearer $TOKEN" \
    -d "$2" 2>/dev/null
}
pass() { PASS=$((PASS+1)); RESULTS+="  ${GREEN}✅${NC} $1\n"; }
fail() { FAIL=$((FAIL+1)); RESULTS+="  ${RED}❌${NC} $1 → $2\n"; }
warn() { WARN=$((WARN+1)); RESULTS+="  ${YELLOW}⚠️ ${NC} $1 → $2\n"; }
section() { RESULTS+="\n${BOLD}$1${NC}\n"; }

echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   LiderAhenk Veri Doğrulama Testi                     ║${NC}"
echo -e "${BOLD}║   $(date '+%Y-%m-%d %H:%M:%S')                             ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"

# ══════════════════════════════════════════════════════════════════
# 1. Dashboard verileri
# ══════════════════════════════════════════════════════════════════
section "[1] Dashboard Verileri — Sayılar gerçek mi?"
DASH=$(api_json POST "/api/dashboard/info" '{}')
DASH_COMP=$(echo "$DASH" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('totalComputerNumber',0))" 2>/dev/null)
DASH_ONLINE=$(echo "$DASH" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('totalOnlineComputerNumber',0))" 2>/dev/null)
DASH_USER=$(echo "$DASH" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('totalUserNumber',0))" 2>/dev/null)
DASH_TASK=$(echo "$DASH" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('totalSentTaskNumber',0))" 2>/dev/null)
DASH_POLICY=$(echo "$DASH" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('totalAssignedPolicyNumber',0))" 2>/dev/null)

[ "$DASH_COMP" -gt 0 ] 2>/dev/null && pass "Bilgisayar sayısı: $DASH_COMP" || fail "Bilgisayar sayısı 0" "Agent kayıtlı değil?"
[ "$DASH_ONLINE" -gt 0 ] 2>/dev/null && pass "Online bilgisayar: $DASH_ONLINE" || warn "Online bilgisayar: $DASH_ONLINE" "Agent'lar offline olabilir"
[ "$DASH_USER" -gt 0 ] 2>/dev/null && pass "Kullanıcı sayısı: $DASH_USER" || fail "Kullanıcı sayısı 0" "LDAP bağlantı sorunu?"
[ "$DASH_TASK" -gt 0 ] 2>/dev/null && pass "Görev sayısı: $DASH_TASK" || warn "Görev sayısı: $DASH_TASK" "Hiç task gönderilmemiş olabilir"

# ══════════════════════════════════════════════════════════════════
# 2. Agent verisi DB ve Dashboard tutarlı mı?
# ══════════════════════════════════════════════════════════════════
section "[2] Agent Verisi — DB ile tutarlı mı?"
AGENT_DATA=$(api_json POST "/api/lider/agent-info/list" '{"pageNumber":1,"pageSize":100}')
API_AGENTS=$(echo "$AGENT_DATA" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('agents',{}).get('totalElements',0))" 2>/dev/null)

[ "$API_AGENTS" -gt 0 ] 2>/dev/null && pass "Agent API'den $API_AGENTS agent döndü" || fail "Agent API boş" "agents.totalElements = 0"

# Dashboard ile cross-check
if [ "$API_AGENTS" = "$DASH_COMP" ] 2>/dev/null; then
  pass "Dashboard ($DASH_COMP) = Agent API ($API_AGENTS) ✓"
else
  warn "Dashboard ($DASH_COMP) ≠ Agent API ($API_AGENTS)" "Fark olabilir"
fi

# DB ile cross-check
DB_AGENTS=$(docker exec liderahenk-test-mariadb-1 mariadb --user=root --password=DEGISTIR liderahenk -N -e "SELECT COUNT(*) FROM c_agent WHERE is_deleted=0;" 2>/dev/null | tr -d '[:space:]')
if [ "$DB_AGENTS" = "$API_AGENTS" ] 2>/dev/null; then
  pass "DB ($DB_AGENTS) = API ($API_AGENTS) ✓"
else
  fail "DB ($DB_AGENTS) ≠ API ($API_AGENTS)" "Veri tutarsızlığı!"
fi

# LDAP ile cross-check
LDAP_AGENTS=$(docker exec liderahenk-test-ldap-1 ldapsearch -x -H ldap://localhost:1389 -D "cn=admin,dc=liderahenk,dc=org" -w DEGISTIR -b "ou=Ahenkler,dc=liderahenk,dc=org" "(objectClass=pardusDevice)" dn 2>/dev/null | grep -c "^dn:" || echo "0")
if [ "$LDAP_AGENTS" = "$API_AGENTS" ] 2>/dev/null; then
  pass "LDAP ($LDAP_AGENTS) = API ($API_AGENTS) ✓"
else
  warn "LDAP ($LDAP_AGENTS) ≠ API ($API_AGENTS)" "LDAP/DB sync farkı"
fi

# Agent veri kalitesi
AGENT_HAS_JID=$(echo "$AGENT_DATA" | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
agents=d.get('agents',{}).get('content',[])
if agents:
    a=agents[0]
    has_jid = bool(a.get('jid'))
    has_dn = bool(a.get('dn'))
    has_host = bool(a.get('hostname'))
    has_ip = bool(a.get('ipAddresses'))
    print(f'jid={has_jid} dn={has_dn} host={has_host} ip={has_ip}')
else:
    print('EMPTY')
" 2>/dev/null)
echo "$AGENT_HAS_JID" | grep -q "jid=True" && pass "Agent JID alanı dolu" || fail "Agent JID boş" "$AGENT_HAS_JID"
echo "$AGENT_HAS_JID" | grep -q "dn=True" && pass "Agent DN alanı dolu" || fail "Agent DN boş" "$AGENT_HAS_JID"
echo "$AGENT_HAS_JID" | grep -q "host=True" && pass "Agent hostname dolu" || fail "Agent hostname boş" "$AGENT_HAS_JID"

# ══════════════════════════════════════════════════════════════════
# 3. Policy verisi tutarlı mı?
# ══════════════════════════════════════════════════════════════════
section "[3] Policy Verisi — DB ile tutarlı mı?"
POLICIES=$(api_json POST "/api/policy/list" '{"pageNumber":1,"pageSize":100}')
API_POLICY=$(echo "$POLICIES" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(len(d) if isinstance(d,list) else d.get('totalElements',0))" 2>/dev/null)

DB_POLICY=$(docker exec liderahenk-test-mariadb-1 mariadb --user=root --password=DEGISTIR liderahenk -N -e "SELECT COUNT(*) FROM c_policy WHERE deleted=0;" 2>/dev/null | tr -d '[:space:]')
if [ "$API_POLICY" = "$DB_POLICY" ] 2>/dev/null; then
  pass "Policy: API ($API_POLICY) = DB ($DB_POLICY) ✓"
else
  warn "Policy: API ($API_POLICY) ≠ DB ($DB_POLICY)" "Format farkı olabilir"
fi

ACTIVE=$(api_json GET "/api/policy/active-policies")
ACTIVE_COUNT=$(echo "$ACTIVE" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null)
[ "$ACTIVE_COUNT" -le "$API_POLICY" ] 2>/dev/null && pass "Aktif ($ACTIVE_COUNT) ≤ Toplam ($API_POLICY) ✓" || fail "Aktif > Toplam" "Mantık hatası"

# ══════════════════════════════════════════════════════════════════
# 4. Settings cross-check
# ══════════════════════════════════════════════════════════════════
section "[4] Settings — Config tutarlı mı?"
CFG=$(api_json GET "/api/lider/settings/configurations")
LDAP_HOST=$(echo "$CFG" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('ldapServer',''))" 2>/dev/null)
XMPP_HOST=$(echo "$CFG" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('xmppHost',''))" 2>/dev/null)
LDAP_ROOT=$(echo "$CFG" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('ldapRootDn',''))" 2>/dev/null)

[ -n "$LDAP_HOST" ] && pass "LDAP server: $LDAP_HOST" || fail "LDAP server boş" ""
[ -n "$XMPP_HOST" ] && pass "XMPP host: $XMPP_HOST" || fail "XMPP host boş" ""
echo "$LDAP_ROOT" | grep -q "dc=" && pass "LDAP root DN: $LDAP_ROOT" || fail "LDAP root DN geçersiz" "$LDAP_ROOT"

# LDAP bağlantısı gerçekten çalışıyor mu?
LDAP_OK=$(docker exec liderahenk-test-ldap-1 ldapsearch -x -H ldap://localhost:1389 -D "cn=admin,dc=liderahenk,dc=org" -w DEGISTIR -b "$LDAP_ROOT" "(objectClass=organization)" dn 2>/dev/null | grep -c "^dn:" || echo "0")
[ "$LDAP_OK" -gt 0 ] && pass "LDAP bağlantısı çalışıyor ✓" || fail "LDAP bağlantı hatası" "Root DN erişilemiyor"

# ══════════════════════════════════════════════════════════════════
# 5. Plugin tutarlılığı
# ══════════════════════════════════════════════════════════════════
section "[5] Plugin Verileri — DB ile tutarlı mı?"
TASK_PLUGINS=$(api_json POST "/api/get-plugin-task-list" '{}' | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null)
DB_PLUGINS=$(docker exec liderahenk-test-mariadb-1 mariadb --user=root --password=DEGISTIR liderahenk -N -e "SELECT COUNT(*) FROM c_plugin;" 2>/dev/null | tr -d '[:space:]')
[ "$TASK_PLUGINS" -gt 0 ] 2>/dev/null && pass "Task plugin: $TASK_PLUGINS adet" || fail "Task plugin yok" ""
[ -n "$DB_PLUGINS" ] && pass "DB plugin: $DB_PLUGINS adet" || warn "DB plugin count alınamadı" ""

# ══════════════════════════════════════════════════════════════════
# 6. Rapor verileri gerçek mi?
# ══════════════════════════════════════════════════════════════════
section "[6] Rapor Verileri — Gerçek kayıtlar var mı?"
# operationType DB'de INT enum: 5=LOGIN. pageNumber 1-indexed (custom DTO)
OP_LOGS=$(api_form "/api/operation/logs" "pageNumber=1&pageSize=5&operationType=5")
LOG_COUNT=$(echo "$OP_LOGS" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('totalElements',0))" 2>/dev/null)
LOG_CONTENT=$(echo "$OP_LOGS" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('content',[])))" 2>/dev/null)
[ "$LOG_COUNT" -gt 0 ] 2>/dev/null && pass "Login logları: $LOG_COUNT kayıt" || warn "Login log yok" "Henüz login olmamış olabilir"
[ "$LOG_CONTENT" -gt 0 ] 2>/dev/null && pass "Log content dolu ($LOG_CONTENT sayfa)" || fail "Log content boş" "totalElements=$LOG_COUNT ama content=0"

# Log'daki kullanıcı doğru mu?
LOG_USER=$(echo "$OP_LOGS" | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
c=d.get('content',[])
if c: print(c[0].get('userId','?'))
else: print('EMPTY')
" 2>/dev/null)
echo "$LOG_USER" | grep -q "lider-admin" && pass "Log'daki user: lider-admin ✓" || warn "Log user beklenmeyen" "$LOG_USER"

# DB ile doğrula (operation_type=5 = LOGIN)
DB_LOGS=$(docker exec liderahenk-test-mariadb-1 mariadb --user=root --password=DEGISTIR liderahenk -N -e "SELECT COUNT(*) FROM c_operation_log WHERE operation_type=5;" 2>/dev/null | tr -d '[:space:]')
if [ -n "$DB_LOGS" ] && [ "$DB_LOGS" -gt 0 ] 2>/dev/null; then
  pass "DB login log: $DB_LOGS kayıt"
  # API ile karşılaştır — yakın mı? (test sırasında login artabileceğinden ±50 tolerans)
  DIFF=$((DB_LOGS - LOG_COUNT))
  [ "${DIFF#-}" -le 50 ] 2>/dev/null && pass "API ($LOG_COUNT) ≈ DB ($DB_LOGS) ✓" || warn "API ($LOG_COUNT) ≠ DB ($DB_LOGS)" "Test sırasında login artmış olabilir"
fi

# ══════════════════════════════════════════════════════════════════
# 7. XMPP bağlantı doğrulama
# ══════════════════════════════════════════════════════════════════
section "[7] XMPP Bağlantısı"
# Not: /api/messaging/get-messaging-server-info upstream'de body(null) dönüyor
# Gerçek XMPP kontrolünü ejabberd üzerinden ve Settings config'den yapıyoruz
XMPP_HOST_CFG=$(echo "$CFG" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('xmppHost',''))" 2>/dev/null)
XMPP_PORT=$(echo "$CFG" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('xmppPort',''))" 2>/dev/null)
[ -n "$XMPP_HOST_CFG" ] && pass "XMPP host config: $XMPP_HOST_CFG" || fail "XMPP host config boş" ""
# ejabberd container ayakta mı?
EJABBERD_OK=$(docker exec liderahenk-test-ejabberd-1 /home/ejabberd/bin/ejabberdctl status 2>/dev/null | grep -c "is started" || echo "0")
[ "$EJABBERD_OK" -gt 0 ] && pass "ejabberd servisi çalışıyor ✓" || warn "ejabberd status alınamadı" "Container erişim sorunu olabilir"
# ejabberd'de kayıtlı kullanıcı var mı?
XMPP_USERS=$(docker exec liderahenk-test-ejabberd-1 /home/ejabberd/bin/ejabberdctl registered_users liderahenk.org 2>/dev/null | wc -l)
[ "$XMPP_USERS" -gt 0 ] 2>/dev/null && pass "XMPP kayıtlı kullanıcı: $XMPP_USERS" || warn "XMPP kullanıcı yok" ""

# ══════════════════════════════════════════════════════════════════
# 8. Versiyon
# ══════════════════════════════════════════════════════════════════
section "[8] Versiyon Doğrulama"
VER=$(curl -s "$API_URL/api/lider-info/version" -H "Authorization: Bearer $TOKEN" 2>/dev/null | tr -d '"')
[ -n "$VER" ] && pass "Lider versiyon: $VER" || fail "Versiyon alınamadı" ""

# ══════════════════════════════════════════════════════════════════
# SONUÇLAR
# ══════════════════════════════════════════════════════════════════
TOTAL=$((PASS + FAIL + WARN))
echo -e "$RESULTS"
echo -e "${BOLD}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  VERİ DOĞRULAMA SONUCU                                ║${NC}"
echo -e "${BOLD}╠════════════════════════════════════════════════════════╣${NC}"
printf  "${BOLD}║${NC}  ${GREEN}✅ Doğru:      %-4s${NC}                                 ${BOLD}║${NC}\n" "$PASS"
printf  "${BOLD}║${NC}  ${YELLOW}⚠️  Uyarı:      %-4s${NC}                                 ${BOLD}║${NC}\n" "$WARN"
printf  "${BOLD}║${NC}  ${RED}❌ Tutarsız:   %-4s${NC}                                 ${BOLD}║${NC}\n" "$FAIL"
printf  "${BOLD}║${NC}  Toplam:      %-4s                                 ${BOLD}║${NC}\n" "$TOTAL"
echo -e "${BOLD}╠════════════════════════════════════════════════════════╣${NC}"
PCT=$((PASS * 100 / TOTAL))
if [ "$FAIL" -eq 0 ]; then
  echo -e "${BOLD}║${NC}  ${GREEN}Veri Tutarlılığı: %${PCT}${NC}                              ${BOLD}║${NC}"
else
  echo -e "${BOLD}║${NC}  ${RED}Veri Tutarlılığı: %${PCT} — ${FAIL} tutarsızlık!${NC}           ${BOLD}║${NC}"
fi
echo -e "${BOLD}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
[ "$FAIL" -gt 0 ] && exit 1 || exit 0
