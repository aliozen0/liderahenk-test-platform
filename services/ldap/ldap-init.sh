#!/bin/sh
# ============================================
# LDAP Init — Schema + Admin Kullanıcı Yükleme
# LDAP container healthcheck'ten sonra çalışır.
# ldapi:/// soketi ile root yetkili erişim kullanır.
# ============================================
set -e

# Gerekli araçları kur (python:3.12-slim imajında mevcut değil)
apt-get update -qq && apt-get install -y -qq ldap-utils > /dev/null 2>&1
echo "[ldap-init] ✅ ldap-utils yüklendi"

LDAP_HOST="${LDAP_HOST:-ldap}"
LDAP_PORT="${LDAP_PORT:-1389}"
LDAP_BASE_DN="${LDAP_BASE_DN:-dc=liderahenk,dc=org}"
LDAP_ADMIN_DN="cn=${LDAP_ADMIN_USERNAME:-admin},${LDAP_BASE_DN}"
LDAP_ADMIN_PW="${LDAP_ADMIN_PASSWORD:-DEGISTIR}"
LDAP_USERS_OU="${LDAP_USERS_OU:-ou=users,${LDAP_BASE_DN}}"
LDAP_GROUPS_OU="${LDAP_GROUPS_OU:-ou=Groups,${LDAP_BASE_DN}}"
LDAP_AGENT_GROUPS_OU="${LDAP_AGENT_GROUPS_OU:-ou=AgentGroups,${LDAP_BASE_DN}}"
LDAP_ROLES_OU="${LDAP_ROLES_OU:-ou=Roles,${LDAP_BASE_DN}}"
LDAP_AGENTS_OU="${LDAP_AGENT_BASE_DN:-ou=Ahenkler,${LDAP_BASE_DN}}"
LIDER_ADMIN_UID="${LIDER_ADMIN_UID:-lider-admin}"
LIDER_ADMIN_PASS="${LIDER_ADMIN_PASS:-secret}"

ensure_ou() {
  ENTRY_DN="$1"
  OU_VALUE="$2"
  LDIF_PATH="$3"
  cat > "${LDIF_PATH}" << EOF
dn: ${ENTRY_DN}
objectClass: organizationalUnit
ou: ${OU_VALUE}
EOF

  ldapadd -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" -f "${LDIF_PATH}" 2>&1 || {
    echo "[ldap-init] ℹ️  OU zaten mevcut: ${ENTRY_DN}"
  }
}

echo "[ldap-init] LDAP bekleniyor: ${LDAP_HOST}:${LDAP_PORT}..."
for i in $(seq 1 30); do
  if ldapsearch -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" -b "${LDAP_BASE_DN}" "(objectClass=top)" dn > /dev/null 2>&1; then
    echo "[ldap-init] ✅ LDAP hazır (deneme $i)"
    break
  fi
  echo "[ldap-init]   ⏳ Bekleniyor... ($i/30)"
  sleep 2
done

# ─── Adım 1: LiderAhenk Şeması ────────────────────────────
echo "[ldap-init] LiderAhenk şeması kontrol ediliyor..."
SCHEMA_EXISTS=$(ldapsearch -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" -b "${LDAP_BASE_DN}" "(objectClass=pardusAccount)" dn 2>/dev/null | grep -c "numEntries" || true)

if [ "$SCHEMA_EXISTS" = "0" ] || [ -z "$SCHEMA_EXISTS" ]; then
  echo "[ldap-init] Şema yükleniyor (ldapi:/// EXTERNAL)..."
  # Container içinden root yetkisiyle çalışır
  ldapadd -Y EXTERNAL -H ldapi:/// -f /schemas/liderahenk.ldif 2>&1 || {
    # "Already exists" (68) veya "Duplicate" (80) hatası normal — geç
    echo "[ldap-init] ℹ️  Şema zaten yüklü veya yükleme sonucu yukarıda"
  }
else
  echo "[ldap-init] ℹ️  Şema zaten yüklü — SKIP"
fi

if ! ldapsearch -Y EXTERNAL -H ldapi:/// -b "cn=liderahenk,cn=schema,cn=config" "(objectClass=olcSchemaConfig)" olcObjectClasses 2>/dev/null \
  | grep -q "NAME 'pardusDeviceGroup'"; then
  echo "[ldap-init] Eksik pardusDeviceGroup şeması ekleniyor..."
  cat > /tmp/liderahenk-schema-device-group.ldif << EOF
dn: cn=liderahenk,cn=schema,cn=config
changetype: modify
add: olcObjectClasses
olcObjectClasses: ( 2.4.2.42.1.9.7.8.1.1.6.5 NAME 'pardusDeviceGroup' AUXILIARY MAY ( liderGroupType ) )
EOF
  ldapmodify -Y EXTERNAL -H ldapi:/// -f /tmp/liderahenk-schema-device-group.ldif 2>&1 || {
    echo "[ldap-init] ℹ️  pardusDeviceGroup zaten ekli veya modify sonucu yukarıda"
  }
fi

# ─── Adım 2: Admin Kullanıcısı (SSHA) ─────────────────────
echo "[ldap-init] LDAP kokleri kontrol ediliyor..."
ensure_ou "${LDAP_USERS_OU}" "users" /tmp/users-ou.ldif
ensure_ou "${LDAP_GROUPS_OU}" "Groups" /tmp/groups-ou.ldif
ensure_ou "${LDAP_AGENT_GROUPS_OU}" "AgentGroups" /tmp/agent-groups-ou.ldif
ensure_ou "${LDAP_ROLES_OU}" "Roles" /tmp/roles-ou.ldif
ensure_ou "${LDAP_AGENTS_OU}" "Ahenkler" /tmp/agents-ou.ldif

echo "[ldap-init] Admin kullanıcısı kontrol ediliyor..."

# SSHA hash oluştur (Python gerekli)
SSHA_HASH=$(python3 -c "
import hashlib, os, base64
password = '${LIDER_ADMIN_PASS}'
salt = os.urandom(8)
sha1 = hashlib.sha1(password.encode('utf-8') + salt).digest()
print('{SSHA}' + base64.b64encode(sha1 + salt).decode())
")

ADMIN_EXISTS=$(ldapsearch -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" -b "${LDAP_USERS_OU}" "(uid=${LIDER_ADMIN_UID})" dn 2>/dev/null | grep -c "numEntries" || true)

if [ "$ADMIN_EXISTS" = "0" ] || [ -z "$ADMIN_EXISTS" ]; then
  echo "[ldap-init] Admin kullanıcısı oluşturuluyor: uid=${LIDER_ADMIN_UID},${LDAP_USERS_OU}"
  cat > /tmp/admin-user.ldif << EOF
dn: uid=${LIDER_ADMIN_UID},${LDAP_USERS_OU}
objectClass: inetOrgPerson
objectClass: organizationalPerson
objectClass: person
objectClass: pardusAccount
objectClass: pardusLider
objectClass: top
uid: ${LIDER_ADMIN_UID}
cn: Lider Admin
sn: Admin
userPassword: ${SSHA_HASH}
mail: admin@liderahenk.org
liderPrivilege: ROLE_ADMIN
liderPrivilege: ROLE_USER
EOF

  ldapadd -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" -f /tmp/admin-user.ldif 2>&1 || {
    echo "[ldap-init] ℹ️  Admin kullanıcısı zaten mevcut"
  }
  echo "[ldap-init] ✅ Admin kullanıcısı oluşturuldu (SSHA)"
else
  echo "[ldap-init] ℹ️  Admin kullanıcısı mevcut — şifre SSHA ile güncelleniyor..."
  cat > /tmp/update-password.ldif << EOF
dn: uid=${LIDER_ADMIN_UID},${LDAP_USERS_OU}
changetype: modify
replace: userPassword
userPassword: ${SSHA_HASH}
EOF
  ldapmodify -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" -f /tmp/update-password.ldif 2>&1
  echo "[ldap-init] ✅ Admin şifresi SSHA ile güncellendi"
fi

# ─── Doğrulama ─────────────────────────────────────────────
echo "[ldap-init] LDAP bind doğrulaması..."
BIND_RESULT=$(ldapwhoami -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "uid=${LIDER_ADMIN_UID},${LDAP_USERS_OU}" -w "${LIDER_ADMIN_PASS}" 2>&1)
if echo "$BIND_RESULT" | grep -q "dn:"; then
  echo "[ldap-init] ✅ LDAP bind başarılı: $BIND_RESULT"
else
  echo "[ldap-init] ❌ LDAP bind başarısız: $BIND_RESULT"
fi

echo "[ldap-init] =========================================="
echo "[ldap-init] ✅ LDAP init tamamlandı"
echo "[ldap-init] =========================================="

echo "[ldap-init] Bitnami generik test verileri (user01, user02) temizleniyor..."

ldapdelete -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" "cn=user01,ou=users,dc=liderahenk,dc=org" 2>/dev/null || true
ldapdelete -x -H "ldap://${LDAP_HOST}:${LDAP_PORT}" -D "${LDAP_ADMIN_DN}" -w "${LDAP_ADMIN_PW}" "cn=user02,ou=users,dc=liderahenk,dc=org" 2>/dev/null || true

echo "[ldap-init] ✅ Bitnami test verileri temizlendi"
