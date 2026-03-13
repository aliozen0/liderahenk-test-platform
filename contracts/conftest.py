"""
Sözleşme testleri — pytest fixture tanımları.
Tüm adapterlerin ortak yapılandırması.
"""

import os
import sys
import pytest

# Proje kök dizinini PYTHONPATH'e ekle
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from adapters.ldap_schema_adapter import LdapSchemaAdapter

# ── Yapılandırma (env veya varsayılan) ─────────────────────

LIDER_API_URL = os.environ.get("LIDER_API_URL_EXTERNAL") \
             or os.environ.get("LIDER_API_URL",    "http://localhost:8082")
LIDER_USER    = os.environ.get("LIDER_API_USER",    "lider-admin")
LIDER_PASS    = os.environ.get("LIDER_API_PASS",    "secret")
EJABBERD_API  = os.environ.get("EJABBERD_API_URL",  "http://localhost:15280/api")
XMPP_ADMIN    = os.environ.get("XMPP_ADMIN_USER",   "lider_sunucu")
XMPP_PASS     = os.environ.get("XMPP_ADMIN_PASS",   "secret")
XMPP_DOMAIN   = os.environ.get("XMPP_DOMAIN",       "liderahenk.org")
LDAP_HOST     = os.environ.get("LDAP_HOST",          "localhost")
LDAP_PORT     = int(os.environ.get("LDAP_PORT",     "1389"))
LDAP_BASE_DN  = os.environ.get("LDAP_BASE_DN",      "dc=liderahenk,dc=org")
LDAP_ADMIN_DN = f"cn={os.environ.get('LDAP_ADMIN_USERNAME', 'admin')},{LDAP_BASE_DN}"
LDAP_PASS     = os.environ.get("LDAP_ADMIN_PASSWORD", "DEGISTIR")
AHENK_COUNT   = int(os.environ.get("AHENK_COUNT",   "10"))


@pytest.fixture(scope="session")
def lider_api():
    """LiderAPI adapter (auth, başarısız olursa unauthenticated)."""
    return LiderApiAdapter(
        LIDER_API_URL,
        username=LIDER_USER,
        password=LIDER_PASS,
    )


@pytest.fixture(scope="session")
def xmpp():
    """ejabberd HTTP API adapter."""
    return XmppMessageAdapter(
        EJABBERD_API,
        admin_user=XMPP_ADMIN,
        admin_pass=XMPP_PASS,
        domain=XMPP_DOMAIN,
    )


@pytest.fixture(scope="session")
def ldap():
    """LDAP adapter (bitnamilegacy, port 1389)."""
    return LdapSchemaAdapter(
        LDAP_HOST, LDAP_PORT,
        LDAP_BASE_DN, LDAP_ADMIN_DN, LDAP_PASS,
    )


@pytest.fixture(scope="session")
def agent_count():
    """Beklenen ajan sayısı."""
    return AHENK_COUNT
