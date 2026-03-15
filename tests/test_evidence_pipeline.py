"""
Evidence pipeline acceptance tests.

These tests validate that logs, metrics and (when tracing is enabled)
authenticated request traces can all be observed from the platform.
"""

from __future__ import annotations

import time

import pytest
import requests


PROM = "http://127.0.0.1:9090"
LOKI = "http://127.0.0.1:3100"
JAEGER = "http://127.0.0.1:16686"


def http_get(url, timeout=5, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def wait_for(predicate, timeout=120, interval=5):
    started = time.time()
    while time.time() - started < timeout:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def prom_query(expr):
    response = http_get(f"{PROM}/api/v1/query", params={"query": expr}, timeout=10)
    assert response and response.status_code == 200, f"Prometheus query failed: {expr}"
    payload = response.json()
    assert payload.get("status") == "success"
    return payload.get("data", {}).get("result", [])


class TestEvidencePipeline:
    def test_metrics_evidence_present(self):
        result = wait_for(lambda: prom_query("lider_probe_success"), timeout=120, interval=5)
        assert result, "Synthetic probe metrics not found"

        recording = wait_for(lambda: prom_query("lider:probe_success_ratio5m"), timeout=120, interval=5)
        assert recording, "Recording rule output not found"

    def test_logs_evidence_present(self):
        def query_logs():
            response = http_get(
                f"{LOKI}/loki/api/v1/query",
                params={"query": "sum(count_over_time({signal=\"logs\"}[5m]))"},
                timeout=10,
            )
            if not response or response.status_code != 200:
                return None
            results = response.json().get("data", {}).get("result", [])
            if any(float(item.get("value", [0, "0"])[1]) > 0 for item in results):
                return results
            return None

        assert wait_for(query_logs, timeout=120, interval=5), "Loki evidence logs not found"

    def test_trace_evidence_present_when_tracing_enabled(self):
        services_response = http_get(f"{JAEGER}/api/services", timeout=5)
        if not services_response or services_response.status_code != 200:
            pytest.skip("Jaeger is not running; trace evidence is only expected in dev-full")

        def traces_available():
            services = http_get(f"{JAEGER}/api/services", timeout=10)
            if not services or services.status_code != 200:
                return None

            service_names = services.json().get("data", [])
            target_service = None
            for name in ("liderapi", "lider-core"):
                if name in service_names:
                    target_service = name
                    break
            if target_service is None:
                return None

            traces = http_get(
                f"{JAEGER}/api/traces",
                params={"service": target_service, "limit": 20, "lookback": "1h"},
                timeout=10,
            )
            if not traces or traces.status_code != 200:
                return None

            data = traces.json().get("data", [])
            return data if data else None

        assert wait_for(traces_available, timeout=120, interval=5), (
            "Jaeger is running but no authenticated request traces were found"
        )
