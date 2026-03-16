#!/usr/bin/env python3
# ===========================================================
# Provisioner — İdempotent Toplu Ajan Kaydı + LDAP Şema Yükleme
# ===========================================================
# Bitnamilegacy OpenLDAP (port 1389) + ejabberd HTTP API uyumlu
# 1. LiderAhenk LDAP şemasını yükle (pardusAccount, pardusLider)
# 2. lider-admin kullanıcısını oluştur (JWT auth için)
# 3. AHENK_COUNT kadar ajan için LDAP + XMPP kaydı yap

import os
import sys
import time
import subprocess
import hashlib
import base64
import ldap3
import requests

# --- Yapılandırma ---
N            = int(os.environ["AHENK_COUNT"])
XMPP_DOMAIN  = os.environ["XMPP_DOMAIN"]              # liderahenk.org
EJABBERD_API = os.environ.get("EJABBERD_API", "http://ejabberd:5280/api")
XMPP_PASS    = os.environ.get("XMPP_AGENT_PASS") or os.environ.get("XMPP_ADMIN_PASS", "secret")

# bitnamilegacy: port 1389 (non-root default)
LDAP_HOST    = os.environ.get("LDAP_HOST", "ldap")
LDAP_PORT    = int(os.environ.get("LDAP_PORT", "1389"))
BASE_DN      = os.environ["LDAP_BASE_DN"]
ADMIN_USER   = os.environ["LDAP_ADMIN_USERNAME"]
ADMIN_DN     = f"cn={ADMIN_USER},{BASE_DN}"
ADMIN_PASS   = os.environ["LDAP_ADMIN_PASSWORD"]

AHENK_OU_DN  = os.environ.get("LDAP_AGENT_BASE_DN", f"ou=Ahenkler,{BASE_DN}")
USERS_OU_DN = os.environ.get("LDAP_USER_BASE_DN", f"ou=users,{BASE_DN}")
ROLES_OU_DN = os.environ.get("LDAP_ROLE_BASE_DN", f"ou=Roles,{BASE_DN}")
GROUPS_OU_DN = f"ou=Groups,{BASE_DN}"
AGENT_GROUPS_OU_DN = f"ou=Agent,{GROUPS_OU_DN}"

MAX_RETRIES  = 30
RETRY_WAIT   = 5

# --- LiderAhenk LDAP Şeması ---
# Kaynak: https://github.com/Pardus-LiderAhenk/lider-ahenk-installer/blob/master/src/conf/liderahenk.ldif
LIDERAHENK_SCHEMA_DN = "cn=liderahenk,cn=schema,cn=config"
LIDERAHENK_SCHEMA_ATTRS = {
    "objectClass": ["olcSchemaConfig"],
    "cn": "liderahenk",
    "olcAttributeTypes": [
        "( 2.4.2.42.1.9.7.9.0.9.7.2 NAME 'liderServiceAddress' SUP description SINGLE-VALUE )",
        "( 2.4.2.42.1.9.7.9.0.9.7.1 NAME 'liderPrivilege' SUP description )",
        "( 2.4.2.42.1.9.7.9.0.9.7.3 NAME 'liderDeviceObjectClassName' SUP objectClass SINGLE-VALUE )",
        "( 2.4.2.42.1.9.7.9.0.9.7.4 NAME 'liderUserObjectClassName' SUP objectClass SINGLE-VALUE )",
        "( 2.4.2.42.1.9.7.9.0.9.7.5 NAME 'liderUserIdentityAttributeName' SUP description SINGLE-VALUE )",
        "( 2.4.2.42.1.9.7.9.0.9.7.6 NAME 'liderAhenkOwnerAttributeName' SUP description SINGLE-VALUE )",
        "( 2.4.2.42.1.9.7.9.0.9.7.7 NAME 'liderDeviceOSType' SUP description )",
        "( 2.4.2.42.1.9.7.9.0.9.7.8 NAME 'liderGroupType' SUP description )",
        # sudo şeması — example-registration plugin sudoUser/sudoHost ile yetkilendirme yapar
        "( 1.3.6.1.4.1.15953.9.1.1 NAME 'sudoUser' SUP name )",
        "( 1.3.6.1.4.1.15953.9.1.2 NAME 'sudoHost' SUP name )",
        "( 1.3.6.1.4.1.15953.9.1.3 NAME 'sudoCommand' SUP name )",
        "( 1.3.6.1.4.1.15953.9.1.4 NAME 'sudoRunAs' SUP name )",
        "( 1.3.6.1.4.1.15953.9.1.6 NAME 'sudoOption' SUP name )",
    ],
    "olcObjectClasses": [
        "( 2.4.2.42.1.9.7.8.1.1.6.1 NAME 'pardusLiderAhenkConfig' STRUCTURAL MUST ( liderServiceAddress $ cn ) MAY ( liderAhenkOwnerAttributeName $ liderDeviceObjectClassName $ liderUserIdentityAttributeName $ liderUserObjectClassName ) )",
        "( 2.4.2.42.1.9.7.8.1.1.6.4 NAME 'pardusAccount' AUXILIARY MUST ( uid $ userPassword ) )",
        "( 2.4.2.42.1.9.7.8.1.1.6.3 NAME 'pardusDevice' AUXILIARY MUST ( cn $ uid $ userPassword $ owner ) MAY (liderDeviceOSType) )",
        "( 2.4.2.42.1.9.7.8.1.1.6.2 NAME 'pardusLider' AUXILIARY MAY ( liderPrivilege $ liderGroupType ) )",
        "( 2.4.2.42.1.9.7.8.1.1.6.5 NAME 'pardusDeviceGroup' AUXILIARY MAY ( liderGroupType ) )",
        # sudo şeması
        "( 1.3.6.1.4.1.15953.9.2.1 NAME 'sudoRole' SUP top STRUCTURAL MUST cn MAY ( sudoUser $ sudoHost $ sudoCommand $ sudoRunAs $ sudoOption $ description ) )",
    ],
}

# Admin kullanıcısı — JWT auth için
LIDER_ADMIN_UID = os.environ.get("LIDER_ADMIN_UID", "lider-admin")
LIDER_ADMIN_PASS = os.environ.get("LIDER_ADMIN_PASS", "secret")


def _user_dn(uid: str) -> str:
    return f"uid={uid},{USERS_OU_DN}"


def _role_dn(cn: str) -> str:
    return f"cn={cn},{ROLES_OU_DN}"


def _group_dn(cn: str) -> str:
    return f"cn={cn},{GROUPS_OU_DN}"


def _agent_owner_dn() -> str:
    return _user_dn(LIDER_ADMIN_UID)


def _ssha_hash(password: str) -> str:
    salt = os.urandom(8)
    sha1_digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(sha1_digest + salt).decode("ascii")


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


def load_ldap_schema():
    """LiderAhenk LDAP şemasını yükle (idempotent).
    cn=config backend'ine bağlanarak şemayı ekler.
    Zaten varsa SKIP."""
    print("[provisioner] LiderAhenk LDAP şeması yükleniyor...")

    # cn=config'e EXTERNAL auth veya admin ile bağlan
    # bitnamilegacy: slapd.d config backend, ldapi socket yok ama
    # LDAP_PORT üzerinden cn=config erişimi admin DN ile mümkün olabilir
    try:
        # Yöntem 1: LDAP admin ile cn=config'e doğrudan ekleme dene
        server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.ALL)
        conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS,
                                auto_bind=True)

        # Şema zaten var mı kontrol et
        conn.search("cn=schema,cn=config", "(cn=liderahenk)",
                     search_scope=ldap3.LEVEL, attributes=["cn"])
        if len(conn.entries) > 0:
            print("[provisioner] ℹ️  LiderAhenk şeması zaten yüklü — SKIP")
            conn.unbind()
            return True

        # Şemayı ekle
        conn.add(LIDERAHENK_SCHEMA_DN, attributes=LIDERAHENK_SCHEMA_ATTRS)
        if conn.result["result"] == 0:
            print("[provisioner] ✅ LiderAhenk şeması yüklendi")
            conn.unbind()
            return True
        elif conn.result["result"] == 68:  # already exists
            print("[provisioner] ℹ️  LiderAhenk şeması zaten yüklü — SKIP")
            conn.unbind()
            return True
        else:
            print(f"[provisioner] ⚠️  Şema yükleme sonucu: {conn.result}")
            conn.unbind()

    except Exception as e:
        print(f"[provisioner] ⚠️  Yöntem 1 başarısız: {e}")

    # Yöntem 2: ldapadd komutu ile dene (container içinde)
    try:
        print("[provisioner] Yöntem 2: ldapadd ile şema yükleme deneniyor...")
        schema_ldif = """dn: cn=liderahenk,cn=schema,cn=config
objectClass: olcSchemaConfig
cn: liderahenk
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.2 NAME 'liderServiceAddress' SUP description SINGLE-VALUE )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.1 NAME 'liderPrivilege' SUP description )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.3 NAME 'liderDeviceObjectClassName' SUP objectClass SINGLE-VALUE )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.4 NAME 'liderUserObjectClassName' SUP objectClass SINGLE-VALUE )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.5 NAME 'liderUserIdentityAttributeName' SUP description SINGLE-VALUE )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.6 NAME 'liderAhenkOwnerAttributeName' SUP description SINGLE-VALUE )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.7 NAME 'liderDeviceOSType' SUP description )
olcAttributeTypes: ( 2.4.2.42.1.9.7.9.0.9.7.8 NAME 'liderGroupType' SUP description )
olcObjectClasses: ( 2.4.2.42.1.9.7.8.1.1.6.1 NAME 'pardusLiderAhenkConfig' STRUCTURAL MUST ( liderServiceAddress $ cn ) MAY ( liderAhenkOwnerAttributeName $ liderDeviceObjectClassName $ liderUserIdentityAttributeName $ liderUserObjectClassName ) )
olcObjectClasses: ( 2.4.2.42.1.9.7.8.1.1.6.4 NAME 'pardusAccount' AUXILIARY MUST ( uid $ userPassword ) )
olcObjectClasses: ( 2.4.2.42.1.9.7.8.1.1.6.3 NAME 'pardusDevice' AUXILIARY MUST ( cn $ uid $ userPassword $ owner ) MAY (liderDeviceOSType) )
olcObjectClasses: ( 2.4.2.42.1.9.7.8.1.1.6.2 NAME 'pardusLider' AUXILIARY MAY ( liderPrivilege $ liderGroupType ) )
"""
        # Schema LDIF'i dosyaya yaz
        with open("/tmp/liderahenk_schema.ldif", "w") as f:
            f.write(schema_ldif)

        # ldapadd çalıştır — provisioner container içinde
        result = subprocess.run(
            ["ldapadd", "-x", "-H", f"ldap://{LDAP_HOST}:{LDAP_PORT}",
             "-D", ADMIN_DN, "-w", ADMIN_PASS,
             "-f", "/tmp/liderahenk_schema.ldif"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print("[provisioner] ✅ LiderAhenk şeması yüklendi (ldapadd)")
            return True
        elif "Already exists" in result.stderr:
            print("[provisioner] ℹ️  LiderAhenk şeması zaten yüklü — SKIP")
            return True
        else:
            print(f"[provisioner] ⚠️  ldapadd hatası: {result.stderr}")

    except FileNotFoundError:
        print("[provisioner] ℹ️  ldapadd komutu mevcut değil — atlanıyor")
    except Exception as e:
        print(f"[provisioner] ⚠️  Yöntem 2 başarısız: {e}")

    print("[provisioner] ⚠️  Şema yüklenemedi — volume temizleyip tekrar deneyin: make clean && make dev")
    return False


def create_lider_admin_user():
    """liderapi JWT auth için admin kullanıcısı oluştur (idempotent).
    pardusAccount + pardusLider objectClass gerekli.
    Şifre SSHA formatında hash'lenir — OpenLDAP bind uyumlu."""
    admin_dn = _user_dn(LIDER_ADMIN_UID)
    print(f"[provisioner] Admin kullanıcısı oluşturuluyor: {admin_dn}")

    # SSHA hash oluşturma (OpenLDAP bind uyumlu)
    try:
        ssha_hash = _ssha_hash(LIDER_ADMIN_PASS)
    except Exception as e:
        print(f"[provisioner] ⚠️  Şifre hash'leme hatası: {e}")
        return False

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.ALL)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        attrs = {
            "objectClass": ["inetOrgPerson", "organizationalPerson",
                            "person", "pardusAccount", "pardusLider", "top"],
            "uid": LIDER_ADMIN_UID,
            "cn": "Lider Admin",
            "sn": "Admin",
            "userPassword": ssha_hash,
            "mail": "admin@liderahenk.org",
            "liderPrivilege": ["ROLE_ADMIN", "ROLE_USER"],
        }
        conn.add(admin_dn, attributes=attrs)
        if conn.result["result"] == 0:
            print(f"[provisioner] ✅ Admin kullanıcısı oluşturuldu: {LIDER_ADMIN_UID}")
            return True
        elif conn.result["result"] == 68:  # entryAlreadyExists
            print(f"[provisioner] ℹ️  Admin kullanıcısı zaten mevcut — SKIP")
            return True
        elif conn.result["result"] == 17:  # undefinedAttributeType
            print(f"[provisioner] ⚠️  pardusAccount/pardusLider objectClass tanımsız — şema yüklenmedi mi?")
            print(f"[provisioner]     Hata: {conn.result}")
            return False
        else:
            print(f"[provisioner] ⚠️  Admin oluşturma hatası: {conn.result}")
            return False
    finally:
        conn.unbind()


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


def ensure_user_tree():
    """Kanonik kullanıcı subtree'sini oluştur."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        conn.add(USERS_OU_DN, "organizationalUnit", {"ou": "users"})
        if conn.result["result"] == 0:
            print(f"[provisioner] ✅ OU oluşturuldu: {USERS_OU_DN}")
        elif conn.result["result"] == 68:
            print(f"[provisioner] ℹ️  OU zaten mevcut: {USERS_OU_DN}")
        else:
            print(f"[provisioner] ⚠️  OU oluşturma sonucu: {conn.result}")
    finally:
        conn.unbind()


def ensure_roles_ou():
    """ou=Roles OU'sunu ve liderahenk rol grubunu oluştur.
    example-registration plugin'i CSV'deki group sütununa göre
    bu OU altında rol grubu arar."""
    role_group_dn = _role_dn("liderahenk")
    admin_group_dn = _group_dn("DomainAdmins")

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        # 1. ou=Roles oluştur
        conn.add(ROLES_OU_DN, "organizationalUnit", {"ou": "Roles"})
        if conn.result["result"] == 0:
            print(f"[provisioner] ✅ OU oluşturuldu: {ROLES_OU_DN}")
        elif conn.result["result"] == 68:
            print(f"[provisioner] ℹ️  OU zaten mevcut: {ROLES_OU_DN}")
        else:
            print(f"[provisioner] ⚠️  OU oluşturma sonucu: {conn.result}")

        # 2. liderahenk rol grubu oluştur
        # Registration yetkilendirmesi agent identity (istemci) uzerinden izlenir.
        sudo_users = [f"ahenk-{i:03d}" for i in range(1, N + 1)]
        sudo_hosts = [f"ahenk-{i:03d}-host" for i in range(1, N + 1)]

        attrs = {
            "objectClass": ["sudoRole", "top"],
            "cn": "liderahenk",
            "description": "LiderAhenk test agent role group",
            "sudoUser": sudo_users,
            "sudoHost": sudo_hosts,
            "sudoCommand": ["ALL"],
        }
        conn.add(role_group_dn, attributes=attrs)
        if conn.result["result"] == 0:
            print(f"[provisioner] ✅ Rol grubu oluşturuldu: {role_group_dn} ({len(sudo_users)} üye)")
        elif conn.result["result"] == 68:
            print(f"[provisioner] ℹ️  Rol grubu zaten mevcut: {role_group_dn}")
        else:
            raise RuntimeError(f"Rol grubu oluşturma hatası: {conn.result}")

        # 3. Domain admin yetkisi user-group root altinda tutulur.
        admin_member_dn = _user_dn(LIDER_ADMIN_UID)
        attrs_admin = {
            "objectClass": ["groupOfNames", "pardusLider", "top"],
            "cn": "DomainAdmins",
            "member": [admin_member_dn],
            "liderPrivilege": ["ROLE_DOMAIN_ADMIN"],
            "liderGroupType": ["USER"],
        }
        conn.add(admin_group_dn, attributes=attrs_admin)
        if conn.result["result"] == 0:
            print(f"[provisioner] ✅ Domain Admin rol baglantisi oluşturuldu: {admin_group_dn}")
        elif conn.result["result"] == 68:
            print(f"[provisioner] ℹ️  Domain Admin rol baglantisi zaten mevcut: {admin_group_dn}")
        else:
            raise RuntimeError(f"Domain Admin rol baglantisi hatası: {conn.result}")

    finally:
        conn.unbind()


def ensure_group_tree():
    """UI computer-group ve policy akışı için gerekli LDAP ağacını oluştur."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        for dn, ou_value in (
            (GROUPS_OU_DN, "Groups"),
            (AGENT_GROUPS_OU_DN, "Agent"),
        ):
            conn.add(dn, "organizationalUnit", {"ou": ou_value})
            if conn.result["result"] == 0:
                print(f"[provisioner] ✅ OU oluşturuldu: {dn}")
            elif conn.result["result"] == 68:
                print(f"[provisioner] ℹ️  OU zaten mevcut: {dn}")
            else:
                print(f"[provisioner] ⚠️  OU oluşturma sonucu: {conn.result}")
    finally:
        conn.unbind()


def register_xmpp_idempotent(username):
    """XMPP kullanıcısı kaydet. 409 → zaten var, SKIP."""
    try:
        resp = requests.post(
            f"{EJABBERD_API}/register",
            json={"user": username, "host": XMPP_DOMAIN, "password": XMPP_PASS},
            timeout=10,
        )
        if resp.status_code == 200:
            return "CREATED"
        elif resp.status_code == 409:
            return "EXISTS"
        else:
            raise RuntimeError(f"XMPP kayıt hatası: {username} → HTTP {resp.status_code}: {resp.text}")
    except requests.RequestException as e:
        raise RuntimeError(f"XMPP kayıt hatası: {username} → {e}")


def register_ldap_idempotent(index):
    """LDAP pardusDevice+device kaydı oluştur. entryAlreadyExists → SKIP."""
    cn = f"ahenk-{index:03d}"
    dn = f"cn={cn},{AHENK_OU_DN}"
    agent_id = cn  # ahenk-001, ahenk-002, ...

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        attrs = {
            "objectClass": ["pardusDevice", "device"],
            "cn": cn,
            "uid": agent_id,
            "userPassword": XMPP_PASS,
            "owner": _agent_owner_dn(),
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
    """LDAP'ta tam olarak N kayıt var mı doğrula."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        conn.search(AHENK_OU_DN, "(objectClass=device)", search_scope=ldap3.SUBTREE)
        count = len(conn.entries)
        print(f"[provisioner] LDAP doğrulama: {count} kayıt bulundu (beklenen: {N})")
        if count != N:
            raise RuntimeError(
                f"Kayıt doğrulama başarısız: actual={count} expected={N}. "
                "Dirty LDAP/XMPP state cleanup or fresh environment is required."
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

    # Not: LDAP şeması ve admin kullanıcısı artık ldap-init servisi tarafından
    # otomatik olarak yönetiliyor (compose.core.yml). Provisioner sadece
    # ajan kaydı yapıyor.

    ensure_user_tree()
    ensure_ou_ahenkler()
    ensure_group_tree()
    ensure_roles_ou()

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
