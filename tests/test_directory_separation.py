from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROVISIONER_PATH = Path("services/provisioner/provision.py")


def _load_provisioner(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "1")
    monkeypatch.setenv("XMPP_DOMAIN", "liderahenk.org")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=liderahenk,dc=org")
    monkeypatch.setenv("LDAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LDAP_ADMIN_PASSWORD", "DEGISTIR")
    monkeypatch.setenv("LDAP_AGENT_BASE_DN", "ou=Ahenkler,dc=liderahenk,dc=org")
    monkeypatch.setenv("LDAP_USER_BASE_DN", "ou=users,dc=liderahenk,dc=org")
    monkeypatch.setenv("LDAP_ROLE_BASE_DN", "ou=Roles,dc=liderahenk,dc=org")
    monkeypatch.setenv("LIDER_ADMIN_UID", "lider-admin")

    module_name = "services.provisioner.provision_test_instance"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, PROVISIONER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_provisioner_uses_separate_roots_for_user_agent_and_role(monkeypatch):
    provisioner = _load_provisioner(monkeypatch)

    assert provisioner.USERS_OU_DN == "ou=users,dc=liderahenk,dc=org"
    assert provisioner.AHENK_OU_DN == "ou=Ahenkler,dc=liderahenk,dc=org"
    assert provisioner.ROLES_OU_DN == "ou=Roles,dc=liderahenk,dc=org"
    assert len({provisioner.USERS_OU_DN, provisioner.AHENK_OU_DN, provisioner.ROLES_OU_DN}) == 3


def test_provisioner_owner_and_domain_admin_reference_human_user_dn(monkeypatch):
    provisioner = _load_provisioner(monkeypatch)

    assert provisioner._user_dn("lider-admin") == "uid=lider-admin,ou=users,dc=liderahenk,dc=org"
    assert provisioner._agent_owner_dn() == "uid=lider-admin,ou=users,dc=liderahenk,dc=org"
    assert provisioner._group_dn("DomainAdmins") == "cn=DomainAdmins,ou=Groups,dc=liderahenk,dc=org"
    assert provisioner._role_dn("liderahenk") == "cn=liderahenk,ou=Roles,dc=liderahenk,dc=org"
