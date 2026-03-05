#!/bin/sh
# ===========================================================
# ejabberd — Custom Entrypoint
# ===========================================================
# Orijinal ejabberd entrypoint'ini çalıştırır, ardından
# lider_sunucu kullanıcısını otomatik kaydeder.
set -e

EJABBERDCTL="/home/ejabberd/bin/ejabberdctl"
XMPP_DOMAIN="${XMPP_DOMAIN:-liderahenk.org}"
XMPP_ADMIN_USER="${XMPP_ADMIN_USER:-lider_sunucu}"
XMPP_ADMIN_PASS="${XMPP_ADMIN_PASS:-secret}"

echo "[ejabberd-init] Orijinal entrypoint başlatılıyor..."

# Orijinal entrypoint'i background'da başlat
/home/ejabberd/bin/ejabberdctl foreground &
EJABBERD_PID=$!

# ejabberd'in hazır olmasını bekle
echo "[ejabberd-init] ejabberd hazır olması bekleniyor..."
RETRIES=0
MAX_RETRIES=60
while [ $RETRIES -lt $MAX_RETRIES ]; do
  if $EJABBERDCTL status > /dev/null 2>&1; then
    echo "[ejabberd-init] ejabberd hazır!"
    break
  fi
  RETRIES=$((RETRIES + 1))
  sleep 2
done

if [ $RETRIES -ge $MAX_RETRIES ]; then
  echo "[ejabberd-init] ❌ ejabberd ${MAX_RETRIES}x2s içinde hazır olmadı!"
  exit 1
fi

# lider_sunucu kullanıcısını kaydet (idempotent)
echo "[ejabberd-init] ${XMPP_ADMIN_USER}@${XMPP_DOMAIN} kaydediliyor..."
if $EJABBERDCTL register "$XMPP_ADMIN_USER" "$XMPP_DOMAIN" "$XMPP_ADMIN_PASS" 2>&1; then
  echo "[ejabberd-init] ✅ ${XMPP_ADMIN_USER} başarıyla kaydedildi"
else
  # "already registered" hatası beklenen bir durum
  echo "[ejabberd-init] ℹ️  ${XMPP_ADMIN_USER} zaten kayıtlı (veya hata)"
fi

# Kayıt doğrulama
if $EJABBERDCTL check_account "$XMPP_ADMIN_USER" "$XMPP_DOMAIN" 2>/dev/null; then
  echo "[ejabberd-init] ✅ ${XMPP_ADMIN_USER}@${XMPP_DOMAIN} doğrulandı"
else
  echo "[ejabberd-init] ⚠️  ${XMPP_ADMIN_USER} doğrulanamadı — log kontrol edin"
fi

# Virtual host kontrolü
echo "[ejabberd-init] Kayıtlı vhost'lar:"
$EJABBERDCTL registered_vhosts 2>/dev/null || true

echo "[ejabberd-init] 🚀 ejabberd çalışıyor (PID: ${EJABBERD_PID})"

# Foreground'a dön — ejabberd process'i bekle
wait $EJABBERD_PID
