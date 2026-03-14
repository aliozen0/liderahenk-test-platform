#!/bin/bash
# ============================================
# LiderCore — Entrypoint (systemd bypass)
# ============================================
# Karaf config dosyalarını environment'tan günceller
# ve Karaf'ı foreground'da başlatır.
set -e

echo "🚀 LiderCore başlatılıyor..."

# systemd kontrol — konteyner ortamında yok, atla
if command -v systemctl > /dev/null 2>&1; then
  echo "ℹ️  systemd mevcut ama konteyner ortamında kullanılmıyor."
else
  echo "ℹ️  systemd yok — Karaf doğrudan başlatılacak."
fi

KARAF_HOME="${KARAF_HOME:-/usr/share/lider-server}"
KARAF_BIN="${KARAF_HOME}/bin/karaf"
KARAF_LOG="${KARAF_HOME}/data/log/lider.log"

# Karaf binary kontrolü
if [ ! -f "$KARAF_BIN" ]; then
  echo "❌ HATA: Karaf bulunamadı: ${KARAF_BIN}"
  echo "   dpkg -L lider-server | head -20:"
  dpkg -L lider-server 2>/dev/null | head -20 || echo "   paket listelenemedi"
  exit 1
fi

# ============================================
# Karaf config dosyalarını environment'tan güncelle
# ============================================
echo "📝 Karaf konfigürasyonu güncelleniyor..."

# --- MariaDB Datasource ---
DS_CFG="${KARAF_HOME}/system/tr/org/liderahenk/lider-datasource-mariadb/1.0.0-SNAPSHOT/lider-datasource-mariadb-1.0.0-SNAPSHOT.cfg"
if [ -f "$DS_CFG" ]; then
  sed -i "s|db.server = .*|db.server = ${DB_HOST:-mariadb}:3306|" "$DS_CFG"
  sed -i "s|db.database = .*|db.database = ${DB_NAME:-liderahenk}|" "$DS_CFG"
  sed -i "s|db.username = .*|db.username = ${DB_USER:-root}|" "$DS_CFG"
  sed -i "s|db.password = .*|db.password = ${DB_PASSWORD:-DEGISTIR}|" "$DS_CFG"
  echo "  ✅ Datasource config güncellendi"
fi

# --- Lider Ana Config ---
MAIN_CFG="${KARAF_HOME}/system/tr/org/liderahenk/lider-config/1.0.0-SNAPSHOT/lider-config-1.0.0-SNAPSHOT.cfg"
if [ -f "$MAIN_CFG" ]; then
  # LDAP
  sed -i "s|ldap.server = .*|ldap.server = ${LDAP_HOST:-ldap}|" "$MAIN_CFG"
  sed -i "s|ldap.port = .*|ldap.port = ${LDAP_PORT:-1389}|" "$MAIN_CFG"
  sed -i "s|ldap.username = .*|ldap.username = ${LDAP_ADMIN_DN:-cn=admin,dc=liderahenk,dc=org}|" "$MAIN_CFG"
  sed -i "s|ldap.password = .*|ldap.password = ${LDAP_ADMIN_PASSWORD:-REPLACE_WITH_LDAP_PASSWORD}|" "$MAIN_CFG"
  sed -i "s|ldap.root.dn = .*|ldap.root.dn = ${LDAP_BASE_DN:-dc=liderahenk,dc=org}|" "$MAIN_CFG"

  # XMPP
  sed -i "s|xmpp.host = .*|xmpp.host = ${XMPP_HOST:-ejabberd}|" "$MAIN_CFG"
  sed -i "s|xmpp.service.name = .*|xmpp.service.name = ${XMPP_DOMAIN:-liderahenk.org}|" "$MAIN_CFG"
  sed -i "s|xmpp.resource = .*|xmpp.resource = ${XMPP_RESOURCE:-LiderAPI}|" "$MAIN_CFG"
  sed -i "s|xmpp.password = .*|xmpp.password = ${XMPP_ADMIN_PASS:-secret}|" "$MAIN_CFG"

  # Agent LDAP base DN
  sed -i "s|agent.ldap.base.dn = .*|agent.ldap.base.dn = ${LDAP_AGENT_BASE_DN:-ou=Ahenkler,${LDAP_BASE_DN:-dc=liderahenk,dc=org}}|" "$MAIN_CFG"
  sed -i "s|user.ldap.base.dn = .*|user.ldap.base.dn = ${LDAP_BASE_DN:-dc=liderahenk,dc=org}|" "$MAIN_CFG"
  sed -i "s|user.ldap.roles.dn= .*|user.ldap.roles.dn= ou=Roles,${LDAP_BASE_DN:-dc=liderahenk,dc=org}|" "$MAIN_CFG"

  # Test ortamı: agent kayıt yetkilendirmesini devre dışı bırak
  sed -i "s|user.authorization.enabled = .*|user.authorization.enabled = false|" "$MAIN_CFG"

  REG_CFG="${KARAF_HOME}/etc/tr.org.liderahenk.example.registration.cfg"
  if [ "${ENABLE_LEGACY_REGISTRATION_SIM:-0}" = "1" ]; then
    AHENK_COUNT=${AHENK_COUNT:-10}
    CSV_PATH="/tmp/records.csv"
    echo "  📋 legacy records.csv oluşturuluyor (${AHENK_COUNT} agent)..."
    rm -f "$CSV_PATH"
    for i in $(seq 1 "$AHENK_COUNT"); do
      ID=$(printf 'ahenk-%03d' "$i")
      echo "${ID}-host,${ID},Test,LiderAhenk,TestLab,liderahenk" >> "$CSV_PATH"
    done

    cat > "$REG_CFG" <<REGEOF
# Dinamik olarak entrypoint tarafından üretildi
file.protocol = local
file.path = ${CSV_PATH}
REGEOF
    echo "  ✅ Legacy registration sim aktif → ${CSV_PATH}"
  else
    rm -f /tmp/records.csv "$REG_CFG"
    echo "  ✅ Legacy registration sim kapalı; registration owner liderapi"
  fi

  # Hot deployment path
  sed -i "s|hot.deployment.path=.*|hot.deployment.path=${KARAF_HOME}/deploy/|" "$MAIN_CFG"

  echo "  ✅ Ana config güncellendi (LDAP, XMPP, Agent)"
fi

echo "📝 Konfigürasyon tamamlandı."

# Log dizini oluştur (yoksa)
mkdir -p "$(dirname "$KARAF_LOG")"

# Log dosyalarını stdout'a yönlendir (background)
(
  while [ ! -f "$KARAF_LOG" ]; do
    sleep 2
  done
  tail -f "$KARAF_LOG"
) &

echo "✅ Karaf başlatılıyor: ${KARAF_BIN} run"

# JMX Prometheus Exporter — port 9779'da metrik sunma
export EXTRA_JAVA_OPTS="-javaagent:/opt/jmx_exporter.jar=9779:/opt/jmx_config.yml"
echo "📊 JMX Exporter port 9779'da aktif"

# Karaf'ı foreground'da çalıştır
exec "$KARAF_BIN" run
