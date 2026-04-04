#!/usr/bin/env python3
from __future__ import annotations
# ===========================================================
# Provisioner — İdempotent Toplu Ajan Kaydı + LDAP Şema Yükleme
# ===========================================================
# Bitnamilegacy OpenLDAP (port 1389) + ejabberd HTTP API uyumlu
# 1. Topology kaynakli user/group seed'ini uygula
# 2. AHENK_COUNT kadar ajan için LDAP + XMPP kaydı yap
# 3. Endpoint group seed'ini agent kaydindan sonra uygula

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
GROUPS_OU_DN = os.environ.get("LDAP_GROUPS_OU", f"ou=Groups,{BASE_DN}")
AGENT_GROUPS_OU_DN = os.environ.get("LDAP_AGENT_GROUPS_OU", f"ou=AgentGroups,{BASE_DN}")
LEGACY_AGENT_GROUPS_OU_DN = f"ou=Agent,ou=Groups,{BASE_DN}"

MAX_RETRIES  = 30
RETRY_WAIT   = 5

# --- Legacy LiderAhenk LDAP Şeması helper'lari ---
# Not: Ilk dilimde schema/admin root ownership'i ldap-init tarafinda kalir.
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
SEEDED_USER_PASS = os.environ.get("SEEDED_USER_PASSWORD", LIDER_ADMIN_PASS)
TOPOLOGY_PROFILE = os.environ.get("TOPOLOGY_PROFILE", os.environ.get("PLATFORM_RUNTIME_PROFILE", "legacy"))
POLICY_PACK = os.environ.get("POLICY_PACK", "baseline-standard")
SESSION_PACK = os.environ.get("SESSION_PACK", "login-basic")


def _count_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise RuntimeError(f"{name} must be >= 0, got {value}")
    return value


OPERATOR_COUNT = _count_env("OPERATOR_COUNT", 1)
DIRECTORY_USER_COUNT = _count_env("DIRECTORY_USER_COUNT", 0)
USER_GROUP_COUNT = _count_env("USER_GROUP_COUNT", 0)
ENDPOINT_GROUP_COUNT = _count_env("ENDPOINT_GROUP_COUNT", 0)

DIRECTORY_USER_ARCHETYPES = ("standard", "privileged", "restricted", "shared")
USER_GROUP_ARCHETYPES = ("standard", "privileged", "restricted", "shared")
ENDPOINT_GROUP_ARCHETYPES = ("standard", "restricted", "privileged")

DEFAULT_OPERATOR_TEMPLATES = (
    {
        "uid": LIDER_ADMIN_UID,
        "cn": "Lider Admin",
        "sn": "Admin",
        "mail": "admin@liderahenk.org",
        "liderPrivilege": ["ROLE_ADMIN", "ROLE_USER"],
    },
    {
        "uid": "ops-operator",
        "cn": "Ops Operator",
        "sn": "Operator",
        "mail": "ops-operator@liderahenk.org",
        "liderPrivilege": ["ROLE_USER"],
    },
    {
        "uid": "policy-operator",
        "cn": "Policy Operator",
        "sn": "Operator",
        "mail": "policy-operator@liderahenk.org",
        "liderPrivilege": ["ROLE_USER"],
    },
)


def _user_dn(uid: str) -> str:
    return f"uid={uid},{USERS_OU_DN}"


def _role_dn(cn: str) -> str:
    return f"cn={cn},{ROLES_OU_DN}"


def _group_dn(cn: str) -> str:
    return f"cn={cn},{GROUPS_OU_DN}"


def _agent_group_dn(cn: str) -> str:
    return f"cn={cn},{AGENT_GROUPS_OU_DN}"


def _agent_owner_dn() -> str:
    return _user_dn(LIDER_ADMIN_UID)


def _ssha_hash(password: str) -> str:
    salt = os.urandom(8)
    sha1_digest = hashlib.sha1(password.encode("utf-8") + salt).digest()
    return "{SSHA}" + base64.b64encode(sha1_digest + salt).decode("ascii")


def _operator_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for index in range(OPERATOR_COUNT):
        if index < len(DEFAULT_OPERATOR_TEMPLATES):
            spec = dict(DEFAULT_OPERATOR_TEMPLATES[index])
        else:
            sequence = index + 1
            uid = f"operator-{sequence:03d}"
            spec = {
                "uid": uid,
                "cn": f"Operator {sequence:03d}",
                "sn": "Operator",
                "mail": f"{uid}@liderahenk.org",
                "liderPrivilege": ["ROLE_USER"],
            }
        spec["dn"] = _user_dn(str(spec["uid"]))
        specs.append(spec)
    return specs


def _directory_user_specs() -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for index in range(DIRECTORY_USER_COUNT):
        archetype = DIRECTORY_USER_ARCHETYPES[index % len(DIRECTORY_USER_ARCHETYPES)]
        ordinal = index // len(DIRECTORY_USER_ARCHETYPES) + 1
        uid = f"user-{archetype}-{ordinal:03d}"
        specs.append(
            {
                "uid": uid,
                "dn": _user_dn(uid),
                "cn": f"{archetype.title()} User {ordinal:03d}",
                "sn": archetype.title(),
                "mail": f"{uid}@liderahenk.org",
                "liderPrivilege": ["ROLE_USER"],
            }
        )
    return specs


def _user_group_name(index: int) -> str:
    if index < len(USER_GROUP_ARCHETYPES):
        return f"ug-{USER_GROUP_ARCHETYPES[index]}"
    return f"ug-{index + 1:03d}"


def _endpoint_group_name(index: int) -> str:
    if index < len(ENDPOINT_GROUP_ARCHETYPES):
        return f"eg-{ENDPOINT_GROUP_ARCHETYPES[index]}"
    return f"eg-{index + 1:03d}"


def _round_robin_members(member_dns: list[str], bucket_count: int) -> list[list[str]]:
    buckets = [[] for _ in range(bucket_count)]
    if bucket_count <= 0:
        return buckets
    for index, member_dn in enumerate(member_dns):
        buckets[index % bucket_count].append(member_dn)
    return buckets


def _user_group_specs(
    directory_users: list[dict[str, object]],
    operators: list[dict[str, object]],
) -> list[dict[str, object]]:
    if USER_GROUP_COUNT <= 0:
        return []
    default_member = str((operators or [{"dn": _user_dn(LIDER_ADMIN_UID)}])[0]["dn"])
    buckets = _round_robin_members([str(user["dn"]) for user in directory_users], USER_GROUP_COUNT)
    specs: list[dict[str, object]] = []
    for index in range(USER_GROUP_COUNT):
        name = _user_group_name(index)
        specs.append(
            {
                "dn": _group_dn(name),
                "cn": name,
                "objectClass": ["groupOfNames", "top"],
                "member": buckets[index] or [default_member],
            }
        )
    return specs


def _agent_dns() -> list[str]:
    return [f"cn=ahenk-{index:03d},{AHENK_OU_DN}" for index in range(1, N + 1)]


def _endpoint_group_specs() -> list[dict[str, object]]:
    if ENDPOINT_GROUP_COUNT <= 0:
        return []
    buckets = _round_robin_members(_agent_dns(), ENDPOINT_GROUP_COUNT)
    specs: list[dict[str, object]] = []
    for index in range(ENDPOINT_GROUP_COUNT):
        if not buckets[index]:
            continue
        name = _endpoint_group_name(index)
        specs.append(
            {
                "dn": _agent_group_dn(name),
                "cn": name,
                "objectClass": ["groupOfNames", "pardusDeviceGroup", "top"],
                "member": buckets[index],
                "liderGroupType": ["AHENK"],
            }
        )
    return specs


def _ensure_seed_user(conn: ldap3.Connection, spec: dict[str, object], *, password: str) -> str:
    attrs = {
        "objectClass": [
            "inetOrgPerson",
            "organizationalPerson",
            "person",
            "pardusAccount",
            "pardusLider",
            "top",
        ],
        "uid": str(spec["uid"]),
        "cn": str(spec["cn"]),
        "sn": str(spec["sn"]),
        "userPassword": _ssha_hash(password),
        "mail": str(spec["mail"]),
        "liderPrivilege": list(spec.get("liderPrivilege", ["ROLE_USER"])),
    }
    conn.add(str(spec["dn"]), attributes=attrs)
    if conn.result["result"] == 0:
        return "CREATED"
    if conn.result["result"] == 68:
        return "EXISTS"
    raise RuntimeError(f"LDAP seed user failed: {spec['dn']} -> {conn.result}")


def _ensure_group_entry(conn: ldap3.Connection, spec: dict[str, object]) -> str:
    attrs = {
        "objectClass": list(spec["objectClass"]),
        "cn": str(spec["cn"]),
        "member": list(spec["member"]),
    }
    extra_multi_value_attrs: dict[str, list[str]] = {}
    for key, value in spec.items():
        if key in {"dn", "objectClass", "cn", "member"}:
            continue
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            normalized = [str(item) for item in value if item is not None and str(item) != ""]
            if normalized:
                extra_multi_value_attrs[key] = normalized
        else:
            normalized_value = str(value)
            if normalized_value:
                extra_multi_value_attrs[key] = [normalized_value]
    attrs.update(extra_multi_value_attrs)

    conn.add(str(spec["dn"]), attributes=attrs)
    if conn.result["result"] == 0:
        return "CREATED"
    if conn.result["result"] != 68:
        raise RuntimeError(f"LDAP seed group failed: {spec['dn']} -> {conn.result}")

    changes = {"member": [(ldap3.MODIFY_REPLACE, list(spec["member"]))]}
    for key, values in extra_multi_value_attrs.items():
        changes[key] = [(ldap3.MODIFY_REPLACE, values)]
    conn.modify(str(spec["dn"]), changes)
    if conn.result["result"] != 0:
        raise RuntimeError(f"LDAP seed group update failed: {spec['dn']} -> {conn.result}")
    return "UPDATED"


def ensure_seeded_directory_identity():
    operator_specs = _operator_specs()
    directory_user_specs = _directory_user_specs()
    user_group_specs = _user_group_specs(directory_user_specs, operator_specs)

    if not operator_specs and not directory_user_specs and not user_group_specs:
        print("[provisioner] no directory identity seed requested")
        return

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        created_users = 0
        for spec in operator_specs + directory_user_specs:
            result = _ensure_seed_user(conn, spec, password=SEEDED_USER_PASS)
            if result == "CREATED":
                created_users += 1

        created_groups = 0
        updated_groups = 0
        for spec in user_group_specs:
            result = _ensure_group_entry(conn, spec)
            if result == "CREATED":
                created_groups += 1
            elif result == "UPDATED":
                updated_groups += 1

        print(
            "[provisioner] directory seed ready: "
            f"profile={TOPOLOGY_PROFILE}, operators={len(operator_specs)}, "
            f"directory_users={len(directory_user_specs)}, "
            f"user_groups={len(user_group_specs)}, created_users={created_users}, "
            f"created_groups={created_groups}, updated_groups={updated_groups}"
        )
    finally:
        conn.unbind()


def ensure_seeded_endpoint_groups():
    endpoint_group_specs = _endpoint_group_specs()
    if not endpoint_group_specs:
        print("[provisioner] no endpoint-group seed requested")
        return

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        created = 0
        updated = 0
        for spec in endpoint_group_specs:
            result = _ensure_group_entry(conn, spec)
            if result == "CREATED":
                created += 1
            elif result == "UPDATED":
                updated += 1
        print(
            "[provisioner] endpoint-group seed ready: "
            f"profile={TOPOLOGY_PROFILE}, endpoint_groups={len(endpoint_group_specs)}, "
            f"created={created}, updated={updated}, policy_pack={POLICY_PACK}, session_pack={SESSION_PACK}"
        )
    finally:
        conn.unbind()


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


def _require_base_entry(conn: ldap3.Connection, dn: str, label: str) -> None:
    found = conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE, attributes=["dn"])
    if not found or not conn.entries:
        raise RuntimeError(
            f"[provisioner] gerekli LDAP root eksik: {label} -> {dn}. "
            "Bu root ldap-init tarafinda olusturulmalidir."
        )


def ensure_ou_ahenkler():
    """Agent root ownership'i ldap-init'tedir; provisioner yalnizca varligini dogrular."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        _require_base_entry(conn, AHENK_OU_DN, "agent-root")
        print(f"[provisioner] ✅ agent root hazir: {AHENK_OU_DN}")
    finally:
        conn.unbind()


def ensure_user_tree():
    """User root ownership'i ldap-init'tedir; provisioner yalnizca varligini dogrular."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        _require_base_entry(conn, USERS_OU_DN, "user-root")
        print(f"[provisioner] ✅ user root hazir: {USERS_OU_DN}")
    finally:
        conn.unbind()


def ensure_roles_ou():
    """Role root ldap-init tarafinda bulunur; provisioner topology role binding'lerini seed eder.
    example-registration plugin'i CSV'deki group sütununa göre
    bu OU altında rol grubu arar."""
    role_group_dn = _role_dn("liderahenk")
    admin_group_dn = _group_dn("DomainAdmins")

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        _require_base_entry(conn, ROLES_OU_DN, "role-root")
        _require_base_entry(conn, GROUPS_OU_DN, "user-group-root")

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
        admin_member_dns = [str(spec["dn"]) for spec in _operator_specs()] or [_user_dn(LIDER_ADMIN_UID)]
        attrs_admin = {
            "objectClass": ["groupOfNames", "pardusLider", "top"],
            "cn": "DomainAdmins",
            "member": admin_member_dns,
            "liderPrivilege": ["ROLE_DOMAIN_ADMIN"],
            "liderGroupType": ["USER"],
        }
        result = _ensure_group_entry(conn, {"dn": admin_group_dn, **attrs_admin})
        if result == "CREATED":
            print(f"[provisioner] ✅ Domain Admin rol baglantisi oluşturuldu: {admin_group_dn}")
        elif result == "UPDATED":
            print(f"[provisioner] ✅ Domain Admin rol baglantisi guncellendi: {admin_group_dn}")
        else:
            print(f"[provisioner] ℹ️  Domain Admin rol baglantisi zaten mevcut: {admin_group_dn}")

    finally:
        conn.unbind()


def ensure_group_tree():
    """Group root ownership'i ldap-init'tedir; provisioner yalnizca varligini dogrular."""
    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        _require_base_entry(conn, GROUPS_OU_DN, "user-group-root")
        _require_base_entry(conn, AGENT_GROUPS_OU_DN, "agent-group-root")
        print(f"[provisioner] ✅ group roots hazir: {GROUPS_OU_DN}, {AGENT_GROUPS_OU_DN}")
    finally:
        conn.unbind()


def _entry_exists(conn: ldap3.Connection, dn: str) -> bool:
    found = conn.search(dn, "(objectClass=*)", search_scope=ldap3.BASE, attributes=["dn"])
    return bool(found and conn.entries)


def migrate_legacy_agent_group_root():
    if LEGACY_AGENT_GROUPS_OU_DN == AGENT_GROUPS_OU_DN:
        return

    server = ldap3.Server(LDAP_HOST, port=LDAP_PORT, get_info=ldap3.NONE)
    conn = ldap3.Connection(server, user=ADMIN_DN, password=ADMIN_PASS, auto_bind=True)
    try:
        if not _entry_exists(conn, LEGACY_AGENT_GROUPS_OU_DN):
            print(f"[provisioner] ℹ️  legacy agent-group root bulunmadi: {LEGACY_AGENT_GROUPS_OU_DN}")
            return

        conn.search(
            LEGACY_AGENT_GROUPS_OU_DN,
            "(objectClass=*)",
            search_scope=ldap3.LEVEL,
            attributes=["dn"],
        )
        child_dns = [entry.entry_dn for entry in conn.entries]
        moved = 0
        deleted_duplicates = 0
        failures: list[dict[str, str]] = []

        for child_dn in child_dns:
            rdn = child_dn.split(",", 1)[0]
            target_dn = f"{rdn},{AGENT_GROUPS_OU_DN}"
            if _entry_exists(conn, target_dn):
                conn.delete(child_dn)
                if conn.result["result"] == 0:
                    deleted_duplicates += 1
                else:
                    failures.append(
                        {
                            "dn": child_dn,
                            "action": "delete_legacy_duplicate",
                            "result": str(conn.result),
                        }
                    )
                continue

            conn.modify_dn(child_dn, rdn, new_superior=AGENT_GROUPS_OU_DN, delete_old_rdn=True)
            if conn.result["result"] == 0:
                moved += 1
            else:
                failures.append(
                    {
                        "dn": child_dn,
                        "action": "move_to_agent_group_root",
                        "result": str(conn.result),
                    }
                )

        conn.search(
            LEGACY_AGENT_GROUPS_OU_DN,
            "(objectClass=*)",
            search_scope=ldap3.LEVEL,
            attributes=["dn"],
        )
        if not conn.entries:
            conn.delete(LEGACY_AGENT_GROUPS_OU_DN)
            if conn.result["result"] != 0:
                failures.append(
                    {
                        "dn": LEGACY_AGENT_GROUPS_OU_DN,
                        "action": "delete_legacy_root",
                        "result": str(conn.result),
                    }
                )

        if failures:
            print(
                "[provisioner] ⚠️  legacy agent-group root migration partial: "
                f"moved={moved}, deleted_duplicates={deleted_duplicates}, failures={failures}"
            )
        else:
            print(
                "[provisioner] ✅ legacy agent-group root normalized: "
                f"moved={moved}, deleted_duplicates={deleted_duplicates}"
            )
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

    # Not: LDAP şeması, root OU'lar ve primer admin hesabı ldap-init tarafından
    # yönetilir. Provisioner topology tabanli user/group/endpoint-group seed ile
    # agent registration akisindan sorumludur.

    ensure_user_tree()
    ensure_ou_ahenkler()
    ensure_group_tree()
    ensure_seeded_directory_identity()
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

    ensure_seeded_endpoint_groups()
    migrate_legacy_agent_group_root()

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
