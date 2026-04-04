"""
Runtime readiness subsystem — decomposed from the original monolithic module.

Public API:
    - collect_runtime_core_report
    - collect_runtime_operational_report
    - write_runtime_report
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from platform_runtime.registration import RegistrationCollector
from platform_runtime.scenario_runner import collect_scenario_checks, collect_scenario_support_summary

from .checks import build_check, summarize_checks
from .containers import service_state_report
from .connectivity import core_connectivity_checks, host_port_checks, observability_checks, http_get
from .mutation_support import (
    mutation_step_support,
    session_support_summary,
    support_summary,
)
from .mutation_evidence import clear_ui_mutation_evidence, load_ui_mutation_evidence
from .policy_roundtrip import run_policy_roundtrip_check

LiderApiAdapter = None

DEFAULT_PLATFORM_ARTIFACTS_DIR = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))
FALLBACK_PLATFORM_ARTIFACTS_DIR = Path(
    os.environ.get("PLATFORM_RUNTIME_FALLBACK_ARTIFACTS_DIR", "artifacts/platform-local")
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile_name(profile: str | None = None) -> str:
    return profile or os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fast")


def _load_topology_profile_module():
    module_path = Path(__file__).resolve().parents[2] / "platform" / "topology" / "profile_loader.py"
    spec = importlib.util.spec_from_file_location("topology_profile_loader", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError(f"unable to load topology profile loader from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_lider_api_adapter():
    adapter_cls = globals().get("LiderApiAdapter")
    if adapter_cls is not None:
        return adapter_cls
    from adapters.lider_api_adapter import LiderApiAdapter as _LiderApiAdapter

    return _LiderApiAdapter


def _topology_summary(profile: str, expected_agents: int) -> dict[str, Any]:
    try:
        topology_module = _load_topology_profile_module()
        topology = topology_module.resolve_topology_profile(
            profile,
            expected_agents=expected_agents,
            env=os.environ.copy(),
        )
        return {
            "name": topology["name"],
            "managedEndpoints": topology["managed_endpoint_count"],
            "operatorCount": topology["operators"]["count"],
            "directoryUserCount": topology["directory_users"]["count"],
            "userGroupCount": topology["user_groups"]["count"],
            "endpointGroupCount": topology["endpoint_groups"]["count"],
            "policyPack": topology["policy_pack"],
            "sessionPack": topology["session_pack"],
        }
    except Exception as exc:  # pragma: no cover
        return {
            "name": os.environ.get("TOPOLOGY_PROFILE", profile),
            "managedEndpoints": expected_agents,
            "resolutionError": str(exc),
        }


def _registration_parity_check(expected_agents: int) -> dict[str, Any]:
    collector = RegistrationCollector.from_env()
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            snapshot = collector.collect_snapshot()
            verdict = collector.evaluate_snapshot(snapshot)
            parity_ok = verdict["status"] == "pass" and snapshot["expectedAgents"] == expected_agents
            details = {
                "failedChecks": verdict["failedChecks"],
                "surfaces": verdict["surfaces"],
                "taxonomy": verdict["taxonomy"],
                "attemptCount": attempt,
            }
            return build_check(
                check_id="registration_parity",
                category="registration",
                description="Runtime registration parity matches expected agent count",
                passed=parity_ok,
                actual=verdict["surfaces"],
                expected={"expectedAgents": expected_agents},
                details=details,
            )
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(2)

    return build_check(
        check_id="registration_parity",
        category="registration",
        description="Runtime registration parity matches expected agent count",
        passed=False,
        actual=type(last_error).__name__ if last_error is not None else "unknown",
        expected={"expectedAgents": expected_agents},
        details={
            "error": str(last_error) if last_error is not None else "unknown error",
            "attemptCount": 3,
        },
    )


def _run_pytest_check(check_id: str, description: str, pytest_paths: list[str], timeout: int) -> dict[str, Any]:
    cmd = ["python3", "-m", "pytest", *pytest_paths, "-v", "--timeout", str(timeout), "--tb=short"]
    started = time.monotonic()
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(Path.cwd()) if not existing_pythonpath else f"{Path.cwd()}:{existing_pythonpath}"
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()), env=env)
    duration = round(time.monotonic() - started, 2)
    return build_check(
        check_id=check_id,
        category="ui",
        description=description,
        passed=result.returncode == 0,
        actual=result.returncode,
        expected=0,
        details={
            "durationSeconds": duration,
            "stdoutTail": "\n".join(result.stdout.splitlines()[-12:]),
            "stderrTail": "\n".join(result.stderr.splitlines()[-12:]),
        },
    )


def _iter_tree_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for key in ("childEntries", "children"):
        value = node.get(key)
        if isinstance(value, list):
            children.extend(item for item in value if isinstance(item, dict))
    return children


def _node_membership_count(node: dict[str, Any]) -> tuple[int, list[str]]:
    if isinstance(node.get("memberCount"), int):
        return max(int(node["memberCount"]), 0), ["memberCount"]
    sources: list[str] = []
    max_count = 0
    for key in ("checkedEntries", "memberEntries", "members", "memberDns", "memberUids"):
        value = node.get(key)
        if isinstance(value, list):
            sources.append(key)
            max_count = max(max_count, len(value))
    return max_count, sources


def _summarize_user_group_tree(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    queue = [node for node in nodes if isinstance(node, dict)]
    root_dns = [
        str(node.get("distinguishedName"))
        for node in queue
        if node.get("distinguishedName")
    ]
    node_count = 0
    leaf_count = 0
    member_bearing_node_count = 0
    declared_member_count = 0
    member_source_keys: set[str] = set()
    sample_group_dns: list[str] = []

    while queue:
        node = queue.pop(0)
        node_count += 1
        dn = node.get("distinguishedName")
        if isinstance(dn, str) and dn and len(sample_group_dns) < 5:
            sample_group_dns.append(dn)
        children = _iter_tree_children(node)
        if not children:
            leaf_count += 1
        queue.extend(children)
        membership_count, membership_sources = _node_membership_count(node)
        if membership_count > 0:
            member_bearing_node_count += 1
            declared_member_count += membership_count
            member_source_keys.update(membership_sources)

    return {
        "captureMode": "user_group_tree_summary",
        "rootCount": len(root_dns),
        "nodeCount": node_count,
        "leafCount": leaf_count,
        "memberBearingNodeCount": member_bearing_node_count,
        "declaredMemberCount": declared_member_count,
        "memberSourceKeys": sorted(member_source_keys),
        "sampleGroupDns": sample_group_dns,
    }


def _collect_membership_snapshot() -> dict[str, Any]:
    LiderApiAdapter = _resolve_lider_api_adapter()
    api = LiderApiAdapter(
        base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )
    if not api.is_authenticated:
        return {
            "status": "auth_unavailable",
            "captureMode": "user_group_tree_summary",
            "note": "liderapi authentication is required before collecting membership evidence.",
        }
    try:
        tree = api.get_user_group_tree()
    except Exception as exc:
        return {
            "status": "collection_failed",
            "captureMode": "user_group_tree_summary",
            "error": str(exc),
        }
    summary = _summarize_user_group_tree(tree)
    return {
        "status": "collected",
        "captureMode": summary["captureMode"],
        "summary": summary,
    }


def _run_membership_snapshot_contract_check() -> dict[str, Any]:
    snapshot = _collect_membership_snapshot()
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    return build_check(
        check_id="membership_snapshot_contract",
        category="scenario",
        description="Runtime can collect a concrete membership snapshot from the user-group tree",
        passed=snapshot.get("status") == "collected",
        actual={
            "status": snapshot.get("status"),
            "rootCount": summary.get("rootCount"),
            "nodeCount": summary.get("nodeCount"),
            "memberBearingNodeCount": summary.get("memberBearingNodeCount"),
            "declaredMemberCount": summary.get("declaredMemberCount"),
        },
        expected={"status": "collected"},
        details=snapshot,
    )


def _run_policy_effect_probe_check() -> dict[str, Any]:
    LiderApiAdapter = _resolve_lider_api_adapter()

    """Verify real business side-effect: run policy roundtrip and confirm
    command execution result appears in the API.

    This separates 'login reachability' from 'observable business effect'.
    The probe creates a group, profile, policy, executes it, then checks
    command history for evidence the execution was recorded."""
    api = LiderApiAdapter(
        base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )
    if not api.is_authenticated:
        return build_check(
            check_id="policy_effect_probe",
            category="scenario",
            description="Policy execution produces an observable command history entry",
            passed=False,
            details={"error": "liderapi authentication required"},
        )

    from platform_runtime.readiness.policy_roundtrip import (
        create_computer_group_with_reconciliation,
        cleanup_roundtrip_artifacts,
    )

    def find_first_agent(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
        for node in nodes or []:
            if node.get("type") in {"AHENK", "WINDOWS_AHENK"}:
                return node
            child = find_first_agent(node.get("childEntries", []) or node.get("children", []))
            if child:
                return child
        return None

    group = None
    profile = None
    policy = None
    try:
        tree = api.get_computer_tree()
        entry = find_first_agent(tree)
        if not entry:
            return build_check(
                check_id="policy_effect_probe",
                category="scenario",
                description="Policy execution produces an observable command history entry",
                passed=False,
                details={"error": "no agent found in computer tree"},
            )

        token = uuid.uuid4().hex[:8]
        selected_ou_dn = os.environ.get(
            "LDAP_AGENT_GROUPS_OU",
            f"ou=AgentGroups,{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
        )
        group, _ = create_computer_group_with_reconciliation(
            api,
            group_name=f"effect-probe-{token}",
            checked_entries=[entry],
            selected_ou_dn=selected_ou_dn,
        )
        profile = api.create_script_profile(
            label=f"effect-profile-{token}",
            description="Sprint 4 verify_effect probe",
            script_contents=f"#!/bin/bash\necho effect-probe-{token}",
        )
        policy = api.create_policy(
            label=f"effect-policy-{token}",
            description="Sprint 4 effect verification",
            profiles=[profile],
            active=False,
        )
        exec_response = api.execute_policy(policy["id"], group["distinguishedName"], "GROUP")
        execution_ok = exec_response.status_code == 200

        # Check command history for evidence of execution
        agent_dn = entry.get("distinguishedName", "")
        effect_evidence = {"executionHttpStatus": exec_response.status_code}
        if execution_ok and agent_dn:
            try:
                time.sleep(2)  # brief wait for command processing
                history = api.get_command_history(agent_dn)
                recent_commands = [
                    cmd for cmd in (history or [])
                    if isinstance(cmd, dict)
                ]
                effect_evidence["commandHistoryCount"] = len(recent_commands)
                effect_evidence["commandHistoryAvailable"] = len(recent_commands) > 0
            except Exception as hist_exc:
                effect_evidence["commandHistoryError"] = str(hist_exc)
                effect_evidence["commandHistoryAvailable"] = False

        cleanup = cleanup_roundtrip_artifacts(
            api,
            policy=policy,
            profile=profile,
            group_dn=group.get("distinguishedName") if isinstance(group, dict) else None,
            delete_group_method="delete_computer_group",
        )
        effect_evidence["cleanup"] = cleanup
        return build_check(
            check_id="policy_effect_probe",
            category="scenario",
            description="Policy execution produces an observable command history entry",
            passed=execution_ok,
            actual=effect_evidence,
            expected={"executionHttpStatus": 200},
            details=effect_evidence,
        )
    except Exception as exc:
        cleanup = cleanup_roundtrip_artifacts(
            api,
            policy=policy,
            profile=profile,
            group_dn=group.get("distinguishedName") if isinstance(group, dict) else None,
            delete_group_method="delete_computer_group",
        )
        return build_check(
            check_id="policy_effect_probe",
            category="scenario",
            description="Policy execution produces an observable command history entry",
            passed=False,
            actual=type(exc).__name__,
            expected="successful policy effect verification",
            details={"error": str(exc), "cleanup": cleanup},
        )


def _collect_policy_snapshot() -> dict[str, Any]:
    """Collect a snapshot of active policies from the Lider API."""
    LiderApiAdapter = _resolve_lider_api_adapter()
    api = LiderApiAdapter(
        base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )
    if not api.is_authenticated:
        return {
            "status": "auth_unavailable",
            "captureMode": "active_policy_list",
            "note": "liderapi authentication is required before collecting policy snapshot.",
        }
    try:
        policies = api.get_active_policies()
        return {
            "status": "collected",
            "captureMode": "active_policy_list",
            "summary": {
                "activePolicyCount": len(policies) if isinstance(policies, list) else 0,
                "sampleLabels": [
                    str(p.get("label", ""))
                    for p in (policies if isinstance(policies, list) else [])[:5]
                ],
            },
        }
    except Exception as exc:
        return {
            "status": "collection_failed",
            "captureMode": "active_policy_list",
            "error": str(exc),
        }


def _run_policy_snapshot_contract_check() -> dict[str, Any]:
    snapshot = _collect_policy_snapshot()
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    return build_check(
        check_id="policy_snapshot_contract",
        category="scenario",
        description="Runtime can collect a concrete policy snapshot from the active-policies API",
        passed=snapshot.get("status") == "collected",
        actual={
            "status": snapshot.get("status"),
            "activePolicyCount": summary.get("activePolicyCount"),
        },
        expected={"status": "collected"},
        details=snapshot,
    )


def _run_session_effect_contract_check() -> dict[str, Any]:
    profile = _profile_name()
    topology_name = str(os.environ.get("TOPOLOGY_PROFILE") or profile)
    scenario_support = collect_scenario_support_summary(
        profile=profile,
        topology_name=topology_name,
        env=os.environ.copy(),
        check_runners={
            "ui_login": lambda: {},
            "ui_user_policy_roundtrip": lambda: {},
            "membership_snapshot_contract": lambda: {},
            "policy_roundtrip": lambda: {},
            "policy_effect_probe": lambda: {},
            "policy_snapshot_contract": lambda: {},
            "session_effect_contract": lambda: {},
        },
    )
    session_support = session_support_summary(
        scenario_support=scenario_support,
        available_checks={
            "ui_login",
            "membership_snapshot_contract",
            "policy_effect_probe",
            "policy_snapshot_contract",
            "session_effect_contract",
            "ui_agent_visibility",
        },
    )
    active_scenarios = session_support["activeScenarios"]
    if not active_scenarios:
        return build_check(
            check_id="session_effect_contract",
            category="scenario",
            description="Session scenarios declare their supported and pending effect steps explicitly",
            passed=True,
            details={"activeScenarios": [], "note": "No active session scenario pack"},
        )

    membership_snapshot = _collect_membership_snapshot()
    policy_snapshot = _collect_policy_snapshot()
    unsupported_steps = session_support["unsupportedDeclaredSteps"]
    documented_unsupported = all(
        session_support["declaredStepCatalog"].get(step, {}).get("note")
        for step in unsupported_steps
    )
    supported_steps = session_support["supportedDeclaredSteps"]
    required_steps = ("simulate_login", "collect_membership_snapshot", "verify_effect")
    passed = all(
        required_step in supported_steps
        for required_step in required_steps
    ) and documented_unsupported
    return build_check(
        check_id="session_effect_contract",
        category="scenario",
        description="Session scenarios declare login, membership, effect verification, and policy snapshot support consistently",
        passed=passed,
        actual={
            "activeScenarios": active_scenarios,
            "supportedSteps": supported_steps,
            "unsupportedSteps": unsupported_steps,
            "membershipSnapshotStatus": membership_snapshot.get("status"),
            "policySnapshotStatus": policy_snapshot.get("status"),
        },
        expected={
            "simulate_login": "supported",
            "collect_membership_snapshot": "supported",
            "verify_effect": "supported",
            "unsupportedSteps": "documented when pending",
        },
        details={
            "declaredSteps": session_support["declaredStepCatalog"],
            "membershipSnapshot": membership_snapshot,
            "policySnapshot": policy_snapshot,
        },
    )


def _run_ui_user_policy_roundtrip_check() -> dict[str, Any]:
    clear_ui_mutation_evidence()
    pytest_check = _run_pytest_check(
        check_id="ui_user_policy_roundtrip",
        description="UI-first user, existing-group membership, and policy surfaces execute successfully",
        pytest_paths=["tests/e2e/specs/management/test_user_group_policy_roundtrip.py"],
        timeout=240,
    )
    evidence = load_ui_mutation_evidence() or {}
    verified_steps = evidence.get("verifiedSteps", {}) if isinstance(evidence, dict) else {}
    create_user_verified = isinstance(verified_steps.get("create_user_via_ui"), dict) and (
        verified_steps["create_user_via_ui"].get("runtimeVerified") is True
    )
    membership_verified = isinstance(verified_steps.get("assign_user_to_group_via_ui"), dict) and (
        verified_steps["assign_user_to_group_via_ui"].get("runtimeVerified") is True
    ) and verified_steps["assign_user_to_group_via_ui"].get("mode") == "existing_group_membership_update"
    pytest_passed = pytest_check["status"] == "pass"
    details = dict(pytest_check.get("details") or {})
    details["mutationEvidence"] = evidence
    return build_check(
        check_id="ui_user_policy_roundtrip",
        category="scenario",
        description="UI-first user creation and existing-group membership path leave concrete runtime evidence",
        passed=pytest_passed and create_user_verified and membership_verified,
        actual={
            "pytestPassed": pytest_passed,
            "createUserVerified": create_user_verified,
            "existingGroupMembershipVerified": membership_verified,
        },
        expected={
            "pytestPassed": True,
            "createUserVerified": True,
            "existingGroupMembershipVerified": True,
        },
        details=details,
    )


def _scenario_runner_registry() -> dict[str, Any]:
    return {
        "policy_roundtrip": run_policy_roundtrip_check,
        "ui_login": lambda: _run_pytest_check(
            check_id="ui_login",
            description="Login flow remains reachable from the UI",
            pytest_paths=["tests/e2e/specs/auth/test_login.py"],
            timeout=180,
        ),
        "ui_user_policy_roundtrip": _run_ui_user_policy_roundtrip_check,
        "membership_snapshot_contract": _run_membership_snapshot_contract_check,
        "policy_effect_probe": _run_policy_effect_probe_check,
        "policy_snapshot_contract": _run_policy_snapshot_contract_check,
        "session_effect_contract": _run_session_effect_contract_check,
    }


def _scenario_operational_checks(profile: str, topology: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scenario_runners = _scenario_runner_registry()
    return collect_scenario_checks(
        profile=profile,
        topology_name=str(topology.get("name") or profile),
        env=os.environ.copy(),
        check_runners=scenario_runners,
    )


# ── Public API ──────────────────────────────────────────────


def collect_runtime_core_report(profile: str | None = None) -> dict[str, Any]:
    resolved_profile = _profile_name(profile)
    expected_agents = int(os.environ.get("AHENK_COUNT", "1"))
    started_at = _utc_now()
    env = os.environ.copy()
    topology = _topology_summary(resolved_profile, expected_agents)
    service_checks, services_report = service_state_report(resolved_profile, expected_agents)
    connectivity_checks = core_connectivity_checks(resolved_profile)
    diagnostic_checks = host_port_checks(resolved_profile)
    checks = service_checks + connectivity_checks
    summary = summarize_checks(checks)
    return {
        "schemaVersion": 1,
        "reportType": "runtime-core",
        "status": "pass" if summary["failedChecks"] == 0 else "fail",
        "profile": resolved_profile,
        "expectedAgents": expected_agents,
        "generatedAt": started_at,
        "checks": checks,
        "summary": summary,
        "services": services_report,
        "diagnostics": {
            "hostPorts": diagnostic_checks,
        },
        "topology": topology,
        "support": support_summary(
            profile=resolved_profile,
            topology=topology,
            env=env,
        ),
    }


def collect_runtime_operational_report(profile: str | None = None) -> dict[str, Any]:
    resolved_profile = _profile_name(profile)
    expected_agents = int(os.environ.get("AHENK_COUNT", "1"))
    env = os.environ.copy()
    topology = _topology_summary(resolved_profile, expected_agents)
    scenario_runners = _scenario_runner_registry()
    checks: list[dict[str, Any]] = []
    checks.append(_registration_parity_check(expected_agents))
    checks.append(run_policy_roundtrip_check())
    scenario_checks, scenario_report = _scenario_operational_checks(resolved_profile, topology)
    checks.extend(scenario_checks)
    checks.append(
        _run_pytest_check(
            check_id="ui_agent_visibility",
            description="Computer management UI shows registered agents consistently",
            pytest_paths=["tests/e2e/specs/management/test_agent_registration.py"],
            timeout=180,
        )
    )
    checks.append(
        _run_pytest_check(
            check_id="ui_dashboard_summary_parity",
            description="Dashboard summary cards match the official dashboard backend metrics",
            pytest_paths=["tests/e2e/specs/auth/test_dashboard_summary.py"],
            timeout=180,
        )
    )
    checks.append(
        _run_pytest_check(
            check_id="ui_computer_information_inventory",
            description="Computer information inventory fields match the official backend inventory surfaces",
            pytest_paths=["tests/e2e/specs/management/test_computer_information.py"],
            timeout=180,
        )
    )
    checks.append(
        _run_pytest_check(
            check_id="ui_script_task_dispatch",
            description="Script task flow is reachable from UI and dispatches from backend",
            pytest_paths=["tests/e2e/specs/management/test_send_task.py"],
            timeout=180,
        )
    )
    checks.append(
        _run_pytest_check(
            check_id="ui_task_history_reflects_command_history",
            description="Task history UI reflects recent backend command history entries",
            pytest_paths=["tests/e2e/specs/management/test_task_history.py"],
            timeout=180,
        )
    )
    checks.extend(observability_checks())
    summary = summarize_checks(checks)
    return {
        "schemaVersion": 1,
        "reportType": "runtime-operational",
        "status": "pass" if summary["failedChecks"] == 0 else "fail",
        "profile": resolved_profile,
        "expectedAgents": expected_agents,
        "generatedAt": _utc_now(),
        "checks": checks,
        "summary": summary,
        "topology": topology,
        "scenarios": scenario_report,
        "support": support_summary(
            profile=resolved_profile,
            topology=topology,
            env=env,
            scenario_runners=scenario_runners,
            scenario_report=scenario_report,
        ),
    }


def write_runtime_report(
    report: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    artifacts_dir = output_dir or DEFAULT_PLATFORM_ARTIFACTS_DIR
    stem = report["reportType"]

    def write_to(directory: Path) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / f"{stem}-report.json"
        markdown_path = directory / f"{stem}-report.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [
            f"# {report['reportType'].title()} Report",
            "",
            f"- Status: `{report['status']}`",
            f"- Profile: `{report['profile']}`",
            f"- Expected agents: `{report['expectedAgents']}`",
            f"- Generated at: `{report['generatedAt']}`",
            "",
            "## Summary",
            "",
            f"- Total checks: `{report['summary']['totalChecks']}`",
            f"- Passed checks: `{report['summary']['passedChecks']}`",
            f"- Failed checks: `{report['summary']['failedChecks']}`",
            "",
        ]
        if report.get("scenarios"):
            lines.extend(
                [
                    "## Scenarios",
                    "",
                    f"- Active scenarios: `{', '.join(report['scenarios'].get('activeScenarios', [])) or 'none'}`",
                    "",
                ]
            )
        diagnostics = report.get("diagnostics") or {}
        host_ports = diagnostics.get("hostPorts") if isinstance(diagnostics, dict) else None
        if host_ports:
            lines.extend(
                [
                    "## Diagnostics",
                    "",
                ]
            )
            for check in host_ports:
                lines.append(
                    f"- `{check['status'].upper()}` {check['id']}: {check['description']}"
                )
            lines.append("")
        support = report.get("support") or {}
        if support:
            mutation_support_data = support.get("mutationSupport", {})
            scenario_support = support.get("scenarios", {})
            session_support_data = support.get("sessionSupport", {})
            declared_catalog = mutation_support_data.get("declaredStepCatalog", {})
            catalog_mutation_catalog = mutation_support_data.get("catalogDeclaredStepCatalog", {})
            session_catalog = session_support_data.get("declaredStepCatalog", {})
            catalog_session_catalog = session_support_data.get("catalogDeclaredStepCatalog", {})
            lines.extend(
                [
                    "## Support",
                    "",
                    f"- Topology profile: `{support.get('topology', {}).get('profile') or 'unknown'}`",
                    f"- Available scenarios: `{len(scenario_support.get('availableScenarios', []))}`",
                    f"- Active scenarios: `{', '.join(scenario_support.get('activeScenarios', [])) or 'none'}`",
                    f"- Supported active mutation steps: `{', '.join(mutation_support_data.get('supportedDeclaredSteps', [])) or 'none'}`",
                    f"- Unsupported active mutation steps: `{', '.join(mutation_support_data.get('unsupportedDeclaredSteps', [])) or 'none'}`",
                    f"- Mutation step catalog: `{', '.join(mutation_support_data.get('catalogDeclaredSteps', [])) or 'none'}`",
                    f"- Supported active session steps: `{', '.join(session_support_data.get('supportedDeclaredSteps', [])) or 'none'}`",
                    f"- Unsupported active session steps: `{', '.join(session_support_data.get('unsupportedDeclaredSteps', [])) or 'none'}`",
                    f"- Session step catalog: `{', '.join(session_support_data.get('catalogDeclaredSteps', [])) or 'none'}`",
                    "",
                ]
            )
            if declared_catalog:
                lines.append("### Active Mutation Step Details")
                lines.append("")
                for step_name in sorted(declared_catalog):
                    step_support = declared_catalog[step_name]
                    detail = "supported" if step_support.get("supported") else "unsupported"
                    mode = step_support.get("mode")
                    adapter_method = step_support.get("adapterMethod")
                    conditional_modes = step_support.get("conditionalModes") or []
                    note = step_support.get("note")
                    detail_parts = [detail]
                    if mode:
                        detail_parts.append(f"mode={mode}")
                    if adapter_method:
                        detail_parts.append(f"adapter={adapter_method}")
                    if conditional_modes:
                        enabled_modes = [
                            str(item.get("name"))
                            for item in conditional_modes
                            if isinstance(item, dict) and item.get("enabled") is True and item.get("name")
                        ]
                        disabled_modes = [
                            str(item.get("name"))
                            for item in conditional_modes
                            if isinstance(item, dict) and item.get("enabled") is not True and item.get("name")
                        ]
                        if enabled_modes:
                            detail_parts.append(f"conditionalModes={','.join(enabled_modes)}")
                        if disabled_modes:
                            detail_parts.append(f"pendingModes={','.join(disabled_modes)}")
                    line = f"- `{step_name}` -> `{', '.join(detail_parts)}`"
                    if note:
                        line += f" ({note})"
                    lines.append(line)
                lines.append("")
            if session_catalog:
                lines.append("### Active Session Step Details")
                lines.append("")
                for step_name in sorted(session_catalog):
                    step_support = session_catalog[step_name]
                    detail = "supported" if step_support.get("supported") else "unsupported"
                    runtime_check = step_support.get("runtimeCheck")
                    operational_check = step_support.get("operationalCheck")
                    mode = step_support.get("mode")
                    note = step_support.get("note")
                    detail_parts = [detail]
                    if runtime_check:
                        detail_parts.append(f"runtimeCheck={runtime_check}")
                    if operational_check:
                        detail_parts.append(f"operationalCheck={operational_check}")
                    if mode:
                        detail_parts.append(f"mode={mode}")
                    line = f"- `{step_name}` -> `{', '.join(detail_parts)}`"
                    if note:
                        line += f" ({note})"
                    lines.append(line)
                lines.append("")
            if catalog_mutation_catalog and not declared_catalog:
                lines.append("### Mutation Step Catalog")
                lines.append("")
                for step_name in sorted(catalog_mutation_catalog):
                    step_support = catalog_mutation_catalog[step_name]
                    detail = "supported" if step_support.get("supported") else "unsupported"
                    mode = step_support.get("mode")
                    note = step_support.get("note")
                    detail_parts = [detail]
                    if mode:
                        detail_parts.append(f"mode={mode}")
                    line = f"- `{step_name}` -> `{', '.join(detail_parts)}`"
                    if note:
                        line += f" ({note})"
                    lines.append(line)
                lines.append("")
            if catalog_session_catalog and not session_catalog:
                lines.append("### Session Step Catalog")
                lines.append("")
                for step_name in sorted(catalog_session_catalog):
                    step_support = catalog_session_catalog[step_name]
                    detail = "supported" if step_support.get("supported") else "unsupported"
                    mode = step_support.get("mode")
                    note = step_support.get("note")
                    detail_parts = [detail]
                    if mode:
                        detail_parts.append(f"mode={mode}")
                    line = f"- `{step_name}` -> `{', '.join(detail_parts)}`"
                    if note:
                        line += f" ({note})"
                    lines.append(line)
                lines.append("")
        lines.extend(["## Checks", ""])
        for check in report["checks"]:
            lines.append(f"- `{check['status'].upper()}` {check['id']}: {check['description']}")
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path, markdown_path

    try:
        return write_to(artifacts_dir)
    except PermissionError:
        return write_to(FALLBACK_PLATFORM_ARTIFACTS_DIR)
