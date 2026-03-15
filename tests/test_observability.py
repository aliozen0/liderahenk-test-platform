"""
Observability tests for the LiderAhenk dev laboratory.

These checks validate the telemetry pipeline, Grafana provisioning and
read-only evidence metrics without mutating the platform state.
"""

from __future__ import annotations

import time

import pytest
import requests


PROM = "http://127.0.0.1:9090"
GRAFANA = "http://127.0.0.1:3000"
LOKI = "http://127.0.0.1:3100"
GRAFANA_AUTH = ("admin", "admin")

EXPECTED_JOBS = [
    "cadvisor",
    "mariadb",
    "liderapi",
    "ejabberd",
    "lider-core",
    "alloy",
    "platform-exporter",
    "otel-collector",
]

EXPECTED_DASHBOARDS = [
    "liderahenk-slo",
    "liderahenk-pipeline-health",
    "liderahenk-workflow-health",
]


def http_get(url, timeout=5, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def prom_query(expr, timeout=5):
    response = http_get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=timeout)
    assert response and response.status_code == 200, f"Prometheus query failed: {expr}"
    payload = response.json()
    assert payload.get("status") == "success", f"Prometheus query unsuccessful: {expr}"
    return payload.get("data", {}).get("result", [])


def wait_for(predicate, timeout=90, interval=5, message="condition not met"):
    started = time.time()
    while time.time() - started < timeout:
        if predicate():
            return
        time.sleep(interval)
    pytest.fail(message)


def get_targets():
    response = http_get(f"{PROM}/api/v1/targets")
    assert response and response.status_code == 200, "Prometheus targets API unavailable"
    return response.json().get("data", {}).get("activeTargets", [])


class TestPrometheus:
    def test_prometheus_ready(self):
        response = http_get(f"{PROM}/-/ready")
        assert response and response.status_code == 200, "Prometheus unreachable"

    def test_prometheus_config_loaded(self):
        response = http_get(f"{PROM}/api/v1/status/config")
        assert response and response.status_code == 200
        assert response.json().get("status") == "success"

    def test_prometheus_targets_exist(self):
        targets = get_targets()
        assert targets, "No active scrape targets found"

    @pytest.mark.parametrize("job_name", EXPECTED_JOBS)
    def test_prometheus_target_configured(self, job_name):
        targets = get_targets()
        job_names = [target.get("labels", {}).get("job", "") for target in targets]
        assert job_name in job_names, f"Missing job '{job_name}'. Found: {job_names}"

    @pytest.mark.parametrize("job_name", EXPECTED_JOBS)
    def test_prometheus_target_health(self, job_name):
        def job_is_up():
            for target in get_targets():
                if target.get("labels", {}).get("job") == job_name:
                    return target.get("health") == "up"
            return False

        wait_for(
            job_is_up,
            timeout=120,
            interval=5,
            message=f"Prometheus job '{job_name}' did not become healthy",
        )

    def test_recording_rules_loaded(self):
        response = http_get(f"{PROM}/api/v1/rules")
        assert response and response.status_code == 200
        groups = response.json().get("data", {}).get("groups", [])
        group_names = {group.get("name") for group in groups}
        assert "liderahenk_slo" in group_names
        assert "liderahenk_recordings" in group_names

    def test_probe_metrics_exist(self):
        wait_for(
            lambda: len(prom_query("lider_probe_success")) > 0,
            timeout=120,
            interval=5,
            message="lider_probe_success metrics were not produced",
        )

    def test_recording_metrics_exist(self):
        wait_for(
            lambda: len(prom_query("lider:probe_success_ratio5m")) > 0,
            timeout=120,
            interval=5,
            message="recording rule lider:probe_success_ratio5m missing",
        )


class TestGrafana:
    def test_grafana_health(self):
        response = http_get(f"{GRAFANA}/api/health")
        assert response and response.status_code == 200, "Grafana unreachable"

    def test_grafana_datasources_provisioned(self):
        response = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert response and response.status_code == 200
        datasources = response.json()
        assert datasources, "No Grafana datasources provisioned"

    def test_grafana_datasource_uids(self):
        response = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert response and response.status_code == 200
        datasources = response.json()
        datasource_uids = {entry.get("uid"): entry.get("type") for entry in datasources}
        assert datasource_uids.get("prometheus") == "prometheus"
        assert datasource_uids.get("loki") == "loki"

    @pytest.mark.parametrize("dashboard_uid", EXPECTED_DASHBOARDS)
    def test_grafana_dashboard_loaded(self, dashboard_uid):
        response = http_get(f"{GRAFANA}/api/dashboards/uid/{dashboard_uid}", auth=GRAFANA_AUTH)
        assert response and response.status_code == 200, f"Dashboard not found: {dashboard_uid}"

    def test_grafana_dashboard_datasource_references(self):
        datasource_response = http_get(f"{GRAFANA}/api/datasources", auth=GRAFANA_AUTH)
        assert datasource_response and datasource_response.status_code == 200
        available_uids = {entry.get("uid") for entry in datasource_response.json()}

        broken = []
        for dashboard_uid in EXPECTED_DASHBOARDS:
            response = http_get(f"{GRAFANA}/api/dashboards/uid/{dashboard_uid}", auth=GRAFANA_AUTH)
            assert response and response.status_code == 200
            panels = response.json().get("dashboard", {}).get("panels", [])
            for panel in panels:
                datasource = panel.get("datasource", {})
                if isinstance(datasource, dict):
                    uid = datasource.get("uid")
                    if uid and uid not in available_uids:
                        broken.append(f"{dashboard_uid}:{panel.get('title', '?')} -> {uid}")

        assert not broken, f"Broken datasource references detected: {broken}"


class TestLoki:
    def test_loki_ready(self):
        response = http_get(f"{LOKI}/ready")
        assert response and response.status_code == 200, "Loki unreachable"

    def test_loki_query_possible(self):
        response = http_get(f"{LOKI}/loki/api/v1/labels")
        assert response is not None and response.status_code == 200

    def test_loki_has_platform_logs(self):
        def logs_present():
            response = http_get(
                f"{LOKI}/loki/api/v1/query",
                params={
                    "query": (
                        "sum(count_over_time("
                        "{signal=\"logs\",compose_service=~\"liderapi|lider-core|ejabberd|ahenk\"}[5m]))"
                    )
                },
                timeout=10,
            )
            if not response or response.status_code != 200:
                return False
            results = response.json().get("data", {}).get("result", [])
            return any(float(item.get("value", [0, "0"])[1]) > 0 for item in results)

        wait_for(
            logs_present,
            timeout=120,
            interval=5,
            message="Loki did not receive platform logs with Alloy labels",
        )
