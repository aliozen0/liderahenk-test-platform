#!/usr/bin/env bash
# ==============================================================
#  LiderAhenk API Health Check — Tüm Endpoint'ler
#  Kullanım: ./tests/test_api_health.sh [API_URL]
#  Make:     make test-api
# ==============================================================
set -euo pipefail

API_URL="${1:-http://localhost:8082}"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0
RESULTS=""

# ── Login & Token ─────────────────────────────────────────────
get_token() {
  local resp
  resp=$(curl -s -X POST "$API_URL/api/auth/signin" \
    -H "Content-Type: application/json" \
    -d '{"username":"lider-admin","password":"secret"}' 2>/dev/null)
  echo "$resp" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('token',''))" 2>/dev/null
}

# ── Test Helper ───────────────────────────────────────────────
# test_endpoint <label> <method> <path> [content-type] [body]
test_endpoint() {
  local label="$1" method="$2" path="$3"
  local ct="${4:-}" body="${5:-}"
  local url="$API_URL$path"
  local args=(-s -o /dev/null -w "%{http_code}" -X "$method")

  if [ -n "$ct" ]; then
    args+=(-H "Content-Type: $ct")
  fi
  args+=(-H "Authorization: Bearer $TOKEN")
  if [ -n "$body" ]; then
    args+=(-d "$body")
  fi

  local code
  code=$(curl "${args[@]}" "$url" 2>/dev/null || echo "000")

  if [ "$code" = "200" ]; then
    PASS=$((PASS + 1))
    RESULTS+="  ${GREEN}✅ ${code}${NC} ${label}\n"
  elif [ "$code" = "417" ]; then
    WARN=$((WARN + 1))
    RESULTS+="  ${YELLOW}⚠️  ${code}${NC} ${label} (config gerekli)\n"
  else
    FAIL=$((FAIL + 1))
    RESULTS+="  ${RED}❌ ${code}${NC} ${label}\n"
  fi
}

# ── Banner ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     LiderAhenk API Health Check                     ║${NC}"
echo -e "${BOLD}║     $(date '+%Y-%m-%d %H:%M:%S')                            ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Token ─────────────────────────────────────────────────────
echo -ne "  ${CYAN}Authenticating...${NC} "
TOKEN=$(get_token)
if [ -z "$TOKEN" ] || [ ${#TOKEN} -lt 20 ]; then
  echo -e "${RED}FAIL — API'ye bağlanılamadı ($API_URL)${NC}"
  exit 1
fi
echo -e "${GREEN}OK${NC} (token: ${TOKEN:0:20}...)"
echo ""

# ══════════════════════════════════════════════════════════════
# MODÜL 1: AUTH & LOGIN
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 1] Auth & Login${NC}\n"
test_endpoint "POST /auth/signin"          POST "/api/auth/signin"          "application/json" '{"username":"lider-admin","password":"secret"}'
test_endpoint "POST /auth/logout"          POST "/api/auth/logout"          "application/json" '{}'
test_endpoint "POST /dashboard/info"       POST "/api/dashboard/info"       "application/json" '{}'
test_endpoint "GET  /ldap-login/config"    GET  "/api/ldap-login/configurations"
test_endpoint "POST /forgot-password"      POST "/api/forgot-password/"     "application/json" '{"username":"lider-admin"}'
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 2: AGENT / COMPUTER
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 2] Agent / Computer${NC}\n"
test_endpoint "GET  /computer/ou"          GET  "/api/lider/computer/ou"
test_endpoint "POST /computer/computers"   POST "/api/lider/computer/computers" "application/json" '{}'
test_endpoint "POST /computer/ou-details"  POST "/api/lider/computer/ou-details" "application/json" '{"searchDn":"ou=Ahenkler,dc=liderahenk,dc=org"}'
test_endpoint "POST /computer/search"      POST "/api/lider/computer/search-entry" "" "searchDn=dc%3Dliderahenk%2Cdc%3Dorg&key=objectClass&value=pardusDevice"
test_endpoint "POST /agent-info/list"      POST "/api/lider/agent-info/list" "application/json" '{"pageNumber":1,"pageSize":5}'
test_endpoint "POST /select-agent/detail"  POST "/api/select-agent-info/detail?agentJid=ahenk-001"
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 3: TASK EXECUTION
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 3] Task Execution${NC}\n"
test_endpoint "GET  /task-report/plugins"  GET  "/api/lider/executed-task-report/plugins"
test_endpoint "GET  /sched-report/plugins" GET  "/api/lider/scheduled-task-report/plugins"
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 4: POLICY & PROFILE
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 4] Policy & Profile${NC}\n"
test_endpoint "POST /policy/list"          POST "/api/policy/list"          "application/json" '{"pageNumber":1,"pageSize":5}'
test_endpoint "GET  /policy/active"        GET  "/api/policy/active-policies"
test_endpoint "POST /profile/list"         POST "/api/profile/list?name=script"
test_endpoint "GET  /profile/all-list"     GET  "/api/profile/all-list"
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 5: USER & GROUP
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 5] User & Group${NC}\n"
test_endpoint "POST /user/users"           POST "/api/lider/user/users"     "application/json" '{"searchDn":"dc=liderahenk,dc=org"}'
test_endpoint "POST /user/ou-details"      POST "/api/lider/user/ou-details" "application/json" '{"searchDn":"dc=liderahenk,dc=org"}'
test_endpoint "GET  /user/configurations"  GET  "/api/lider/user/configurations"
test_endpoint "POST /user-groups/groups"   POST "/api/lider/user-groups/groups" "application/json" '{"searchDn":"ou=Groups,dc=liderahenk,dc=org"}'
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 6: COMPUTER GROUPS
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 6] Computer Groups${NC}\n"
test_endpoint "POST /comp-groups/groups"   POST "/api/lider/computer-groups/groups" "application/json" '{"searchDn":"ou=AgentGroups,dc=liderahenk,dc=org"}'
test_endpoint "POST /comp-groups/ou"       POST "/api/lider/computer-groups/ou-details" "application/json" '{"searchDn":"ou=AgentGroups,dc=liderahenk,dc=org"}'
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 7: REPORTS
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 7] Reports${NC}\n"
test_endpoint "POST /agent-session/list"   POST "/api/lider/agent-session/list"   "" "pageNumber=1&pageSize=10&getFilterData=false"
test_endpoint "POST /user-session/list"    POST "/api/lider/user-session/list"    "" "pageNumber=1&pageSize=10&sessionType=LOGIN"
test_endpoint "POST /operation/logs"       POST "/api/operation/logs"             "" "pageNumber=1&pageSize=10&operationType=LOGIN"
test_endpoint "GET  /operation-log-type"   GET  "/api/lider/operation-log-type"
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 8: SETTINGS & CONFIG
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 8] Settings & Config${NC}\n"
test_endpoint "GET  /settings/config"      GET  "/api/lider/settings/configurations"
test_endpoint "GET  /settings/users"       GET  "/api/lider/settings/console-users"
test_endpoint "GET  /settings/roles"       GET  "/api/lider/settings/roles"
test_endpoint "GET  /server/list"          GET  "/api/server/list"
test_endpoint "GET  /script/list-all"      GET  "/api/script/list-all"
test_endpoint "GET  /conky/list-all"       GET  "/api/conky/list-all"
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 9: AD & SUDO
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 9] AD & Sudo${NC}\n"
test_endpoint "POST /ad/configurations"    POST "/api/ad/configurations"    "application/json" '{}'
test_endpoint "POST /sudo-groups/groups"   POST "/api/lider/sudo-groups/groups" "application/json" '{"searchDn":"ou=Roles,dc=liderahenk,dc=org"}'
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 10: REMOTE & TRANSFER
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 10] Remote & Transfer${NC}\n"
test_endpoint "POST /messaging/info"       POST "/api/messaging/get-messaging-server-info" "application/json" '{}'
test_endpoint "GET  /packages/repo"        GET  "/api/packages/repo-address"
test_endpoint "GET  /policy-exception"     GET  "/api/policy-exception/list"
RESULTS+="\n"

# ══════════════════════════════════════════════════════════════
# MODÜL 11: EK CONTROLLER'LAR
# ══════════════════════════════════════════════════════════════
RESULTS+="${BOLD}[Modül 11] Ek Controller'lar${NC}\n"
test_endpoint "GET  /lider-info/version"   GET  "/api/lider-info/version"
test_endpoint "POST /plugin-task-list"     POST "/api/get-plugin-task-list"  "application/json" '{}'
test_endpoint "POST /plugin-profile-list"  POST "/api/get-plugin-profile-list" "application/json" '{}'
test_endpoint "POST /lider-console/profile" POST "/api/lider-console/profile" "application/json" '{}'
test_endpoint "POST /change-language"      POST "/api/lider/change-language?langa1799b6ac27611eab3de0242ac130004=tr"
RESULTS+="\n"

# ── Sonuçlar ──────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))

echo -e "$RESULTS"
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  SONUÇ                                              ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
printf  "${BOLD}║${NC}  ${GREEN}✅ Başarılı:  %-5s${NC}                                ${BOLD}║${NC}\n" "$PASS"
printf  "${BOLD}║${NC}  ${YELLOW}⚠️  Config:    %-5s${NC}                                ${BOLD}║${NC}\n" "$WARN"
printf  "${BOLD}║${NC}  ${RED}❌ Başarısız: %-5s${NC}                                ${BOLD}║${NC}\n" "$FAIL"
printf  "${BOLD}║${NC}  Toplam:     %-5s                                ${BOLD}║${NC}\n" "$TOTAL"
echo -e "${BOLD}╠══════════════════════════════════════════════════════╣${NC}"

if [ "$FAIL" -eq 0 ]; then
  PCT=$((PASS * 100 / TOTAL))
  echo -e "${BOLD}║${NC}  ${GREEN}Başarı Oranı: %${PCT} (config hariç %100)${NC}            ${BOLD}║${NC}"
  echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
  echo ""
  exit 0
else
  PCT=$((PASS * 100 / TOTAL))
  echo -e "${BOLD}║${NC}  ${RED}Başarı Oranı: %${PCT} — ${FAIL} endpoint başarısız!${NC}       ${BOLD}║${NC}"
  echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
  echo ""
  exit 1
fi
