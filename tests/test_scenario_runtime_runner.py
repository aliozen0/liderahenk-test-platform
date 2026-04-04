from __future__ import annotations

from platform_runtime import scenario_runner


def test_resolve_active_scenarios_prefers_explicit_env(monkeypatch):
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip,session-login-basic")
    monkeypatch.setenv("SESSION_PACK", "login-basic")

    scenarios = scenario_runner.resolve_active_scenarios()

    assert scenarios == ["ui-user-policy-roundtrip", "session-login-basic"]


def test_resolve_active_scenarios_uses_session_pack_default(monkeypatch):
    monkeypatch.delenv("PLATFORM_SCENARIO_PACKS", raising=False)
    monkeypatch.setenv("SESSION_PACK", "login-basic")

    scenarios = scenario_runner.resolve_active_scenarios()

    assert scenarios == ["session-login-basic"]


def test_collect_scenario_checks_runs_registered_runtime_checks(monkeypatch):
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")

    def fake_ui_user_policy_roundtrip():
        return {
            "id": "ui_user_policy_roundtrip",
            "category": "scenario",
            "description": "UI-first mutation lane works",
            "status": "pass",
            "details": {"createUserVerified": True},
        }

    def fake_policy_roundtrip():
        return {
            "id": "policy_roundtrip",
            "category": "operational",
            "description": "Policy flow works",
            "status": "pass",
            "details": {"statusCode": 200},
        }

    def fake_policy_effect_probe():
        return {
            "id": "policy_effect_probe",
            "category": "scenario",
            "description": "Policy execution produces an observable effect",
            "status": "pass",
            "details": {"executionHttpStatus": 200},
        }

    def fake_policy_snapshot_contract():
        return {
            "id": "policy_snapshot_contract",
            "category": "scenario",
            "description": "Policy snapshot collected",
            "status": "pass",
            "details": {"activePolicyCount": 0},
        }

    checks, report = scenario_runner.collect_scenario_checks(
        profile="dev-fidelity",
        topology_name="dev-fidelity",
        check_runners={
            "ui_user_policy_roundtrip": fake_ui_user_policy_roundtrip,
            "policy_roundtrip": fake_policy_roundtrip,
            "policy_effect_probe": fake_policy_effect_probe,
            "policy_snapshot_contract": fake_policy_snapshot_contract,
        },
    )

    assert report["activeScenarios"] == ["ui-user-policy-roundtrip"]
    assert report["scenarios"]["ui-user-policy-roundtrip"]["status"] == "pass"
    assert checks[0]["id"] == "scenario:ui-user-policy-roundtrip:contract"
    assert checks[1]["id"] == "scenario:ui-user-policy-roundtrip:ui_user_policy_roundtrip"
    assert checks[1]["details"]["scenario"] == "ui-user-policy-roundtrip"
    assert checks[2]["id"] == "scenario:ui-user-policy-roundtrip:policy_roundtrip"
    assert checks[3]["id"] == "scenario:ui-user-policy-roundtrip:policy_effect_probe"
    assert checks[4]["id"] == "scenario:ui-user-policy-roundtrip:policy_snapshot_contract"


def test_collect_scenario_checks_fails_when_runner_missing(monkeypatch):
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "session-login-basic")

    checks, report = scenario_runner.collect_scenario_checks(
        profile="dev-fidelity",
        topology_name="dev-fidelity",
        check_runners={},
    )

    assert report["scenarios"]["session-login-basic"]["status"] == "fail"
    assert any(check["status"] == "fail" and check["actual"] == "missing" for check in checks)


def test_collect_scenario_checks_runs_login_and_session_contract_runners(monkeypatch):
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "session-login-basic")

    checks, report = scenario_runner.collect_scenario_checks(
        profile="dev-fidelity",
        topology_name="dev-fidelity",
        check_runners={
            "ui_login": lambda: {
                "id": "ui_login",
                "category": "ui",
                "description": "UI login works",
                "status": "pass",
            },
            "membership_snapshot_contract": lambda: {
                "id": "membership_snapshot_contract",
                "category": "scenario",
                "description": "Membership snapshot can be collected",
                "status": "pass",
                "details": {"captureMode": "user_group_tree_summary"},
            },
            "session_effect_contract": lambda: {
                "id": "session_effect_contract",
                "category": "scenario",
                "description": "Session contract is documented",
                "status": "pass",
            },
        },
    )

    assert report["scenarios"]["session-login-basic"]["status"] == "pass"
    assert [check["id"] for check in checks] == [
        "scenario:session-login-basic:contract",
        "scenario:session-login-basic:ui_login",
        "scenario:session-login-basic:membership_snapshot_contract",
        "scenario:session-login-basic:session_effect_contract",
    ]
    assert checks[2]["details"]["captureMode"] == "user_group_tree_summary"


def test_collect_scenario_support_summary_marks_membership_step_supported(monkeypatch):
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "ui-user-policy-roundtrip")

    support = scenario_runner.collect_scenario_support_summary(
        profile="dev-fidelity",
        topology_name="dev-fidelity",
        check_runners={"policy_roundtrip": lambda: {"id": "policy_roundtrip", "status": "pass"}},
        mutation_support={
            "create_user_via_ui": {"supported": False},
            "create_group_via_ui": {"supported": True, "adapterMethod": "create_user_group"},
            "assign_user_to_group_via_ui": {
                "supported": True,
                "adapterMethod": "create_user_group",
                "mode": "membership_on_group_create",
            },
            "create_policy_via_ui": {"supported": True, "adapterMethod": "create_policy"},
            "assign_policy_to_group_via_ui": {"supported": True, "adapterMethod": "execute_policy"},
        },
    )

    scenario = support["scenarios"]["ui-user-policy-roundtrip"]
    assert "assign_user_to_group_via_ui" in scenario["supportedMutationSteps"]
    assert scenario["mutationStepDetails"]["assign_user_to_group_via_ui"]["mode"] == "membership_on_group_create"
    assert "create_user_via_ui" in scenario["unsupportedMutationSteps"]
