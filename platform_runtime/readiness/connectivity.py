"""Network connectivity and service health checks."""
from __future__ import annotations

import os
import socket
from typing import Any

import requests

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.ldap_schema_adapter import LdapSchemaAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from platform_runtime.runtime_db import RuntimeDbAdapter

from .checks import build_check


def http_get(url: str, timeout: int = 5, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def http_post(url: str, timeout: int = 5, **kwargs):
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def port_open(host: str, port: int, timeout: int = 3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _runtime_readiness_contract() -> dict[str, Any]:
    import yaml
    from pathlib import Path

    contract_path = Path("platform/contracts/runtime-readiness.yaml")
    with contract_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def prom_query(expr: str):
    response = http_get(
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


def core_connectivity_checks(profile: str) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    api_health = http_get(os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082") + "/actuator/health")
    checks.append(
        build_check(
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
        build_check(
            check_id="liderapi_auth",
            category="service",
            description="liderapi JWT authentication works",
            passed=api.is_authenticated,
            actual=api.is_authenticated,
            expected=True,
        )
    )

    ui_response = http_get(os.environ.get("LIDER_UI_URL", "http://127.0.0.1:3001"))
    checks.append(
        build_check(
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
        build_check(
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
        build_check(
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
        build_check(
            check_id="ejabberd_api",
            category="service",
            description="ejabberd HTTP API responds",
            passed=xmpp_ok,
            actual=registered_count,
            expected="registered user list available",
        )
    )
    return checks


def host_port_checks(profile: str) -> list[dict[str, Any]]:
    contract = _runtime_readiness_contract()
    checks: list[dict[str, Any]] = []
    ports = contract["runtime_profiles"][profile]["required_ports"]
    for p in ports:
        checks.append(
            build_check(
                check_id=f"port:{p}",
                category="diagnostic",
                description=f"Port {p} is reachable from localhost",
                passed=port_open("127.0.0.1", int(p)),
                actual=p,
                expected="open",
            )
        )
    return checks


def observability_checks() -> list[dict[str, Any]]:
    import yaml
    from pathlib import Path

    contract_path = Path("platform/contracts/runtime-readiness.yaml")
    with contract_path.open("r", encoding="utf-8") as handle:
        contract = yaml.safe_load(handle)

    checks: list[dict[str, Any]] = []
    prom_url = os.environ.get("PROM_URL", "http://127.0.0.1:9090")
    grafana_url = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
    loki_url = os.environ.get("LOKI_URL", "http://127.0.0.1:3100")
    auth = ("admin", os.environ.get("GRAFANA_ADMIN_PASS", "admin"))

    expected_jobs = contract["observability"]["expected_jobs"]
    targets_response = http_get(f"{prom_url}/api/v1/targets")
    target_payload = targets_response.json() if targets_response and targets_response.status_code == 200 else {}
    active_targets = target_payload.get("data", {}).get("activeTargets", [])
    target_jobs = {target.get("labels", {}).get("job"): target.get("health") for target in active_targets}
    missing_jobs = [job for job in expected_jobs if target_jobs.get(job) != "up"]
    checks.append(
        build_check(
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
        response = http_get(f"{grafana_url}/api/dashboards/uid/{uid}", auth=auth)
        if response and response.status_code == 200:
            found_dashboards[uid] = True
        else:
            found_dashboards[uid] = False
            missing_dashboards.append(uid)
    checks.append(
        build_check(
            check_id="grafana_dashboards",
            category="observability",
            description="Grafana dashboards are provisioned",
            passed=not missing_dashboards,
            actual=found_dashboards,
            expected={uid: True for uid in dashboards},
            details={"missingDashboards": missing_dashboards},
        )
    )

    loki_response = http_get(
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
        build_check(
            check_id="loki_platform_logs",
            category="observability",
            description="Loki receives platform logs from runtime services",
            passed=loki_count > 0,
            actual=loki_count,
            expected="> 0",
        )
    )

    probe_metrics = prom_query("lider_probe_success")
    checks.append(
        build_check(
            check_id="probe_metrics",
            category="observability",
            description="Prometheus receives runtime probe metrics",
            passed=bool(probe_metrics),
            actual=len(probe_metrics or []),
            expected="> 0 series",
        )
    )
    return checks
