from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "services" / "ahenk" / "liderapi_gate.py"
SPEC = importlib.util.spec_from_file_location("test_liderapi_gate_module", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
liderapi_gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(liderapi_gate)


def test_wait_for_liderapi_gate_requires_stable_successes(monkeypatch):
    responses = iter(
        [
            RuntimeError("signin returned HTTP 503"),
            "token-1",
            RuntimeError("protected probe returned HTTP 401"),
            "token-2",
            None,
            "token-3",
            None,
        ]
    )

    def fake_authenticate(**_kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    def fake_probe(**_kwargs):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    sleep_calls: list[int] = []
    monotonic_values = iter([0, 0, 1, 2, 3, 4, 5, 6])

    monkeypatch.setattr(liderapi_gate, "authenticate", fake_authenticate)
    monkeypatch.setattr(liderapi_gate, "probe_protected_endpoint", fake_probe)
    monkeypatch.setattr(liderapi_gate.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(liderapi_gate.time, "monotonic", lambda: next(monotonic_values))

    result = liderapi_gate.wait_for_liderapi_gate(
        base_url="http://liderapi:8080",
        username="lider-admin",
        password="secret",
        timeout_seconds=10,
        interval_seconds=0,
        stable_success_count=2,
    )

    assert result["status"] == "ready"
    assert result["attempts"] == 4
    assert result["stableSuccessCount"] == 2
    assert sleep_calls == [0, 0, 0]


def test_resolve_base_url_prefers_compose_service_ip(monkeypatch):
    monkeypatch.setattr(
        liderapi_gate,
        "_discover_compose_service_ip",
        lambda service_name: "172.19.0.15" if service_name == "liderapi" else None,
    )

    assert liderapi_gate.resolve_base_url("http://liderapi:8080") == "http://172.19.0.15:8080"
    assert liderapi_gate.resolve_base_url("http://localhost:8080") == "http://localhost:8080"


def test_wait_for_liderapi_gate_times_out(monkeypatch):
    monotonic_values = iter([0, 0, 1, 2, 3, 4, 5])

    monkeypatch.setattr(
        liderapi_gate,
        "authenticate",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("signin returned HTTP 503")),
    )
    monkeypatch.setattr(liderapi_gate.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(liderapi_gate.time, "monotonic", lambda: next(monotonic_values))

    with pytest.raises(liderapi_gate.GateTimeoutError) as excinfo:
        liderapi_gate.wait_for_liderapi_gate(
            base_url="http://liderapi:8080",
            username="lider-admin",
            password="secret",
            timeout_seconds=3,
            interval_seconds=0,
            stable_success_count=1,
        )

    assert "last error: signin returned HTTP 503" in str(excinfo.value)
