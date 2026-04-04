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


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)
PLATFORM_ARTIFACTS_DIR = ROOT / os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform")
RUNTIME_ARTIFACTS_FALLBACK_DIR = ROOT / os.environ.get(
    "PLATFORM_RUNTIME_FALLBACK_ARTIFACTS_DIR",
    "artifacts/platform-local",
)

PROM = os.environ.get("PROM_URL", "http://127.0.0.1:9090")
GRAFANA = os.environ.get("GRAFANA_URL", "http://127.0.0.1:3000")
LOKI = os.environ.get("LOKI_URL", "http://127.0.0.1:3100")
JAEGER = os.environ.get("JAEGER_URL", "http://127.0.0.1:16686")
LIDER_API = os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082")
LIDER_UI = os.environ.get("LIDER_UI_URL", "http://127.0.0.1:3001")
XMPP_API = os.environ.get("XMPP_API_URL", "http://127.0.0.1:15280/api")


def active_runtime_profile() -> str:
    return os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fidelity")


def profile_requires_observability() -> bool:
    return active_runtime_profile() == "dev-fidelity"


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

    if profile_requires_observability():
        prom_ready = http_get(f"{PROM}/-/ready")
        checks.append(("prometheus ready", bool(prom_ready and prom_ready.status_code == 200)))

        grafana_health = http_get(f"{GRAFANA}/api/health")
        checks.append(("grafana health", bool(grafana_health and grafana_health.status_code == 200)))

        loki_ready = http_get(f"{LOKI}/ready")
        checks.append(("loki ready", bool(loki_ready and loki_ready.status_code in (200, 503))))

    return checks


def check_observability():
    if not profile_requires_observability():
        return []

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


def load_platform_artifact(name: str):
    path = PLATFORM_ARTIFACTS_DIR / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_runtime_artifact(name: str):
    for base in (PLATFORM_ARTIFACTS_DIR, RUNTIME_ARTIFACTS_FALLBACK_DIR):
        path = base / name
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def check_release_signals():
    checks = []
    run_manifest = load_platform_artifact("run-manifest.json")
    verdict = load_platform_artifact("registration-verdict.json")
    baseline_diff = load_platform_artifact("baseline-diff.json")
    evidence_report = load_platform_artifact("registration-evidence-report.json")

    checks.append(("run manifest present", run_manifest is not None))
    checks.append(("registration verdict present", verdict is not None))
    checks.append(("baseline diff present", baseline_diff is not None))
    checks.append(("registration evidence report present", evidence_report is not None))

    if verdict is not None:
        checks.append(("registration verdict pass", verdict.get("status") == "pass"))

    if baseline_diff is not None:
        checks.append(("baseline diff pass", baseline_diff.get("status") == "pass"))

    if evidence_report is not None:
        checks.append(("registration evidence valid", evidence_report.get("valid") is True))

    return checks


def check_runtime_signals():
    checks = []
    runtime_core = load_runtime_artifact("runtime-core-report.json")
    runtime_operational = load_runtime_artifact("runtime-operational-report.json")

    checks.append(("runtime core report present", runtime_core is not None))
    if runtime_core is not None:
        checks.append(("runtime core pass", runtime_core.get("status") == "pass"))

    if profile_requires_observability():
        checks.append(("runtime operational report present", runtime_operational is not None))
        if runtime_operational is not None:
            checks.append(("runtime operational pass", runtime_operational.get("status") == "pass"))

    return checks


def build_markdown(service_checks, obs_checks, release_checks, runtime_checks=None):
    runtime_checks = runtime_checks or []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = [
        "# Quality Report",
        "",
        f"- Generated at: `{now}`",
        f"- Workspace: `{ROOT}`",
        f"- Runtime profile: `{active_runtime_profile()}`",
        "",
        "## Service Checks",
        "",
    ]
    for name, ok in service_checks:
        lines.append(f"- `{status_line(ok)}` {name}")

    lines.extend(["", "## Observability Checks", ""])
    for name, ok in obs_checks:
        lines.append(f"- `{status_line(ok)}` {name}")

    lines.extend(["", "## Runtime Checks", ""])
    for name, ok in runtime_checks:
        lines.append(f"- `{status_line(ok)}` {name}")

    lines.extend(["", "## Release Checks", ""])
    for name, ok in release_checks:
        lines.append(f"- `{status_line(ok)}` {name}")

    total = len(service_checks) + len(obs_checks) + len(runtime_checks) + len(release_checks)
    passed = sum(1 for _, ok in service_checks + obs_checks + runtime_checks + release_checks if ok)
    lines.extend(["", "## Summary", "", f"- Passed: `{passed}/{total}`"])
    return "\n".join(lines) + "\n"


def main():
    service_checks = check_services()
    obs_checks = check_observability()
    runtime_checks = check_runtime_signals()
    release_checks = check_release_signals()

    markdown = build_markdown(service_checks, obs_checks, release_checks, runtime_checks)
    (ARTIFACTS_DIR / "quality-report.md").write_text(markdown, encoding="utf-8")
    (ARTIFACTS_DIR / "quality-report.json").write_text(
        json.dumps(
            {
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "service_checks": service_checks,
                "observability_checks": obs_checks,
                "runtime_checks": runtime_checks,
                "release_checks": release_checks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(markdown)


if __name__ == "__main__":
    main()
