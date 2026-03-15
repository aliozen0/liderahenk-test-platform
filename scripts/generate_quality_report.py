#!/usr/bin/env python3
"""
Generate a lightweight quality report for local runs and CI artifacts.

The report focuses on release evidence surfaces without touching core
business logic:
- service availability
- observability availability
- evidence metrics/logs/traces
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

PROM = os.environ.get("PROM_URL", "http://127.0.0.1:9090")
GRAFANA = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
LOKI = os.environ.get("LOKI_URL", "http://127.0.0.1:3100")
JAEGER = os.environ.get("JAEGER_URL", "http://127.0.0.1:16686")
LIDER_API = os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082")
LIDER_UI = os.environ.get("LIDER_UI_URL", "http://127.0.0.1:3001")
XMPP_API = os.environ.get("XMPP_API_URL", "http://127.0.0.1:15280/api")


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


def status_line(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def prom_query(expr: str):
    response = http_get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=10)
    if not response or response.status_code != 200:
        return None
    payload = response.json()
    if payload.get("status") != "success":
        return None
    return payload.get("data", {}).get("result", [])


def check_services():
    checks = []

    api_health = http_get(f"{LIDER_API}/actuator/health")
    checks.append(("liderapi health", bool(api_health and api_health.status_code in (200, 401))))

    ui_health = http_get(LIDER_UI)
    checks.append(("lider-ui http", bool(ui_health and ui_health.status_code == 200)))

    xmpp_users = http_post(f"{XMPP_API}/registered_users", json={"host": os.environ.get("XMPP_DOMAIN", "liderahenk.org")})
    checks.append(("ejabberd api", bool(xmpp_users and xmpp_users.status_code == 200)))

    prom_ready = http_get(f"{PROM}/-/ready")
    checks.append(("prometheus ready", bool(prom_ready and prom_ready.status_code == 200)))

    grafana_health = http_get(f"{GRAFANA}/api/health")
    checks.append(("grafana health", bool(grafana_health and grafana_health.status_code == 200)))

    loki_ready = http_get(f"{LOKI}/ready")
    checks.append(("loki ready", bool(loki_ready and loki_ready.status_code in (200, 503))))

    return checks


def check_observability():
    checks = []

    probe_metrics = prom_query("lider_probe_success")
    checks.append(("synthetic probe metrics", bool(probe_metrics)))

    recording_metrics = prom_query("lider:probe_success_ratio5m")
    checks.append(("recording rules output", bool(recording_metrics)))

    logs = prom_query("sum(up{job=~\"alloy|platform-exporter|otel-collector\"})")
    checks.append(("telemetry jobs visible in Prometheus", bool(logs)))

    loki_logs = http_get(
        f"{LOKI}/loki/api/v1/query",
        params={"query": "sum(count_over_time({signal=\"logs\"}[5m]))"},
        timeout=10,
    )
    loki_ok = False
    if loki_logs and loki_logs.status_code == 200:
        results = loki_logs.json().get("data", {}).get("result", [])
        loki_ok = any(float(item.get("value", [0, "0"])[1]) > 0 for item in results)
    checks.append(("loki evidence logs", loki_ok))

    jaeger_services = http_get(f"{JAEGER}/api/services", timeout=5)
    jaeger_ok = bool(jaeger_services and jaeger_services.status_code == 200)
    checks.append(("jaeger available", jaeger_ok))

    if jaeger_ok:
        service_names = jaeger_services.json().get("data", [])
        checks.append(("jaeger traced service found", any(name in service_names for name in ("liderapi", "lider-core"))))

    return checks


def build_markdown(service_checks, obs_checks):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = [
        "# Quality Report",
        "",
        f"- Generated at: `{now}`",
        f"- Workspace: `{ROOT}`",
        "",
        "## Service Checks",
        "",
    ]
    for name, ok in service_checks:
        lines.append(f"- `{status_line(ok)}` {name}")

    lines.extend(["", "## Observability Checks", ""])
    for name, ok in obs_checks:
        lines.append(f"- `{status_line(ok)}` {name}")

    total = len(service_checks) + len(obs_checks)
    passed = sum(1 for _, ok in service_checks + obs_checks if ok)
    lines.extend(["", "## Summary", "", f"- Passed: `{passed}/{total}`"])
    return "\n".join(lines) + "\n"


def main():
    service_checks = check_services()
    obs_checks = check_observability()

    markdown = build_markdown(service_checks, obs_checks)
    (ARTIFACTS_DIR / "quality-report.md").write_text(markdown, encoding="utf-8")
    (ARTIFACTS_DIR / "quality-report.json").write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "service_checks": service_checks,
                "observability_checks": obs_checks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(markdown)


if __name__ == "__main__":
    main()
