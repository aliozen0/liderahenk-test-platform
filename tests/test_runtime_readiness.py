from __future__ import annotations

import json

import platform_runtime.runtime_readiness as runtime_readiness


def test_collect_runtime_core_report_passes_when_all_checks_pass(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "3")
    monkeypatch.setattr(
        runtime_readiness,
        "_service_state_report",
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
        runtime_readiness,
        "_core_connectivity_checks",
        lambda profile: [
            runtime_readiness._build_check(
                check_id="liderapi_auth",
                category="service",
                description="liderapi JWT authentication works",
                passed=True,
            )
        ],
    )

    report = runtime_readiness.collect_runtime_core_report(profile="dev-fast")

    assert report["status"] == "pass"
    assert report["expectedAgents"] == 3
    assert report["summary"] == {"totalChecks": 2, "passedChecks": 2, "failedChecks": 0}
    assert report["services"]["liderapi"]["states"] == ["running"]


def test_collect_runtime_operational_report_fails_on_any_check(monkeypatch):
    monkeypatch.setenv("AHENK_COUNT", "2")
    monkeypatch.setattr(
        runtime_readiness,
        "_registration_parity_check",
        lambda expected_agents: runtime_readiness._build_check(
            check_id="registration_parity",
            category="registration",
            description="registration parity",
            passed=True,
        ),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_run_policy_roundtrip_check",
        lambda: runtime_readiness._build_check(
            check_id="policy_roundtrip",
            category="operational",
            description="policy roundtrip",
            passed=False,
        ),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_run_pytest_check",
        lambda check_id, description, pytest_paths, timeout: runtime_readiness._build_check(
            check_id=check_id,
            category="ui",
            description=description,
            passed=True,
        ),
    )
    monkeypatch.setattr(
        runtime_readiness,
        "_observability_checks",
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
