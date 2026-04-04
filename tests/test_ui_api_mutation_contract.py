from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import quote

import pytest
import requests

from adapters.lider_api_adapter import LiderApiAdapter
from tests.e2e.support.backend_facade import BackendFacade


class _DummyResponse:
    def __init__(self, *, payload=None, status_code: int = 200, text: str | None = None):
        self._payload = payload
        self.status_code = status_code
        if text is None:
            if payload is None:
                text = ""
            else:
                text = json.dumps(payload)
        self.text = text
        self.content = text.encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


def _build_facade(fake_api) -> BackendFacade:
    from tests.e2e.support.policy_workflow import PolicyWorkflow

    facade = BackendFacade.__new__(BackendFacade)
    facade.api_adapter = fake_api
    facade.xmpp_adapter = SimpleNamespace()
    facade._policy_workflow = PolicyWorkflow(facade.api_adapter, facade.xmpp_adapter)
    return facade


def test_create_user_group_posts_expected_official_payload(monkeypatch):
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}

    def fake_post(url, json=None, params=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["params"] = params
        captured["timeout"] = timeout
        return _DummyResponse(payload={"distinguishedName": "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"})

    monkeypatch.setattr(adapter.session, "post", fake_post)

    result = adapter.create_user_group(
        group_name="ug-standard",
        checked_entries=[{"distinguishedName": "uid=user-standard-001,ou=users,dc=liderahenk,dc=org", "type": "USER"}],
        selected_ou_dn="ou=Groups,dc=liderahenk,dc=org",
    )

    assert captured["url"] == "http://liderapi.test/api/lider/user-groups/create-new-group"
    assert captured["json"]["groupName"] == "ug-standard"
    assert captured["json"]["selectedOUDN"] == "ou=Groups,dc=liderahenk,dc=org"
    assert json.loads(captured["json"]["checkedEntries"]) == [
        {"distinguishedName": "uid=user-standard-001,ou=users,dc=liderahenk,dc=org", "type": "USER"}
    ]
    assert result["distinguishedName"] == "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"


def test_create_directory_user_posts_configured_official_payload(monkeypatch):
    monkeypatch.setenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", "/api/lider/user/add-user")
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}

    def fake_post(url, files=None, params=None, timeout=None):
        captured["url"] = url
        captured["files"] = files
        captured["params"] = params
        captured["timeout"] = timeout
        return _DummyResponse(payload={"distinguishedName": "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org"})

    monkeypatch.setattr(adapter.session, "post", fake_post)
    monkeypatch.setattr(
        adapter,
        "get_directory_user_tree",
        lambda: [
            {
                "distinguishedName": "ou=users,dc=liderahenk,dc=org",
                "type": "ORGANIZATIONAL_UNIT",
                "childEntries": [
                    {
                        "distinguishedName": "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org",
                        "uid": "scenario-user-001",
                        "cn": "Scenario User",
                        "type": "USER",
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(
        "platform_runtime.readiness.mutation_evidence.load_ui_mutation_evidence",
        lambda: None,
    )
    monkeypatch.setattr(
        "platform_runtime.readiness.mutation_evidence.write_ui_mutation_evidence",
        lambda payload: captured.setdefault("evidence", payload),
    )

    result = adapter.create_directory_user(
        uid="scenario-user-001",
        common_name="Scenario User",
        surname="User",
        selected_ou_dn="ou=users,dc=liderahenk,dc=org",
        privileges=["ROLE_USER", "ROLE_PROFILE_VIEW"],
    )

    multipart = {key: value[1] for key, value in captured["files"].items()}
    assert captured["url"] == "http://liderapi.test/api/lider/user/add-user"
    assert multipart["parentName"] == "ou=users,dc=liderahenk,dc=org"
    assert multipart["uid"] == "scenario-user-001"
    assert multipart["cn"] == "Scenario User"
    assert multipart["sn"] == "User"
    assert multipart["mail"] == "scenario-user-001@liderahenk.org"
    assert multipart["telephoneNumber"] == "(555) 123-4567"
    assert multipart["homePostalAddress"] == "LiderAhenk UI acceptance flow"
    assert multipart["userPassword"] == "Secret123!"
    assert result["distinguishedName"] == "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org"
    assert result["runtimeVerified"] is True
    assert result["verifiedDn"] == "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org"
    assert captured["evidence"]["verifiedSteps"]["create_user_via_ui"]["runtimeVerified"] is True
    assert captured["evidence"]["verifiedSteps"]["create_user_via_ui"]["mode"] == "ui-first-postcondition"


def test_directory_user_create_capability_reports_disabled_without_env(monkeypatch):
    monkeypatch.delenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", raising=False)
    adapter = LiderApiAdapter("http://liderapi.test")

    capability = adapter.directory_user_create_capability()

    assert capability["capability"] == "create_user_via_ui"
    assert capability["env"] == "LIDER_DIRECTORY_USER_CREATE_ENDPOINT"
    assert capability["endpoint"] is None
    assert capability["configured"] is False
    assert capability["runtimeVerified"] is False
    assert capability["enabled"] is False
    assert capability["status"] == "disabled"
    assert capability["reason"] == "Set LIDER_DIRECTORY_USER_CREATE_ENDPOINT to enable create_user_via_ui."


def test_directory_user_create_capability_can_probe_configured_endpoint(monkeypatch):
    monkeypatch.setenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", "/api/lider/users/create-entry")
    adapter = LiderApiAdapter("http://liderapi.test")

    def fake_options(url, timeout=None):
        assert url == "http://liderapi.test/api/lider/users/create-entry"
        return _DummyResponse(status_code=405, text="")

    monkeypatch.setattr(adapter.session, "options", fake_options)

    capability = adapter.directory_user_create_capability(probe=True)

    assert capability["configured"] is True
    assert capability["runtimeVerified"] is False
    assert capability["enabled"] is False
    assert capability["status"] == "configured"
    assert capability["probe"] == {
        "probed": True,
        "probeMethod": "OPTIONS",
        "serverReachable": True,
        "routeLikelyPresent": True,
        "statusCode": 405,
    }


def test_directory_user_create_capability_promotes_to_runtime_verified_when_evidence_exists(monkeypatch):
    monkeypatch.setenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", "/api/lider/user/add-user")
    monkeypatch.setattr(
        "platform_runtime.readiness.mutation_evidence.load_ui_mutation_evidence",
        lambda: {
            "verifiedSteps": {
                "create_user_via_ui": {
                    "runtimeVerified": True,
                    "mode": "ui-first-postcondition",
                }
            }
        },
    )
    adapter = LiderApiAdapter("http://liderapi.test")

    capability = adapter.directory_user_create_capability()

    assert capability["configured"] is True
    assert capability["runtimeVerified"] is True
    assert capability["enabled"] is True
    assert capability["status"] == "runtime-verified"


def test_user_group_membership_capability_promotes_to_runtime_verified_when_evidence_exists(monkeypatch):
    monkeypatch.setenv("LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT", "/api/lider/user-groups/group-existing")
    monkeypatch.setattr(
        "platform_runtime.readiness.mutation_evidence.load_ui_mutation_evidence",
        lambda: {
            "verifiedSteps": {
                "assign_user_to_group_via_ui": {
                    "runtimeVerified": True,
                    "mode": "existing_group_membership_update",
                }
            }
        },
    )
    adapter = LiderApiAdapter("http://liderapi.test")

    capability = adapter.user_group_membership_update_capability()

    assert capability["configured"] is True
    assert capability["runtimeVerified"] is True
    assert capability["enabled"] is True
    assert capability["status"] == "runtime-verified"


def test_add_directory_entries_to_user_group_posts_configured_membership_payload(monkeypatch):
    monkeypatch.setenv("LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT", "/api/lider/user-groups/group-existing")
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}

    def fake_post(url, json=None, params=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["params"] = params
        captured["timeout"] = timeout
        return _DummyResponse(payload={"distinguishedName": "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"})

    monkeypatch.setattr(adapter.session, "post", fake_post)
    monkeypatch.setattr(
        adapter,
        "get_user_group_tree",
        lambda: [
            {
                "distinguishedName": "ou=groups,dc=liderahenk,dc=org",
                "type": "ORGANIZATIONAL_UNIT",
                "childEntries": [
                    {
                        "distinguishedName": "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org",
                        "cn": "ug-standard",
                        "type": "GROUP",
                        "attributesMultiValues": {
                            "member": [
                                "uid=user-standard-001,ou=users,dc=liderahenk,dc=org",
                            ]
                        },
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(
        "platform_runtime.readiness.mutation_evidence.load_ui_mutation_evidence",
        lambda: None,
    )
    monkeypatch.setattr(
        "platform_runtime.readiness.mutation_evidence.write_ui_mutation_evidence",
        lambda payload: captured.setdefault("evidence", payload),
    )

    result = adapter.add_directory_entries_to_user_group(
        group_dn="cn=ug-standard,ou=Groups,dc=liderahenk,dc=org",
        checked_entries=[{"distinguishedName": "uid=user-standard-001,ou=users,dc=liderahenk,dc=org", "type": "USER"}],
    )

    assert captured["url"] == "http://liderapi.test/api/lider/user-groups/group-existing"
    assert captured["json"]["groupDN"] == "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"
    assert json.loads(captured["json"]["checkedEntries"]) == [
        {"distinguishedName": "uid=user-standard-001,ou=users,dc=liderahenk,dc=org", "type": "USER"}
    ]
    assert result["distinguishedName"] == "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"
    assert result["runtimeVerified"] is True
    assert result["verifiedGroupDn"] == "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"
    assert captured["evidence"]["verifiedSteps"]["assign_user_to_group_via_ui"]["runtimeVerified"] is True
    assert captured["evidence"]["verifiedSteps"]["assign_user_to_group_via_ui"]["mode"] == "existing_group_membership_update"


def test_delete_policy_uses_official_delete_endpoint(monkeypatch):
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}

    def fake_delete(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return _DummyResponse(payload=None, status_code=200, text="")

    monkeypatch.setattr(adapter.session, "delete", fake_delete)

    result = adapter.delete_policy(77)

    assert captured["url"] == "http://liderapi.test/api/policy/delete/id/77"
    assert result == {"statusCode": 200}


def test_delete_profile_uses_official_delete_endpoint(monkeypatch):
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}

    def fake_delete(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return _DummyResponse(payload=None, status_code=200, text="")

    monkeypatch.setattr(adapter.session, "delete", fake_delete)

    result = adapter.delete_profile(41)

    assert captured["url"] == "http://liderapi.test/api/profile/delete/id/41"
    assert result == {"statusCode": 200}


def test_delete_user_group_encodes_dn_for_official_delete_endpoint(monkeypatch):
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}
    group_dn = "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org"

    def fake_delete(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return _DummyResponse(payload=None, status_code=200, text="")

    monkeypatch.setattr(adapter.session, "delete", fake_delete)

    result = adapter.delete_user_group(group_dn)

    assert captured["url"] == f"http://liderapi.test/api/lider/user-groups/delete-entry/dn/{quote(group_dn, safe='')}"
    assert result == {"statusCode": 200}


def test_delete_computer_group_encodes_dn_for_official_delete_endpoint(monkeypatch):
    adapter = LiderApiAdapter("http://liderapi.test")
    captured = {}
    group_dn = "cn=rt-group,ou=AgentGroups,dc=liderahenk,dc=org"

    def fake_delete(url, timeout=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return _DummyResponse(payload=None, status_code=200, text="")

    monkeypatch.setattr(adapter.session, "delete", fake_delete)

    result = adapter.delete_computer_group(group_dn)

    assert captured["url"] == f"http://liderapi.test/api/lider/computer-groups/delete-entry/dn/{quote(group_dn, safe='')}"
    assert result == {"statusCode": 200}


def test_delete_artifact_helpers_tolerate_missing_entries(monkeypatch):
    adapter = LiderApiAdapter("http://liderapi.test")

    def fake_delete(url, timeout=None):
        return _DummyResponse(payload=None, status_code=404, text="")

    monkeypatch.setattr(adapter.session, "delete", fake_delete)

    assert adapter.delete_policy(77) == {"statusCode": 404}
    assert adapter.delete_profile(41) == {"statusCode": 404}
    assert adapter.delete_user_group("cn=missing,ou=Groups,dc=liderahenk,dc=org") == {"statusCode": 404}
    assert adapter.delete_computer_group("cn=missing,ou=AhenkGroups,dc=liderahenk,dc=org") == {"statusCode": 404}


def test_backend_facade_describes_supported_scenario_mutations():
    facade = _build_facade(fake_api=SimpleNamespace())

    support = facade.describe_scenario_mutation_support("ui-user-policy-roundtrip")

    assert support["mutationSteps"] == [
        "create_user_via_ui",
        "create_group_via_ui",
        "assign_user_to_group_via_ui",
        "create_policy_via_ui",
        "assign_policy_to_group_via_ui",
    ]
    assert support["supportedSteps"] == [
        "create_group_via_ui",
        "assign_user_to_group_via_ui",
        "create_policy_via_ui",
        "assign_policy_to_group_via_ui",
    ]
    assert support["unsupportedSteps"] == [
        "create_user_via_ui",
    ]


def test_backend_facade_exposes_lifecycle_capabilities_from_adapter():
    fake_api = SimpleNamespace(
        directory_user_create_capability=lambda probe=False: {
            "capability": "create_user_via_ui",
            "enabled": True,
            "status": "configured",
            "probeRequested": probe,
        },
        user_group_membership_update_capability=lambda probe=False: {
            "capability": "assign_user_to_group_via_ui",
            "enabled": False,
            "status": "disabled",
            "probeRequested": probe,
        },
    )
    facade = _build_facade(fake_api=fake_api)

    capability = facade.describe_lifecycle_capabilities(probe=True)

    assert capability["create_user_via_ui"]["configured"] is True
    assert capability["create_user_via_ui"]["runtimeVerified"] is False
    assert capability["create_user_via_ui"]["enabled"] is False
    assert capability["create_user_via_ui"]["mode"] == "configured-not-verified"
    assert capability["create_user_via_ui"]["probeRequested"] is True
    assert capability["assign_user_to_group_via_ui"]["enabled"] is False
    assert capability["assign_user_to_group_via_ui"]["probeRequested"] is True


def test_backend_facade_keeps_create_user_unsupported_when_api_capability_is_only_configured():
    fake_api = SimpleNamespace(
        directory_user_create_capability=lambda probe=False: {
            "capability": "create_user_via_ui",
            "enabled": True,
            "status": "configured",
        },
    )
    facade = _build_facade(fake_api=fake_api)

    support = facade.describe_scenario_mutation_support("ui-user-policy-roundtrip")

    assert support["supportedSteps"] == [
        "create_group_via_ui",
        "assign_user_to_group_via_ui",
        "create_policy_via_ui",
        "assign_policy_to_group_via_ui",
    ]
    assert support["unsupportedSteps"] == ["create_user_via_ui"]


def test_backend_facade_falls_back_to_legacy_boolean_when_descriptor_shape_is_invalid():
    class _FakeApi:
        def directory_user_create_capability(self, probe=False):
            return {"distinguishedName": "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org"}

        def supports_directory_user_create(self):
            return True

    facade = _build_facade(fake_api=_FakeApi())

    capability = facade.describe_lifecycle_capabilities()

    assert capability["create_user_via_ui"]["enabled"] is True
    assert capability["create_user_via_ui"]["status"] == "legacy-bool"
    assert capability["create_user_via_ui"]["source"] == "supports_directory_user_create"
    assert capability["create_user_via_ui"]["fallbackFrom"] == "directory_user_create_capability"


def test_backend_facade_executes_group_policy_roundtrip_from_scenario():
    calls = []

    class _FakeApi:
        def create_user_group(self, **kwargs):
            calls.append(("create_user_group", kwargs))
            return {}

        def create_script_profile(self, **kwargs):
            calls.append(("create_script_profile", kwargs))
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            calls.append(("create_policy", kwargs))
            return {"id": 77, "label": kwargs["label"]}

        def execute_policy(self, **kwargs):
            calls.append(("execute_policy", kwargs))
            return SimpleNamespace(status_code=200)

        def delete_policy(self, **kwargs):
            calls.append(("delete_policy", kwargs))
            return {"statusCode": 200}

        def delete_profile(self, **kwargs):
            calls.append(("delete_profile", kwargs))
            return {"statusCode": 200}

        def delete_user_group(self, **kwargs):
            calls.append(("delete_user_group", kwargs))
            return {"statusCode": 200}

    facade = _build_facade(fake_api=_FakeApi())

    result = facade.execute_user_group_policy_roundtrip(
        "ui-user-policy-roundtrip",
        group_name="ug-e2e-policy",
    )

    assert [name for name, _ in calls] == [
        "create_user_group",
        "create_script_profile",
        "create_policy",
        "execute_policy",
        "delete_policy",
        "delete_profile",
        "delete_user_group",
    ]
    create_group_kwargs = calls[0][1]
    assert create_group_kwargs["group_name"] == "ug-e2e-policy"
    assert create_group_kwargs["selected_ou_dn"] == "ou=Groups,dc=liderahenk,dc=org"
    assert create_group_kwargs["checked_entries"][0]["distinguishedName"] == (
        "uid=user-standard-001,ou=users,dc=liderahenk,dc=org"
    )
    assert calls[3][1] == {
        "policy_id": 77,
        "dn": "cn=ug-e2e-policy,ou=Groups,dc=liderahenk,dc=org",
    }
    assert calls[-1][1] == {
        "dn": "cn=ug-e2e-policy,ou=Groups,dc=liderahenk,dc=org",
    }
    assert calls[-2][1] == {
        "profile_id": 41,
    }
    assert calls[-3][1] == {
        "policy_id": 77,
    }
    assert result["policyExecutionStatusCode"] == 200
    assert result["cleanup"] == {
        "status": "completed",
        "attempted": [
            {"resource": "policy", "identifier": "77", "method": "delete_policy"},
            {"resource": "profile", "identifier": "41", "method": "delete_profile"},
            {
                "resource": "group",
                "identifier": "cn=ug-e2e-policy,ou=Groups,dc=liderahenk,dc=org",
                "method": "delete_user_group",
            },
        ],
        "failed": [],
    }
    assert set(result["appliedSteps"]) == {
        "assign_user_to_group_via_ui",
        "assign_policy_to_group_via_ui",
        "create_group_via_ui",
        "create_policy_via_ui",
    }


def test_backend_facade_executes_user_create_before_group_roundtrip_when_supported():
    calls = []

    class _FakeApi:
        def supports_directory_user_create(self):
            return True

        def create_directory_user(self, **kwargs):
            calls.append(("create_directory_user", kwargs))
            return {"distinguishedName": f"uid={kwargs['uid']},ou=users,dc=liderahenk,dc=org"}

        def create_user_group(self, **kwargs):
            calls.append(("create_user_group", kwargs))
            return {}

        def create_script_profile(self, **kwargs):
            calls.append(("create_script_profile", kwargs))
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            calls.append(("create_policy", kwargs))
            return {"id": 77, "label": kwargs["label"]}

        def execute_policy(self, **kwargs):
            calls.append(("execute_policy", kwargs))
            return SimpleNamespace(status_code=200)

        def delete_policy(self, **kwargs):
            calls.append(("delete_policy", kwargs))
            return {"statusCode": 200}

        def delete_profile(self, **kwargs):
            calls.append(("delete_profile", kwargs))
            return {"statusCode": 200}

        def delete_user_group(self, **kwargs):
            calls.append(("delete_user_group", kwargs))
            return {"statusCode": 200}

    facade = _build_facade(fake_api=_FakeApi())

    result = facade.execute_user_group_policy_roundtrip(
        "ui-user-policy-roundtrip",
        group_name="ug-e2e-policy",
        create_user_uid="scenario-user-001",
    )

    assert [name for name, _ in calls] == [
        "create_directory_user",
        "create_user_group",
        "create_script_profile",
        "create_policy",
        "execute_policy",
        "delete_policy",
        "delete_profile",
        "delete_user_group",
    ]
    assert calls[0][1]["uid"] == "scenario-user-001"
    assert calls[1][1]["checked_entries"][0]["distinguishedName"] == (
        "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org"
    )
    assert result["activeUserUid"] == "scenario-user-001"
    assert result["createdUser"]["distinguishedName"] == "uid=scenario-user-001,ou=users,dc=liderahenk,dc=org"
    assert result["cleanup"]["status"] == "completed"
    assert set(result["appliedSteps"]) == {
        "assign_user_to_group_via_ui",
        "assign_policy_to_group_via_ui",
        "create_group_via_ui",
        "create_policy_via_ui",
        "create_user_via_ui",
    }


def test_backend_facade_adds_user_to_existing_group_when_membership_capability_exists():
    calls = []

    class _FakeApi:
        def supports_user_group_membership_update(self):
            return True

        def add_directory_entries_to_user_group(self, **kwargs):
            calls.append(("add_directory_entries_to_user_group", kwargs))
            return {"distinguishedName": kwargs["group_dn"]}

        def create_script_profile(self, **kwargs):
            calls.append(("create_script_profile", kwargs))
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            calls.append(("create_policy", kwargs))
            return {"id": 77, "label": kwargs["label"]}

        def execute_policy(self, **kwargs):
            calls.append(("execute_policy", kwargs))
            return SimpleNamespace(status_code=200)

        def delete_policy(self, **kwargs):
            calls.append(("delete_policy", kwargs))
            return {"statusCode": 200}

        def delete_profile(self, **kwargs):
            calls.append(("delete_profile", kwargs))
            return {"statusCode": 200}

    facade = _build_facade(fake_api=_FakeApi())

    result = facade.execute_user_group_policy_roundtrip(
        "ui-user-policy-roundtrip",
        group_name="ug-existing-policy",
        existing_group_dn="cn=ug-existing-policy,ou=Groups,dc=liderahenk,dc=org",
        user_uid="user-standard-002",
    )

    assert [name for name, _ in calls] == [
        "add_directory_entries_to_user_group",
        "create_script_profile",
        "create_policy",
        "execute_policy",
        "delete_policy",
        "delete_profile",
    ]
    assert calls[0][1]["group_dn"] == "cn=ug-existing-policy,ou=Groups,dc=liderahenk,dc=org"
    assert calls[0][1]["checked_entries"][0]["distinguishedName"] == (
        "uid=user-standard-002,ou=users,dc=liderahenk,dc=org"
    )
    assert result["groupDn"] == "cn=ug-existing-policy,ou=Groups,dc=liderahenk,dc=org"
    assert result["cleanup"] == {
        "status": "completed",
        "attempted": [
            {"resource": "policy", "identifier": "77", "method": "delete_policy"},
            {"resource": "profile", "identifier": "41", "method": "delete_profile"},
        ],
        "failed": [],
    }
    assert set(result["appliedSteps"]) == {
        "assign_user_to_group_via_ui",
        "assign_policy_to_group_via_ui",
        "create_policy_via_ui",
    }


def test_backend_facade_falls_back_to_existing_group_when_group_create_returns_417():
    calls = []

    class _FakeApi:
        def create_user_group(self, **kwargs):
            calls.append(("create_user_group", kwargs))
            response = SimpleNamespace(status_code=417)
            raise requests.HTTPError("HTTP 417", response=response)

        def get_user_group_tree(self):
            return [
                {
                    "distinguishedName": "ou=groups,dc=liderahenk,dc=org",
                    "type": "ORGANIZATIONAL_UNIT",
                    "childEntries": [
                        {
                            "distinguishedName": "cn=DomainAdmins,ou=groups,dc=liderahenk,dc=org",
                            "cn": "DomainAdmins",
                            "type": "GROUP",
                        }
                    ],
                }
            ]

        def create_script_profile(self, **kwargs):
            calls.append(("create_script_profile", kwargs))
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            calls.append(("create_policy", kwargs))
            return {"id": 77, "label": kwargs["label"]}

        def execute_policy(self, **kwargs):
            calls.append(("execute_policy", kwargs))
            return SimpleNamespace(status_code=200)

        def delete_policy(self, **kwargs):
            calls.append(("delete_policy", kwargs))
            return {"statusCode": 200}

        def delete_profile(self, **kwargs):
            calls.append(("delete_profile", kwargs))
            return {"statusCode": 200}

    facade = _build_facade(fake_api=_FakeApi())

    result = facade.execute_user_group_policy_roundtrip(
        "ui-user-policy-roundtrip",
        group_name="ug-fallback-policy",
    )

    assert [name for name, _ in calls] == [
        "create_user_group",
        "create_script_profile",
        "create_policy",
        "execute_policy",
        "delete_policy",
        "delete_profile",
    ]
    assert result["executionMode"] == "existing_group_fallback"
    assert result["fallbackReason"] == "create_user_group returned HTTP 417"
    assert result["groupDn"] == "cn=DomainAdmins,ou=groups,dc=liderahenk,dc=org"
    assert result["cleanup"]["status"] == "completed"
    assert set(result["appliedSteps"]) == {
        "assign_policy_to_group_via_ui",
        "create_policy_via_ui",
    }


def test_backend_facade_cleanup_runs_on_policy_creation_failure():
    calls = []

    class _FakeApi:
        def create_user_group(self, **kwargs):
            calls.append(("create_user_group", kwargs))
            return {"distinguishedName": "cn=ug-e2e-policy,ou=Groups,dc=liderahenk,dc=org"}

        def create_script_profile(self, **kwargs):
            calls.append(("create_script_profile", kwargs))
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            calls.append(("create_policy", kwargs))
            raise RuntimeError("policy create failed")

        def delete_profile(self, **kwargs):
            calls.append(("delete_profile", kwargs))
            return {"statusCode": 200}

        def delete_user_group(self, **kwargs):
            calls.append(("delete_user_group", kwargs))
            return {"statusCode": 200}

    facade = _build_facade(fake_api=_FakeApi())

    with pytest.raises(RuntimeError, match="policy create failed"):
        facade.execute_user_group_policy_roundtrip(
            "ui-user-policy-roundtrip",
            group_name="ug-e2e-policy",
        )

    assert [name for name, _ in calls] == [
        "create_user_group",
        "create_script_profile",
        "create_policy",
        "delete_profile",
        "delete_user_group",
    ]
