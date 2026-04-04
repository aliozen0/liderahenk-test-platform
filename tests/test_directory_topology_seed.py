from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROVISIONER_PATH = Path("services/provisioner/provision.py")


def _load_provisioner(monkeypatch, **env_overrides):
    monkeypatch.setenv("AHENK_COUNT", "10")
    monkeypatch.setenv("XMPP_DOMAIN", "liderahenk.org")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=liderahenk,dc=org")
    monkeypatch.setenv("LDAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("LDAP_ADMIN_PASSWORD", "DEGISTIR")
    monkeypatch.setenv("LDAP_AGENT_BASE_DN", "ou=Ahenkler,dc=liderahenk,dc=org")
    monkeypatch.setenv("LDAP_USER_BASE_DN", "ou=users,dc=liderahenk,dc=org")
    monkeypatch.setenv("LDAP_ROLE_BASE_DN", "ou=Roles,dc=liderahenk,dc=org")
    monkeypatch.setenv("LIDER_ADMIN_UID", "lider-admin")
    monkeypatch.setenv("LIDER_ADMIN_PASS", "secret")

    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    module_name = "services.provisioner.provision_seed_test_instance"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, PROVISIONER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_operator_seed_keeps_primary_admin_and_named_operators(monkeypatch):
    provisioner = _load_provisioner(monkeypatch, OPERATOR_COUNT="3")

    operators = provisioner._operator_specs()

    assert [operator["uid"] for operator in operators] == [
        "lider-admin",
        "ops-operator",
        "policy-operator",
    ]
    assert operators[0]["dn"] == "uid=lider-admin,ou=users,dc=liderahenk,dc=org"


def test_directory_user_seed_uses_topology_count(monkeypatch):
    provisioner = _load_provisioner(monkeypatch, DIRECTORY_USER_COUNT="6")

    users = provisioner._directory_user_specs()

    assert len(users) == 6
    assert [user["uid"] for user in users[:4]] == [
        "user-standard-001",
        "user-privileged-001",
        "user-restricted-001",
        "user-shared-001",
    ]
    assert users[4]["uid"] == "user-standard-002"


def test_user_group_seed_distributes_directory_users_round_robin(monkeypatch):
    provisioner = _load_provisioner(
        monkeypatch,
        OPERATOR_COUNT="2",
        DIRECTORY_USER_COUNT="5",
        USER_GROUP_COUNT="3",
    )

    groups = provisioner._user_group_specs(
        provisioner._directory_user_specs(),
        provisioner._operator_specs(),
    )

    assert [group["cn"] for group in groups] == ["ug-standard", "ug-privileged", "ug-restricted"]
    assert groups[0]["member"] == [
        "uid=user-standard-001,ou=users,dc=liderahenk,dc=org",
        "uid=user-shared-001,ou=users,dc=liderahenk,dc=org",
    ]
    assert groups[1]["member"] == [
        "uid=user-privileged-001,ou=users,dc=liderahenk,dc=org",
        "uid=user-standard-002,ou=users,dc=liderahenk,dc=org",
    ]
    assert groups[2]["member"] == ["uid=user-restricted-001,ou=users,dc=liderahenk,dc=org"]
    assert all("liderGroupType" not in group for group in groups)


def test_endpoint_group_seed_uses_registered_agent_dns(monkeypatch):
    provisioner = _load_provisioner(monkeypatch, ENDPOINT_GROUP_COUNT="3")

    groups = provisioner._endpoint_group_specs()

    assert [group["cn"] for group in groups] == ["eg-standard", "eg-restricted", "eg-privileged"]
    assert groups[0]["dn"] == "cn=eg-standard,ou=AgentGroups,dc=liderahenk,dc=org"
    assert groups[0]["member"] == [
        "cn=ahenk-001,ou=Ahenkler,dc=liderahenk,dc=org",
        "cn=ahenk-004,ou=Ahenkler,dc=liderahenk,dc=org",
        "cn=ahenk-007,ou=Ahenkler,dc=liderahenk,dc=org",
        "cn=ahenk-010,ou=Ahenkler,dc=liderahenk,dc=org",
    ]
    assert groups[1]["member"][0] == "cn=ahenk-002,ou=Ahenkler,dc=liderahenk,dc=org"
    assert groups[2]["objectClass"] == ["groupOfNames", "pardusDeviceGroup", "top"]


def test_agent_group_root_is_separated_from_user_group_root(monkeypatch):
    provisioner = _load_provisioner(monkeypatch)

    assert provisioner.GROUPS_OU_DN == "ou=Groups,dc=liderahenk,dc=org"
    assert provisioner.AGENT_GROUPS_OU_DN == "ou=AgentGroups,dc=liderahenk,dc=org"
    assert provisioner.LEGACY_AGENT_GROUPS_OU_DN == "ou=Agent,ou=Groups,dc=liderahenk,dc=org"


def test_ensure_group_entry_preserves_lider_privilege_on_create_and_update(monkeypatch):
    provisioner = _load_provisioner(monkeypatch)

    class _FakeConnection:
        def __init__(self):
            self.result = {"result": 0}
            self.add_calls = []
            self.modify_calls = []

        def add(self, dn, attributes):
            self.add_calls.append((dn, attributes))

        def modify(self, dn, changes):
            self.modify_calls.append((dn, changes))
            self.result = {"result": 0}

    spec = {
        "dn": "cn=DomainAdmins,ou=Groups,dc=liderahenk,dc=org",
        "cn": "DomainAdmins",
        "objectClass": ["groupOfNames", "pardusLider", "top"],
        "member": ["uid=lider-admin,ou=users,dc=liderahenk,dc=org"],
        "liderPrivilege": ["ROLE_DOMAIN_ADMIN"],
        "liderGroupType": ["USER"],
    }

    conn = _FakeConnection()
    result = provisioner._ensure_group_entry(conn, spec)
    assert result == "CREATED"
    assert conn.add_calls[0][1]["liderPrivilege"] == ["ROLE_DOMAIN_ADMIN"]
    assert conn.add_calls[0][1]["liderGroupType"] == ["USER"]

    conn = _FakeConnection()
    conn.result = {"result": 68}
    result = provisioner._ensure_group_entry(conn, spec)
    assert result == "UPDATED"
    assert conn.modify_calls[0][1]["liderPrivilege"] == [
        (provisioner.ldap3.MODIFY_REPLACE, ["ROLE_DOMAIN_ADMIN"])
    ]
    assert conn.modify_calls[0][1]["liderGroupType"] == [
        (provisioner.ldap3.MODIFY_REPLACE, ["USER"])
    ]
