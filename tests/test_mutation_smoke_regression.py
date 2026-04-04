from __future__ import annotations

from types import SimpleNamespace

import pytest
import requests

from tests.e2e.support.backend_facade import BackendFacade


class _SpyApi:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def supports_directory_user_create(self):
        return False

    def __getattr__(self, name: str):
        def _method(**kwargs):
            self.calls.append((name, kwargs))
            if "create" in name and "group" in name:
                group_name = kwargs.get("group_name", "ug-smoke")
                selected_ou_dn = kwargs.get("selected_ou_dn", "ou=Groups,dc=liderahenk,dc=org")
                return {"distinguishedName": f"cn={group_name},{selected_ou_dn}"}
            if "create" in name and "user" in name:
                uid = kwargs.get("uid", "user-smoke-001")
                return {"distinguishedName": f"uid={uid},ou=users,dc=liderahenk,dc=org"}
            if name == "create_script_profile":
                return {"id": 41, "label": kwargs["label"]}
            if name == "create_policy":
                return {"id": 77, "label": kwargs["label"]}
            if name == "execute_policy":
                return SimpleNamespace(status_code=200)
            if name.startswith("delete_"):
                return {"statusCode": 200}
            if "group" in name and ("assign" in name or "member" in name or "add" in name):
                return {"statusCode": 200}
            raise AssertionError(f"Unexpected API call: {name}")

        return _method


def _build_facade(fake_api) -> BackendFacade:
    facade = BackendFacade.__new__(BackendFacade)
    facade.api_adapter = fake_api
    facade.xmpp_adapter = SimpleNamespace()
    return facade


def _roundtrip_executor(facade: BackendFacade):
    for name in (
        "execute_full_user_group_policy_roundtrip",
        "execute_user_group_policy_roundtrip",
    ):
        method = getattr(facade, name, None)
        if callable(method):
            return method
    raise AssertionError("No facade roundtrip executor is available.")


def test_current_user_group_policy_roundtrip_smoke_aligns_support_and_execution():
    fake_api = _SpyApi()
    facade = _build_facade(fake_api)

    support = facade.describe_scenario_mutation_support("ui-user-policy-roundtrip")
    result = _roundtrip_executor(facade)(
        "ui-user-policy-roundtrip",
        group_name="ug-smoke-policy",
    )

    assert set(result["appliedSteps"]) == set(support["supportedSteps"])
    assert result["policyExecutionStatusCode"] == 200
    assert result["cleanup"]["status"] == "completed"
    assert [name for name, _ in fake_api.calls] == [
        "create_user_group",
        "create_script_profile",
        "create_policy",
        "execute_policy",
        "delete_policy",
        "delete_profile",
        "delete_user_group",
    ]


def test_membership_on_group_create_remains_supported_without_user_create_capability():
    fake_api = _SpyApi()
    facade = _build_facade(fake_api)

    support = facade.describe_scenario_mutation_support("ui-user-policy-roundtrip")

    assert "assign_user_to_group_via_ui" in support["supportedSteps"]
    assert "create_user_via_ui" in support["unsupportedSteps"]


def test_full_user_onboarding_roundtrip_turns_green_when_remaining_steps_land():
    fake_api = _SpyApi()
    facade = _build_facade(fake_api)

    support = facade.describe_scenario_mutation_support("ui-user-policy-roundtrip")
    if support["unsupportedSteps"]:
        pytest.skip("Awaiting create_user_via_ui and assign_user_to_group_via_ui support.")

    result = _roundtrip_executor(facade)(
        "ui-user-policy-roundtrip",
        group_name="ug-smoke-onboarding",
    )

    assert set(result["appliedSteps"]) == set(support["mutationSteps"])
    call_names = [name for name, _ in fake_api.calls]
    assert any("create" in name and "user" in name for name in call_names)
    assert any("group" in name and ("assign" in name or "member" in name or "add" in name) for name in call_names)


def test_roundtrip_falls_back_to_existing_group_when_group_creation_is_rejected():
    class _FallbackApi(_SpyApi):
        def create_user_group(self, **kwargs):
            self.calls.append(("create_user_group", kwargs))
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

    fake_api = _FallbackApi()
    facade = _build_facade(fake_api)

    result = _roundtrip_executor(facade)(
        "ui-user-policy-roundtrip",
        group_name="ug-fallback-policy",
    )

    assert result["executionMode"] == "existing_group_fallback"
    assert result["groupDn"] == "cn=DomainAdmins,ou=groups,dc=liderahenk,dc=org"
    assert result["cleanup"]["status"] == "completed"
    assert set(result["appliedSteps"]) == {
        "assign_policy_to_group_via_ui",
        "create_policy_via_ui",
    }
