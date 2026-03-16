from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.ldap_schema_adapter import LdapSchemaAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from platform_runtime.registration import RegistrationCollector
from platform_runtime.runtime_db import RuntimeDbAdapter


BOOTSTRAP_MANIFEST_PATH = Path("platform/bootstrap/bootstrap-manifest.yaml")
RUNTIME_READINESS_CONTRACT_PATH = Path("platform/contracts/runtime-readiness.yaml")
DEFAULT_PLATFORM_ARTIFACTS_DIR = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))
FALLBACK_PLATFORM_ARTIFACTS_DIR = Path(
    os.environ.get("PLATFORM_RUNTIME_FALLBACK_ARTIFACTS_DIR", "artifacts/platform-local")
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _project_name() -> str:
    return os.environ.get("PROJECT_NAME", "liderahenk-test")


def _profile_name(profile: str | None = None) -> str:
    return profile or os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fast")


def _http_get(url: str, timeout: int = 5, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def _http_post(url: str, timeout: int = 5, **kwargs):
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def _port_open(host: str, port: int, timeout: int = 3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _compose_stack(profile: str) -> list[str]:
    bootstrap = _read_yaml(BOOTSTRAP_MANIFEST_PATH)
    return bootstrap["runtime_profiles"][profile]["compose_stack"]


def _compose_ps(profile: str) -> list[dict[str, Any]]:
    compose_stack = _compose_stack(profile)
    cmd = ["docker", "compose", "--env-file", ".env"]
    for path in compose_stack:
        cmd.extend(["-f", path])
    cmd.extend(["-p", _project_name(), "ps", "--all", "--format", "json"])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(Path.cwd()),
        timeout=30,
    )
    if result.returncode != 0:
        return []
    containers: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return containers


def _containers_by_service(containers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in containers:
        service = entry.get("Service") or entry.get("Name")
        if not service:
            continue
        grouped.setdefault(str(service), []).append(entry)
    return grouped


def _normalize_state(container: dict[str, Any]) -> str:
    state = str(container.get("State") or "").lower()
    status = str(container.get("Status") or "")
    if state == "running":
        return "running"
    if state == "exited" and "Exited (0)" in status:
        return "completed"
    return state or "unknown"


def _build_check(
    *,
    check_id: str,
    category: str,
    description: str,
    passed: bool,
    actual: Any = None,
    expected: Any = None,
    details: Any = None,
) -> dict[str, Any]:
    payload = {
        "id": check_id,
        "category": category,
        "description": description,
        "status": "pass" if passed else "fail",
    }
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if details is not None:
        payload["details"] = details
    return payload


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for item in checks if item["status"] == "pass")
    failed = len(checks) - passed
    return {
        "totalChecks": len(checks),
        "passedChecks": passed,
        "failedChecks": failed,
    }


def _service_state_report(profile: str, expected_agents: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contract = _read_yaml(RUNTIME_READINESS_CONTRACT_PATH)
    grouped = _containers_by_service(_compose_ps(profile))
    checks: list[dict[str, Any]] = []
    services_report: dict[str, Any] = {}
    required_groups = contract["runtime_profiles"][profile]["required_service_groups"]
    for group_name in required_groups:
        for service_name in contract["service_groups"][group_name]:
            expectation = contract["service_expectations"][service_name]
            instances = grouped.get(service_name, [])
            normalized_states = [_normalize_state(item) for item in instances]
            services_report[service_name] = {
                "instanceCount": len(instances),
                "states": normalized_states,
            }
            accepted_states = expectation["accepted_states"]
            if expectation["kind"] == "scaled":
                passed = len(instances) == expected_agents and instances and all(
                    state in accepted_states for state in normalized_states
                )
                expected = {"instances": expected_agents, "states": accepted_states}
                actual = {"instances": len(instances), "states": normalized_states}
            else:
                passed = bool(instances) and all(state in accepted_states for state in normalized_states)
                expected = accepted_states
                actual = normalized_states
            checks.append(
                _build_check(
                    check_id=f"service:{service_name}",
                    category="docker",
                    description=f"{service_name} service readiness",
                    passed=passed,
                    actual=actual,
                    expected=expected,
                )
            )
    return checks, services_report


def _core_connectivity_checks(profile: str) -> list[dict[str, Any]]:
    contract = _read_yaml(RUNTIME_READINESS_CONTRACT_PATH)
    checks: list[dict[str, Any]] = []
    ports = contract["runtime_profiles"][profile]["required_ports"]
    for port in ports:
        checks.append(
            _build_check(
                check_id=f"port:{port}",
                category="network",
                description=f"Port {port} is reachable from localhost",
                passed=_port_open("127.0.0.1", int(port)),
                actual=port,
                expected="open",
            )
        )

    api_health = _http_get(os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082") + "/actuator/health")
    checks.append(
        _build_check(
            check_id="liderapi_health",
            category="service",
            description="liderapi actuator health endpoint responds",
            passed=api_health is not None and api_health.status_code in (200, 401),
            actual=api_health.status_code if api_health else None,
            expected="200 or 401",
        )
    )

    api = LiderApiAdapter(
        base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )
    checks.append(
        _build_check(
            check_id="liderapi_auth",
            category="service",
            description="liderapi JWT authentication works",
            passed=api.is_authenticated,
            actual=api.is_authenticated,
            expected=True,
        )
    )

    ui_response = _http_get(os.environ.get("LIDER_UI_URL", "http://127.0.0.1:3001"))
    checks.append(
        _build_check(
            check_id="liderui_http",
            category="service",
            description="lider-ui root page responds",
            passed=bool(ui_response and ui_response.status_code == 200),
            actual=ui_response.status_code if ui_response else None,
            expected=200,
        )
    )

    ldap = LdapSchemaAdapter(
        host=os.environ.get("LDAP_HOST", "127.0.0.1"),
        port=int(os.environ.get("LDAP_PORT", "1389")),
        base_dn=os.environ.get("LDAP_BASE_DN", "dc=liderahenk,dc=org"),
        admin_dn=f"cn={os.environ.get('LDAP_ADMIN_USERNAME', 'admin')},{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
        admin_pass=os.environ.get("LDAP_ADMIN_PASSWORD", "DEGISTIR"),
    )
    ldap_ok = ldap.connection_healthy()
    checks.append(
        _build_check(
            check_id="ldap_health",
            category="service",
            description="LDAP bind and search are healthy",
            passed=ldap_ok,
            actual=ldap_ok,
            expected=True,
        )
    )

    runtime_db = RuntimeDbAdapter.from_env()
    mariadb_ok = runtime_db.connection_healthy()
    checks.append(
        _build_check(
            check_id="mariadb_health",
            category="service",
            description="MariaDB runtime state is reachable",
            passed=mariadb_ok,
            actual=mariadb_ok,
            expected=True,
        )
    )

    xmpp = XmppMessageAdapter(
        api_url=os.environ.get("XMPP_API_URL", "http://127.0.0.1:15280/api"),
        domain=os.environ.get("XMPP_DOMAIN", "liderahenk.org"),
    )
    xmpp_ok = xmpp.api_healthy()
    registered_count = xmpp.get_registered_count() if xmpp_ok else None
    checks.append(
        _build_check(
            check_id="ejabberd_api",
            category="service",
            description="ejabberd HTTP API responds",
            passed=xmpp_ok,
            actual=registered_count,
            expected="registered user list available",
        )
    )
    return checks


def collect_runtime_core_report(profile: str | None = None) -> dict[str, Any]:
    resolved_profile = _profile_name(profile)
    expected_agents = int(os.environ.get("AHENK_COUNT", "1"))
    started_at = _utc_now()
    service_checks, services_report = _service_state_report(resolved_profile, expected_agents)
    connectivity_checks = _core_connectivity_checks(resolved_profile)
    checks = service_checks + connectivity_checks
    summary = _summarize_checks(checks)
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
    }


def _registration_parity_check(expected_agents: int) -> dict[str, Any]:
    collector = RegistrationCollector.from_env()
    snapshot = collector.collect_snapshot()
    verdict = collector.evaluate_snapshot(snapshot)
    parity_ok = verdict["status"] == "pass" and snapshot["expectedAgents"] == expected_agents
    details = {
        "failedChecks": verdict["failedChecks"],
        "surfaces": verdict["surfaces"],
        "taxonomy": verdict["taxonomy"],
    }
    return _build_check(
        check_id="registration_parity",
        category="registration",
        description="Runtime registration parity matches expected agent count",
        passed=parity_ok,
        actual=verdict["surfaces"],
        expected={"expectedAgents": expected_agents},
        details=details,
    )


def _run_policy_roundtrip_check() -> dict[str, Any]:
    api = LiderApiAdapter(
        base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )
    def find_first_agent(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
        for node in nodes or []:
            if node.get("type") in {"AHENK", "WINDOWS_AHENK"}:
                return node
            child = find_first_agent(node.get("childEntries", []) or node.get("children", []))
            if child:
                return child
        return None

    tree = api.get_computer_tree()
    entry = find_first_agent(tree)
    if not entry:
        return _build_check(
            check_id="policy_roundtrip",
            category="operational",
            description="Policy roundtrip can target at least one agent group",
            passed=False,
            details="No computer tree root entry available",
        )

    token = uuid.uuid4().hex[:8]
    group_name = f"rt-group-{token}"
    profile_label = f"rt-profile-{token}"
    policy_label = f"rt-policy-{token}"
    group = api.create_computer_group(
        group_name=group_name,
        checked_entries=[entry],
        selected_ou_dn=f"ou=Agent,ou=Groups,{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
    )
    profile = api.create_script_profile(
        label=profile_label,
        description="Runtime readiness policy roundtrip",
        script_contents="#!/bin/bash\nprintf 'runtime-policy-roundtrip\\n'",
    )
    policy = api.create_policy(
        label=policy_label,
        description="Runtime readiness policy",
        profiles=[profile],
        active=False,
    )
    response = api.execute_policy(policy["id"], group["distinguishedName"], "GROUP")
    return _build_check(
        check_id="policy_roundtrip",
        category="operational",
        description="Policy roundtrip can create group/profile/policy and execute it",
        passed=response.status_code == 200,
        actual=response.status_code,
        expected=200,
        details={
            "groupDn": group.get("distinguishedName"),
            "profileLabel": profile.get("label"),
            "policyLabel": policy.get("label"),
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
    return _build_check(
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


def _prom_query(expr: str):
    response = _http_get(
        f"{os.environ.get('PROM_URL', 'http://127.0.0.1:9090')}/api/v1/query",
        params={"query": expr},
        timeout=10,
    )
    if not response or response.status_code != 200:
        return None
    payload = response.json()
    if payload.get("status") != "success":
        return None
    return payload.get("data", {}).get("result", [])


def _observability_checks() -> list[dict[str, Any]]:
    contract = _read_yaml(RUNTIME_READINESS_CONTRACT_PATH)
    checks: list[dict[str, Any]] = []
    prom_url = os.environ.get("PROM_URL", "http://127.0.0.1:9090")
    grafana_url = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
    loki_url = os.environ.get("LOKI_URL", "http://127.0.0.1:3100")
    auth = ("admin", os.environ.get("GRAFANA_ADMIN_PASS", "admin"))

    expected_jobs = contract["observability"]["expected_jobs"]
    targets_response = _http_get(f"{prom_url}/api/v1/targets")
    target_payload = targets_response.json() if targets_response and targets_response.status_code == 200 else {}
    active_targets = target_payload.get("data", {}).get("activeTargets", [])
    target_jobs = {target.get("labels", {}).get("job"): target.get("health") for target in active_targets}
    missing_jobs = [job for job in expected_jobs if target_jobs.get(job) != "up"]
    checks.append(
        _build_check(
            check_id="observability_targets",
            category="observability",
            description="Prometheus targets for the runtime stack are healthy",
            passed=not missing_jobs,
            actual=target_jobs,
            expected={job: "up" for job in expected_jobs},
            details={"missingJobs": missing_jobs},
        )
    )

    dashboards = contract["observability"]["expected_dashboards"]
    found_dashboards = {}
    missing_dashboards = []
    for uid in dashboards:
        response = _http_get(f"{grafana_url}/api/dashboards/uid/{uid}", auth=auth)
        if response and response.status_code == 200:
            found_dashboards[uid] = True
        else:
            found_dashboards[uid] = False
            missing_dashboards.append(uid)
    checks.append(
        _build_check(
            check_id="grafana_dashboards",
            category="observability",
            description="Grafana dashboards are provisioned",
            passed=not missing_dashboards,
            actual=found_dashboards,
            expected={uid: True for uid in dashboards},
            details={"missingDashboards": missing_dashboards},
        )
    )

    loki_response = _http_get(
        f"{loki_url}/loki/api/v1/query",
        params={
            "query": "sum(count_over_time({signal=\"logs\",compose_service=~\"liderapi|lider-core|ejabberd|ahenk\"}[5m]))"
        },
        timeout=10,
    )
    loki_count = 0.0
    if loki_response and loki_response.status_code == 200:
        for item in loki_response.json().get("data", {}).get("result", []):
            loki_count = max(loki_count, float(item.get("value", [0, "0"])[1]))
    checks.append(
        _build_check(
            check_id="loki_platform_logs",
            category="observability",
            description="Loki receives platform logs from runtime services",
            passed=loki_count > 0,
            actual=loki_count,
            expected="> 0",
        )
    )

    probe_metrics = _prom_query("lider_probe_success")
    checks.append(
        _build_check(
            check_id="probe_metrics",
            category="observability",
            description="Prometheus receives runtime probe metrics",
            passed=bool(probe_metrics),
            actual=len(probe_metrics or []),
            expected="> 0 series",
        )
    )
    return checks


def collect_runtime_operational_report(profile: str | None = None) -> dict[str, Any]:
    resolved_profile = _profile_name(profile)
    expected_agents = int(os.environ.get("AHENK_COUNT", "1"))
    checks: list[dict[str, Any]] = []
    checks.append(_registration_parity_check(expected_agents))
    checks.append(_run_policy_roundtrip_check())
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
            check_id="ui_script_task_dispatch",
            description="Script task flow is reachable from UI and dispatches from backend",
            pytest_paths=["tests/e2e/specs/management/test_send_task.py"],
            timeout=180,
        )
    )
    checks.extend(_observability_checks())
    summary = _summarize_checks(checks)
    return {
        "schemaVersion": 1,
        "reportType": "runtime-operational",
        "status": "pass" if summary["failedChecks"] == 0 else "fail",
        "profile": resolved_profile,
        "expectedAgents": expected_agents,
        "generatedAt": _utc_now(),
        "checks": checks,
        "summary": summary,
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
            "## Checks",
            "",
        ]
        for check in report["checks"]:
            lines.append(f"- `{check['status'].upper()}` {check['id']}: {check['description']}")
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return json_path, markdown_path

    try:
        return write_to(artifacts_dir)
    except PermissionError:
        return write_to(FALLBACK_PLATFORM_ARTIFACTS_DIR)
