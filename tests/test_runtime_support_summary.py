from __future__ import annotations

from pathlib import Path

import pytest

import platform_runtime.readiness as readiness_package
import platform_runtime.readiness.mutation_support as mutation_support_module
import platform_runtime.runtime_readiness as runtime_readiness
from platform_runtime.readiness.mutation_evidence import clear_ui_mutation_evidence


@pytest.fixture(autouse=True)
def _clear_runtime_mutation_evidence():
    clear_ui_mutation_evidence()
    yield
    clear_ui_mutation_evidence()


def test_runtime_core_report_includes_support_summary(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")
    monkeypatch.delenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", raising=False)
    monkeypatch.delenv("LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT", raising=False)
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
        lambda profile, expected_agents: ([], {}),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fidelity")

    support = report["support"]
    assert support["topology"]["profile"] == "dev-fidelity"
    assert support["scenarios"]["activeScenarios"] == ["ui-user-policy-roundtrip"]
    assert "create_group_via_ui" in support["mutationSupport"]["supportedDeclaredSteps"]
    assert "assign_user_to_group_via_ui" in support["mutationSupport"]["supportedDeclaredSteps"]
    assert "create_user_via_ui" in support["mutationSupport"]["unsupportedDeclaredSteps"]
    assert "create_user_via_ui" in support["mutationSupport"]["catalogDeclaredSteps"]
    assert support["mutationSupport"]["declaredStepCatalog"]["assign_user_to_group_via_ui"]["mode"] == (
        "membership_on_group_create"
    )
    conditional_mode = support["mutationSupport"]["declaredStepCatalog"]["assign_user_to_group_via_ui"][
        "conditionalModes"
    ][0]
    assert conditional_mode["name"] == "existing_group_membership_update"
    assert conditional_mode["enabled"] is False
    assert conditional_mode["capabilityEnv"] == "LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT"


def test_runtime_core_report_marks_existing_group_membership_mode_when_endpoint_is_configured(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")
    monkeypatch.setenv("LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT", "/api/lider/user-groups/add-member")
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
        lambda profile, expected_agents: ([], {}),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fidelity")

    step_support = report["support"]["mutationSupport"]["declaredStepCatalog"]["assign_user_to_group_via_ui"]
    assert step_support["supported"] is True
    assert step_support["mode"] == "membership_on_group_create"
    assert "configured via LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT" in step_support["note"]
    conditional_mode = step_support["conditionalModes"][0]
    assert conditional_mode["enabled"] is False
    assert conditional_mode["configured"] is True
    assert conditional_mode["runtimeVerified"] is False
    assert conditional_mode["status"] == "configured"
    assert conditional_mode["adapterMethod"] == "add_directory_entries_to_user_group"
    assert conditional_mode["capabilityMethod"] == "supports_user_group_membership_update"


def test_runtime_core_report_keeps_create_user_configured_but_not_supported_until_runtime_verified(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")
    monkeypatch.setenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", "/api/lider/users/create-entry")
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
        lambda profile, expected_agents: ([], {}),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fidelity")

    step_support = report["support"]["mutationSupport"]["declaredStepCatalog"]["create_user_via_ui"]
    assert step_support["supported"] is False
    assert step_support["configured"] is True
    assert step_support["runtimeVerified"] is False
    assert step_support["status"] == "configured"
    assert step_support["mode"] == "configured-not-verified"
    assert step_support["capabilityEnv"] == "LIDER_DIRECTORY_USER_CREATE_ENDPOINT"
    assert "runtime-verified yet" in step_support["note"]


def test_runtime_core_report_promotes_create_user_when_runtime_evidence_exists(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")
    monkeypatch.setenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", "/api/lider/user/add-user")
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
        lambda profile, expected_agents: ([], {}),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [],
    )
    monkeypatch.setattr(
        mutation_support_module,
        "load_ui_mutation_evidence",
        lambda: {
            "verifiedSteps": {
                "create_user_via_ui": {
                    "runtimeVerified": True,
                    "mode": "ui-first-postcondition",
                }
            }
        },
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fidelity")

    step_support = report["support"]["mutationSupport"]["declaredStepCatalog"]["create_user_via_ui"]
    assert step_support["supported"] is True
    assert step_support["runtimeVerified"] is True
    assert step_support["status"] == "runtime-verified"


def test_runtime_core_report_separates_active_steps_from_catalog_when_no_scenario_is_active(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.delenv("PLATFORM_SCENARIO_PACKS", raising=False)
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
        lambda profile, expected_agents: ([], {}),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fidelity")

    mutation_support = report["support"]["mutationSupport"]
    session_support = report["support"]["sessionSupport"]
    assert mutation_support["declaredSteps"] == []
    assert session_support["declaredSteps"] == []
    assert "create_group_via_ui" in mutation_support["catalogDeclaredSteps"]
    assert "verify_effect" in session_support["catalogDeclaredSteps"]


def test_write_runtime_report_renders_support_section(tmp_path):
    report = {
        "schemaVersion": 1,
        "reportType": "runtime-operational",
        "status": "pass",
        "profile": "dev-fidelity",
        "expectedAgents": 10,
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "checks": [],
        "summary": {"totalChecks": 0, "passedChecks": 0, "failedChecks": 0},
        "topology": {"name": "dev-fidelity"},
        "scenarios": {"activeScenarios": ["ui-user-policy-roundtrip"], "scenarios": {}},
        "support": {
            "topology": {"profile": "dev-fidelity"},
            "scenarios": {
                "activeScenarios": ["ui-user-policy-roundtrip"],
                "availableScenarios": ["ui-user-policy-roundtrip", "session-login-basic"],
            },
            "mutationSupport": {
                "supportedDeclaredSteps": [
                    "create_group_via_ui",
                    "assign_user_to_group_via_ui",
                    "create_policy_via_ui",
                ],
                "unsupportedDeclaredSteps": ["create_user_via_ui"],
                "catalogDeclaredSteps": [
                    "create_user_via_ui",
                    "create_group_via_ui",
                    "assign_user_to_group_via_ui",
                    "create_policy_via_ui",
                ],
                "catalogSupportedDeclaredSteps": [
                    "create_group_via_ui",
                    "assign_user_to_group_via_ui",
                    "create_policy_via_ui",
                ],
                "catalogUnsupportedDeclaredSteps": ["create_user_via_ui"],
                "declaredStepCatalog": {
                    "create_user_via_ui": {
                        "supported": False,
                        "mode": "configured-not-verified",
                        "adapterMethod": "create_directory_user",
                        "capabilityEnv": "LIDER_DIRECTORY_USER_CREATE_ENDPOINT",
                        "configured": True,
                        "runtimeVerified": False,
                        "note": "Official directory user create flow is wired but not runtime-verified yet.",
                    },
                    "assign_user_to_group_via_ui": {
                        "supported": True,
                        "mode": "membership_on_group_create",
                        "adapterMethod": "create_user_group",
                        "conditionalModes": [
                            {
                                "name": "existing_group_membership_update",
                                "enabled": False,
                                "configured": True,
                                "capabilityEnv": "LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT",
                            }
                        ],
                        "note": "Initial membership is supported during group creation.",
                    }
                },
                "catalogDeclaredStepCatalog": {
                    "create_user_via_ui": {
                        "supported": False,
                        "mode": "configured-not-verified",
                        "note": "Official directory user create flow is wired but not runtime-verified yet.",
                    }
                },
            },
            "sessionSupport": {
                "supportedDeclaredSteps": [
                    "simulate_login",
                    "collect_membership_snapshot",
                    "verify_effect",
                    "collect_policy_snapshot",
                ],
                "unsupportedDeclaredSteps": [],
                "catalogDeclaredSteps": [
                    "simulate_login",
                    "collect_membership_snapshot",
                    "verify_effect",
                    "collect_policy_snapshot",
                ],
                "catalogSupportedDeclaredSteps": [
                    "simulate_login",
                    "collect_membership_snapshot",
                    "verify_effect",
                    "collect_policy_snapshot",
                ],
                "catalogUnsupportedDeclaredSteps": [],
                "declaredStepCatalog": {
                    "collect_membership_snapshot": {
                        "supported": True,
                        "runtimeCheck": "membership_snapshot_contract",
                        "mode": "user_group_tree_summary",
                        "note": "Membership evidence is collected from user-group tree.",
                    },
                    "verify_effect": {
                        "supported": True,
                        "runtimeCheck": "policy_effect_probe",
                        "mode": "policy_command_history",
                        "note": "Post-login business-effect verification via policy execution.",
                    },
                    "collect_policy_snapshot": {
                        "supported": True,
                        "runtimeCheck": "policy_snapshot_contract",
                        "mode": "active_policy_list",
                        "note": "Policy snapshot from active-policies API.",
                    },
                },
                "catalogDeclaredStepCatalog": {
                    "verify_effect": {
                        "supported": True,
                        "runtimeCheck": "policy_effect_probe",
                        "mode": "policy_command_history",
                        "note": "Post-login business-effect verification via policy execution.",
                    },
                },
            },
        },
    }

    _, markdown_path = runtime_readiness.write_runtime_report(report, output_dir=tmp_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "## Support" in markdown
    assert "Supported active mutation steps" in markdown
    assert "Mutation step catalog" in markdown
    assert "create_group_via_ui" in markdown
    assert "create_user_via_ui" in markdown
    assert "assign_user_to_group_via_ui" in markdown
    assert "configured-not-verified" in markdown
    assert "membership_on_group_create" in markdown
    assert "pendingModes=existing_group_membership_update" in markdown
    assert "collect_membership_snapshot" in markdown
    assert "user_group_tree_summary" in markdown
    assert "verify_effect" in markdown
    assert "policy_command_history" in markdown
    assert "collect_policy_snapshot" in markdown
    assert "active_policy_list" in markdown


def test_operational_support_promotes_ui_mutations_only_after_active_scenario_passes(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")
    monkeypatch.setenv("LIDER_DIRECTORY_USER_CREATE_ENDPOINT", "/api/lider/user/add-user")
    monkeypatch.setenv("LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT", "/api/lider/user-groups/group/existing/add-user")
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
        lambda profile, expected_agents: ([], {}),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [],
    )
    monkeypatch.setattr(
        readiness_package,
        "_registration_parity_check",
        lambda expected_agents: runtime_readiness._build_check(
            check_id="registration_parity",
            category="registration",
            description="registration parity",
            passed=True,
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "run_policy_roundtrip_check",
        lambda: runtime_readiness._build_check(
            check_id="policy_roundtrip",
            category="operational",
            description="policy roundtrip",
            passed=True,
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "_run_ui_user_policy_roundtrip_check",
        lambda: runtime_readiness._build_check(
            check_id="ui_user_policy_roundtrip",
            category="scenario",
            description="ui-first roundtrip",
            passed=True,
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "_run_pytest_check",
        lambda check_id, description, pytest_paths, timeout: runtime_readiness._build_check(
            check_id=check_id,
            category="ui",
            description=description,
            passed=True,
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "observability_checks",
        lambda: [],
    )
    monkeypatch.setattr(
        readiness_package,
        "load_ui_mutation_evidence",
        lambda: {
            "scenario": "ui-user-policy-roundtrip",
            "verifiedSteps": {
                "create_user_via_ui": {"runtimeVerified": True},
                "assign_user_to_group_via_ui": {
                    "runtimeVerified": True,
                    "mode": "existing_group_membership_update",
                },
            },
        },
    )
    monkeypatch.setattr(
        mutation_support_module,
        "load_ui_mutation_evidence",
        lambda: {
            "scenario": "ui-user-policy-roundtrip",
            "verifiedSteps": {
                "create_user_via_ui": {"runtimeVerified": True},
                "assign_user_to_group_via_ui": {
                    "runtimeVerified": True,
                    "mode": "existing_group_membership_update",
                },
            },
        },
    )

    report = runtime_readiness.collect_runtime_operational_report(profile="dev-fidelity")

    step_support = report["support"]["mutationSupport"]["declaredStepCatalog"]["create_user_via_ui"]
    assert step_support["supported"] is True
    assert step_support["runtimeVerified"] is True
    assert step_support["status"] == "runtime-verified"
    membership_step = report["support"]["mutationSupport"]["declaredStepCatalog"]["assign_user_to_group_via_ui"]
    assert membership_step["conditionalModes"][0]["enabled"] is True
    assert membership_step["conditionalModes"][0]["runtimeVerified"] is True
