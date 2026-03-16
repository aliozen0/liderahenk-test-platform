from __future__ import annotations

import os
from dataclasses import dataclass

from adapters.interfaces import (
    AgentInventoryAdapter,
    DirectoryAdapter,
    PolicyDispatchAdapter,
    PresenceAdapter,
    TaskDispatchAdapter,
)
from adapters.ldap_schema_adapter import LdapSchemaAdapter
from adapters.lider_api_adapter import LiderApiAdapter
from adapters.runtime_db_adapter import RuntimeDbAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter


@dataclass(frozen=True)
class PlatformAdapterBundle:
    directory: DirectoryAdapter
    presence: PresenceAdapter
    inventory: AgentInventoryAdapter
    tasks: TaskDispatchAdapter
    policies: PolicyDispatchAdapter
    lider_api: LiderApiAdapter
    runtime_db: RuntimeDbAdapter


def _resolve_host_urls() -> tuple[str, str]:
    api_url = os.environ.get("LIDER_API_HOST_URL", os.environ.get("LIDER_API_URL", "http://localhost:8082"))
    container_context = os.environ.get("PLATFORM_EXECUTION_CONTEXT") == "container"
    if not container_context and "liderapi:8080" in api_url:
        api_url = "http://localhost:8082"

    ejabberd_url = os.environ.get("EJABBERD_API_HOST", os.environ.get("EJABBERD_API_URL", "http://localhost:15280/api"))
    if not container_context and "ejabberd:5280" in ejabberd_url:
        ejabberd_url = "http://localhost:15280/api"
    return api_url, ejabberd_url


def build_platform_bundle() -> PlatformAdapterBundle:
    api_url, ejabberd_url = _resolve_host_urls()

    lider_api = LiderApiAdapter(
        base_url=api_url,
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )
    presence = XmppMessageAdapter(
        api_url=ejabberd_url,
        domain=os.environ.get("XMPP_DOMAIN", "liderahenk.org"),
    )
    directory = LdapSchemaAdapter(
        host=os.environ.get("LDAP_HOST", "localhost"),
        port=int(os.environ.get("LDAP_PORT", "1389")),
        base_dn=os.environ.get("LDAP_BASE_DN", "dc=liderahenk,dc=org"),
        admin_dn=f"cn={os.environ.get('LDAP_ADMIN_USERNAME', 'admin')},{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
        admin_pass=os.environ.get("LDAP_ADMIN_PASSWORD", "DEGISTIR"),
    )

    return PlatformAdapterBundle(
        directory=directory,
        presence=presence,
        inventory=lider_api,
        tasks=lider_api,
        policies=lider_api,
        lider_api=lider_api,
        runtime_db=RuntimeDbAdapter.from_env(),
    )
