#!/usr/bin/env python3
# ===========================================================
# Provisioner — İdempotent Toplu Ajan Kaydı
# ===========================================================
# Bitnamilegacy OpenLDAP (port 1389) + ejabberd HTTP API uyumlu
# AHENK_COUNT kadar ajan için LDAP + XMPP kaydı yapar.

import os
import sys
import time
import ldap3
import requests

# --- Yapılandırma ---
N            = int(os.environ["AHENK_COUNT"])
XMPP_DOMAIN  = os.environ["XMPP_DOMAIN"]              # liderahenk.org
EJABBERD_API = os.environ.get("EJABBERD_API", "http://ejabberd:5280/api")
XMPP_PASS    = os.environ.get("XMPP_ADMIN_PASS", "secret")

# bitnamilegacy: port 1389 (non-root default)
LDAP_HOST    = os.environ.get("LDAP_HOST", "ldap")
LDAP_PORT    = int(os.environ.get("LDAP_PORT", "1389"))
BASE_DN      = os.environ["LDAP_BASE_DN"]
ADMIN_DN     = f"cn={os.environ['LDAP_ADMIN_USERNAME']},{BASE_DN}"
ADMIN_PASS   = os.environ["LDAP_ADMIN_PASSWORD"]

AHENK_OU_DN  = f"ou=Ahenkler,{BASE_DN}"

MAX_RETRIES  = 30
RETRY_WAIT   = 5


def wait_for_ldap():
    """LDAP bağlantısını bekle (max 30 deneme, 5sn ara)."""
    print(f"[provisioner] LDAP bekleniyor: {LDAP_HOST}:{LDAP_PORT} ...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
            conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS)
            if conn.bind():
                print(f"[provisioner] ✅ LDAP bağlantısı başarılı (deneme {attempt})")
                conn.unbind()
                return
            else:
                print(f"[provisioner]   Deneme {attempt}/{MAX_RETRIES}: bind başarısız — {conn.result}")
        except Exception as e:
            print(f"[provisioner]   Deneme {attempt}/{MAX_RETRIES}: {e}")
        time.sleep(RETRY_WAIT)
    raise RuntimeError("LDAP zaman aşımı — bağlantı kurulamadı")


def wait_for_ejabberd():
    """ejabberd HTTP API hazır olmasını bekle."""
    print(f"[provisioner] ejabberd API bekleniyor: {EJABBERD_API} ...")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{EJABBERD_API}/registered_users",
                json={"host": XMPP_DOMAIN},
                timeout=5,
            )
            if resp.status_code == 200:
                print(f"[provisioner] ✅ ejabberd API hazır (deneme {attempt})")
                return
            else:
                print(f"[provisioner]   Deneme {attempt}/{MAX_RETRIES}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"[provisioner]   Deneme {attempt}/{MAX_RETRIES}: {e}")
        time.sleep(RETRY_WAIT)
    raise RuntimeError("ejabberd API zaman aşımı — bağlantı kurulamadı")


def ensure_ou_ahenkler():
    """ou=Ahenkler OU'sunu oluştur (yoksa)."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        conn.add(AHENK_OU_DN, "organizationalUnit", {"ou": "Ahenkler"})
        if conn.result["result"] == 0:
            print(f"[provisioner] ✅ OU oluşturuldu: {AHENK_OU_DN}")
        elif conn.result["result"] == 68:  # entryAlreadyExists
            print(f"[provisioner] ℹ️  OU zaten mevcut: {AHENK_OU_DN}")
        else:
            print(f"[provisioner] ⚠️  OU oluşturma sonucu: {conn.result}")
    finally:
        conn.unbind()


def register_xmpp_idempotent(username):
    """XMPP kullanıcısı kaydet. 409 → zaten var, SKIP."""
    try:
        resp = requests.post(
            f"{EJABBERD_API}/register",
            json={
                "user": username,
                "host": XMPP_DOMAIN,
                "password": XMPP_PASS,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            return "CREATED"
        elif resp.status_code == 409:
            return "EXISTS"
        else:
            raise RuntimeError(
                f"XMPP kayıt hatası: {username} → HTTP {resp.status_code}: {resp.text}"
            )
    except requests.RequestException as e:
        raise RuntimeError(f"XMPP kayıt hatası: {username} → {e}")


def register_ldap_idempotent(index):
    """LDAP device kaydı oluştur. entryAlreadyExists → SKIP."""
    cn = f"ahenk-{index:03d}"
    dn = f"cn={cn},{AHENK_OU_DN}"

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        attrs = {
            "objectClass": ["device"],
            "cn": cn,
        }
        conn.add(dn, attributes=attrs)
        if conn.result["result"] == 0:
            return "CREATED"
        elif conn.result["result"] == 68:  # entryAlreadyExists
            return "EXISTS"
        else:
            raise RuntimeError(f"LDAP kayıt hatası: {dn} → {conn.result}")
    finally:
        conn.unbind()


def verify_registrations():
    """LDAP'ta N kayıt var mı doğrula."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        conn.search(AHENK_OU_DN, "(objectClass=device)", search_scope=ldap3.SUBTREE)
        count = len(conn.entries)
        print(f"[provisioner] LDAP doğrulama: {count} kayıt bulundu (beklenen: {N})")
        if count < N:
            raise RuntimeError(
                f"Kayıt doğrulama başarısız: {count}/{N} kayıt"
            )
        return count
    finally:
        conn.unbind()


def main():
    print(f"[provisioner] ========================================")
    print(f"[provisioner] {N} ajan kaydı başlatılıyor...")
    print(f"[provisioner] LDAP: {LDAP_HOST}:{LDAP_PORT}")
    print(f"[provisioner] XMPP: {XMPP_DOMAIN}")
    print(f"[provisioner] ========================================")

    wait_for_ldap()
    wait_for_ejabberd()
    ensure_ou_ahenkler()

    created_xmpp = 0
    created_ldap = 0
    skipped = 0

    for i in range(1, N + 1):
        agent_id = f"ahenk-{i:03d}"

        # XMPP kaydı
        xmpp_result = register_xmpp_idempotent(agent_id)
        if xmpp_result == "CREATED":
            created_xmpp += 1

        # LDAP kaydı
        ldap_result = register_ldap_idempotent(i)
        if ldap_result == "CREATED":
            created_ldap += 1
        elif ldap_result == "EXISTS":
            skipped += 1

        status_icon = "🆕" if xmpp_result == "CREATED" else "✓"
        print(f"  [{status_icon}] {agent_id} — XMPP:{xmpp_result} LDAP:{ldap_result}")

    # Doğrulama
    verify_registrations()

    print(f"[provisioner] ========================================")
    print(f"[provisioner] XMPP: {created_xmpp} yeni, {N - created_xmpp} mevcut")
    print(f"[provisioner] LDAP: {created_ldap} yeni, {skipped} mevcut")
    print(f"[DONE] {N} ajan başarıyla kaydedildi")
    print(f"[provisioner] ========================================")
    sys.exit(0)


if __name__ == "__main__":
    main()
