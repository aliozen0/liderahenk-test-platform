from __future__ import annotations

import json
from types import SimpleNamespace

import requests

import platform_runtime.runtime_readiness as runtime_readiness
import platform_runtime.readiness as readiness_package
import platform_runtime.readiness.connectivity as readiness_connectivity
import platform_runtime.readiness.policy_roundtrip as policy_roundtrip_module
import platform_runtime.readiness.service_logs as service_logs_module


def test_collect_runtime_core_report_passes_when_all_checks_pass(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setattr(
        readiness_package,
        "_topology_summary",
        lambda profile, expected_agents: {
            "name": profile,
            "managedEndpoints": expected_agents,
            "operatorCount": 3,
            "directoryUserCount": 12,
            "userGroupCount": 4,
            "endpointGroupCount": 3,
            "policyPack": "baseline-standard",
            "sessionPack": "login-basic",
        },
    )
    monkeypatch.setattr(
        readiness_package,
        "service_state_report",
        lambda profile, expected_agents: (
            [
                runtime_readiness._build_check(
                    check_id="service:liderapi",
                    category="docker",
                    description="liderapi service readiness",
                    passed=True,
                )
            ],
            {"liderapi": {"instanceCount": 1, "states": ["running"]}},
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "core_connectivity_checks",
        lambda profile: [
            runtime_readiness._build_check(
                check_id="liderapi_auth",
                category="service",
                description="liderapi JWT authentication works",
                passed=True,
            )
        ],
    )
    monkeypatch.setattr(
        readiness_package,
        "host_port_checks",
        lambda profile: [
            runtime_readiness._build_check(
                check_id="port:8082",
                category="diagnostic",
                description="Port 8082 is reachable from localhost",
                passed=False,
                actual=8082,
                expected="open",
            )
        ],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fast")

    assert report["status"] == "pass"
    assert report["expectedAgents"] == 3
    assert report["summary"] == {"totalChecks": 2, "passedChecks": 2, "failedChecks": 0}
    assert report["services"]["liderapi"]["states"] == ["running"]
    assert report["topology"]["directoryUserCount"] == 12
    assert report["diagnostics"]["hostPorts"][0]["status"] == "fail"


def test_collect_runtime_core_report_fails_when_semantic_checks_fail_even_if_ports_pass(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "1")
    monkeypatch.setattr(
        readiness_package,
        "_topology_summary",
        lambda profile, expected_agents: {
            "name": profile,
            "managedEndpoints": expected_agents,
        },
    )
    monkeypatch.setattr(
        readiness_package,
        "service_state_report",
        lambda profile, expected_agents: (
            [
                runtime_readiness._build_check(
                    check_id="service:liderapi",
                    category="docker",
                    description="liderapi service readiness",
                    passed=True,
                )
            ],
            {"liderapi": {"instanceCount": 1, "states": ["running"]}},
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "core_connectivity_checks",
        lambda profile: [
            runtime_readiness._build_check(
                check_id="liderapi_auth",
                category="service",
                description="liderapi JWT authentication works",
                passed=False,
                actual=False,
                expected=True,
            )
        ],
    )
    monkeypatch.setattr(
        readiness_package,
        "host_port_checks",
        lambda profile: [
            runtime_readiness._build_check(
                check_id="port:8082",
                category="diagnostic",
                description="Port 8082 is reachable from localhost",
                passed=True,
                actual=8082,
                expected="open",
            )
        ],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fast")

    assert report["status"] == "fail"
    assert report["summary"] == {"totalChecks": 2, "passedChecks": 1, "failedChecks": 1}
    assert report["diagnostics"]["hostPorts"][0]["status"] == "pass"


def test_collect_runtime_operational_report_fails_on_any_check(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "2")
    monkeypatch.setattr(
        readiness_package,
        "_topology_summary",
        lambda profile, expected_agents: {
            "name": profile,
            "managedEndpoints": expected_agents,
            "operatorCount": 2,
        },
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
            passed=False,
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
        "_scenario_operational_checks",
        lambda profile, topology: (
            [
                runtime_readiness._build_check(
                    check_id="scenario:session-login-basic:ui_login",
                    category="scenario",
                    description="Scenario login check",
                    passed=True,
                )
            ],
            {
                "activeScenarios": ["session-login-basic"],
                "scenarios": {"session-login-basic": {"status": "pass"}},
            },
        ),
    )
    monkeypatch.setattr(
        readiness_package,
        "observability_checks",
        lambda: [
            runtime_readiness._build_check(
                check_id="observability_targets",
                category="observability",
                description="observability targets",
                passed=True,
            )
        ],
    )

    report = runtime_readiness.collect_runtime_operational_report(profile="dev-fidelity")

    assert report["status"] == "fail"
    assert report["summary"]["failedChecks"] == 1
    assert any(check["id"] == "policy_roundtrip" and check["status"] == "fail" for check in report["checks"])
    assert report["topology"]["managedEndpoints"] == 2
    assert report["scenarios"]["activeScenarios"] == ["session-login-basic"]


def test_registration_parity_check_returns_fail_after_retries(monkeypatch):
    class _FailingCollector:
        @classmethod
        def from_env(cls):
            return cls()

        def collect_snapshot(self):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(readiness_package, "RegistrationCollector", _FailingCollector)
    monkeypatch.setattr(readiness_package.time, "sleep", lambda *_args, **_kwargs: None)

    check = runtime_readiness._registration_parity_check(expected_agents=10)

    assert check["status"] == "fail"
    assert check["actual"] == "RuntimeError"
    assert check["details"] == {"error": "connection reset", "attemptCount": 3}


def test_host_port_checks_follow_required_ports_contract(monkeypatch):
    monkeypatch.setattr(
        readiness_connectivity,
        "_runtime_readiness_contract",
        lambda: {
            "runtime_profiles": {
                "dev-fast": {
                    "required_ports": [1111, 2222],
                }
            }
        },
    )
    seen_calls = []

    def _fake_port_open(host, port, timeout=3):
        seen_calls.append((host, port, timeout))
        return port == 2222

    monkeypatch.setattr(readiness_connectivity, "port_open", _fake_port_open)

    checks = readiness_connectivity.host_port_checks("dev-fast")

    assert [check["id"] for check in checks] == ["port:1111", "port:2222"]
    assert [check["status"] for check in checks] == ["fail", "pass"]
    assert seen_calls == [("127.0.0.1", 1111, 3), ("127.0.0.1", 2222, 3)]


def test_write_runtime_report_uses_expected_runtime_filenames(tmp_path):
    report = {
        "schemaVersion": 1,
        "reportType": "runtime-core",
        "status": "pass",
        "profile": "dev-fast",
        "expectedAgents": 1,
        "generatedAt": "2026-01-01T00:00:00+00:00",
        "checks": [
            {
                "id": "liderapi_auth",
                "category": "service",
                "description": "liderapi JWT authentication works",
                "status": "pass",
            }
        ],
        "summary": {"totalChecks": 1, "passedChecks": 1, "failedChecks": 0},
    }

    json_path, markdown_path = runtime_readiness.write_runtime_report(report, output_dir=tmp_path)

    assert json_path.name == "runtime-core-report.json"
    assert markdown_path.name == "runtime-core-report.md"
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "pass"
    assert "liderapi_auth" in markdown_path.read_text(encoding="utf-8")


def test_membership_snapshot_contract_collects_user_group_tree_summary(monkeypatch):
    class _FakeApi:
        def __init__(self, *args, **kwargs):
            self.is_authenticated = True

        def get_user_group_tree(self):
            return [
                {
                    "distinguishedName": "ou=Groups,dc=liderahenk,dc=org",
                    "childEntries": [
                        {
                            "distinguishedName": "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org",
                            "memberCount": 2,
                        }
                    ],
                }
            ]

    monkeypatch.setattr(readiness_package, "LiderApiAdapter", _FakeApi)

    check = runtime_readiness._run_membership_snapshot_contract_check()

    assert check["status"] == "pass"
    assert check["actual"] == {
        "status": "collected",
        "rootCount": 1,
        "nodeCount": 2,
        "memberBearingNodeCount": 1,
        "declaredMemberCount": 2,
    }
    assert check["details"]["summary"]["sampleGroupDns"] == [
        "ou=Groups,dc=liderahenk,dc=org",
        "cn=ug-standard,ou=Groups,dc=liderahenk,dc=org",
    ]


def test_session_effect_contract_reports_membership_snapshot_context(monkeypatch):
    monkeypatch.setenv("PLATFORM_SCENARIO_PACKS", "session-login-basic")
    monkeypatch.setenv("SESSION_PACK", "login-basic")
    monkeypatch.setattr(
        readiness_package,
        "_collect_membership_snapshot",
        lambda: {
            "status": "collected",
            "captureMode": "user_group_tree_summary",
            "summary": {"rootCount": 1, "nodeCount": 2},
        },
    )

    check = runtime_readiness._run_session_effect_contract_check()

    assert check["status"] == "pass"
    assert check["actual"]["membershipSnapshotStatus"] == "collected"
    assert "collect_membership_snapshot" in check["actual"]["supportedSteps"]
    assert check["details"]["membershipSnapshot"]["captureMode"] == "user_group_tree_summary"


def test_policy_roundtrip_reconciles_group_creation_when_api_returns_417(monkeypatch):
    monkeypatch.setenv("LDAP_AGENT_GROUPS_OU", "ou=AgentGroups,dc=liderahenk,dc=org")

    class _FakeApi:
        def __init__(self, *args, **kwargs):
            self.group_name = None

        def get_computer_tree(self):
            return [{"type": "AHENK", "distinguishedName": "cn=ahenk-001,ou=Ahenkler,dc=liderahenk,dc=org"}]

        def create_computer_group(self, *, group_name, checked_entries, selected_ou_dn):
            self.group_name = group_name
            error = requests.HTTPError("417 create-new-agent-group")
            error.response = SimpleNamespace(status_code=417, text="created-with-warning")
            raise error

        def get_computer_group_tree(self):
            return [
                {
                    "name": "Agent",
                    "childEntries": [
                        {
                            "cn": self.group_name,
                            "distinguishedName": f"cn={self.group_name},ou=AgentGroups,dc=liderahenk,dc=org",
                        }
                    ],
                }
            ]

        def create_script_profile(self, **kwargs):
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            return {"id": 77, "label": kwargs["label"]}

        def execute_policy(self, *args, **kwargs):
            return SimpleNamespace(status_code=200)

        def delete_policy(self, **kwargs):
            return {"statusCode": 200, **kwargs}

        def delete_profile(self, **kwargs):
            return {"statusCode": 200, **kwargs}

        def delete_computer_group(self, **kwargs):
            return {"statusCode": 200, **kwargs}

    monkeypatch.setattr(policy_roundtrip_module, "LiderApiAdapter", _FakeApi)

    check = runtime_readiness._run_policy_roundtrip_check()

    assert check["status"] == "pass"
    assert check["actual"] == 200
    assert check["details"]["cleanup"]["status"] == "completed"
    assert check["details"]["groupCreateReconciliation"] == {
        "mode": "group_tree_reconciliation",
        "httpStatus": 417,
        "groupName": check["details"]["groupDn"].split(",")[0].split("=", 1)[1],
        "responseText": "created-with-warning",
    }


def test_policy_roundtrip_attempts_cleanup_when_policy_creation_fails(monkeypatch):
    calls = []

    class _FakeApi:
        def __init__(self, *args, **kwargs):
            pass

        def get_computer_tree(self):
            return [{"type": "AHENK", "distinguishedName": "cn=ahenk-001,ou=Ahenkler,dc=liderahenk,dc=org"}]

        def create_computer_group(self, *, group_name, checked_entries, selected_ou_dn):
            calls.append(("create_computer_group", group_name))
            return {"distinguishedName": f"cn={group_name},{selected_ou_dn}"}

        def create_script_profile(self, **kwargs):
            calls.append(("create_script_profile", kwargs["label"]))
            return {"id": 41, "label": kwargs["label"]}

        def create_policy(self, **kwargs):
            calls.append(("create_policy", kwargs["label"]))
            raise RuntimeError("policy create failed")

        def delete_profile(self, **kwargs):
            calls.append(("delete_profile", kwargs["profile_id"]))
            return {"statusCode": 200}

        def delete_computer_group(self, **kwargs):
            calls.append(("delete_computer_group", kwargs["dn"]))
            return {"statusCode": 200}

    monkeypatch.setattr(policy_roundtrip_module, "LiderApiAdapter", _FakeApi)

    check = runtime_readiness._run_policy_roundtrip_check()

    assert check["status"] == "fail"
    assert check["actual"] == "RuntimeError"
    assert check["details"]["stage"] == "create_policy"
    assert check["details"]["cleanup"]["status"] == "completed"
    assert check["details"]["cleanup"]["failed"] == []
    assert check["details"]["cleanup"]["attempted"][0] == {
        "resource": "profile",
        "identifier": "41",
        "method": "delete_profile",
    }
    assert check["details"]["cleanup"]["attempted"][1]["resource"] == "group"
    assert check["details"]["cleanup"]["attempted"][1]["method"] == "delete_computer_group"
    assert [name for name, _ in calls] == [
        "create_computer_group",
        "create_script_profile",
        "create_policy",
        "delete_profile",
        "delete_computer_group",
    ]


def test_policy_roundtrip_returns_fail_check_instead_of_raising(monkeypatch):
    class _FakeApi:
        def __init__(self, *args, **kwargs):
            pass

        def get_computer_tree(self):
            raise RuntimeError("computer tree unavailable")

    monkeypatch.setattr(policy_roundtrip_module, "LiderApiAdapter", _FakeApi)

    check = runtime_readiness._run_policy_roundtrip_check()

    assert check["status"] == "fail"
    assert check["actual"] == "RuntimeError"
    assert check["details"] == {
        "stage": "get_computer_tree",
        "error": "computer tree unavailable",
    }


def test_policy_roundtrip_captures_liderapi_permission_diagnosis(monkeypatch):
    class _FakeApi:
        def __init__(self, *args, **kwargs):
            pass

        def get_computer_tree(self):
            return [{"type": "AHENK", "distinguishedName": "cn=ahenk-001,ou=Ahenkler,dc=liderahenk,dc=org"}]

        def create_computer_group(self, **kwargs):
            error = requests.HTTPError("417 create-new-agent-group")
            error.response = SimpleNamespace(status_code=417, text="")
            raise error

        def get_computer_group_tree(self):
            return []

    monkeypatch.setattr(policy_roundtrip_module, "LiderApiAdapter", _FakeApi)
    monkeypatch.setattr(
        policy_roundtrip_module,
        "tail_service_logs",
        lambda service_name, tail=120: {
            "container": "liderahenk-test-liderapi-1",
            "available": True,
            "tailLines": tail,
            "tail": (
                "ComputerGroupsController.createNewAgentGroup failed\n"
                "LDAP: no write access to parent\n"
            ),
            "error": None,
        },
    )
    monkeypatch.setattr(
        policy_roundtrip_module,
        "search_service_logs",
        lambda service_name, since="20m": {
            "container": "liderahenk-test-liderapi-1",
            "available": True,
            "since": since,
            "logs": (
                "ComputerGroupsController.createNewAgentGroup failed\n"
                "LDAP: no write access to parent\n"
            ),
            "error": None,
        },
    )

    check = runtime_readiness._run_policy_roundtrip_check()

    assert check["status"] == "fail"
    assert check["details"]["stage"] == "create_computer_group"
    assert check["details"]["httpStatus"] == 417
    assert check["details"]["diagnosis"] == {
        "classification": "ldap_parent_write_denied",
        "likelyCause": (
            "Lider API computer-group creation appears to run with an authenticated bind "
            "that cannot write to the parent OU, which matches the authenticated-user "
            "LDAP bind mode failure seen in ComputerGroupsController.createNewAgentGroup."
        ),
        "evidenceLines": [
            "ComputerGroupsController.createNewAgentGroup failed",
            "LDAP: no write access to parent",
        ],
    }
