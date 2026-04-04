from __future__ import annotations

import json
from pathlib import Path

from platform_runtime.registration_evidence import (
    validate_registration_evidence,
    write_registration_evidence_report,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_valid_evidence_bundle(tmp_path: Path) -> Path:
    _write_json(
        tmp_path / "run-manifest.json",
        {
            "schemaVersion": 1,
            "runId": "run-123",
            "runtimeProfile": "dev-fast",
            "expectedAgents": 2,
            "startedAt": "2026-01-01T00:00:00+00:00",
            "timeoutSeconds": 180,
            "backoff": {"minSeconds": 2, "maxSeconds": 15},
            "lastVerdictAt": "2026-01-01T00:00:10+00:00",
            "lastStatus": "pass",
            "attemptCount": 1,
        },
    )
    verdict = {
        "schemaVersion": 1,
        "runId": "run-123",
        "status": "pass",
        "runtimeProfile": "dev-fast",
        "expectedAgents": 2,
        "checks": {"ldap_matches_expected": True},
        "failedChecks": [],
        "taxonomy": [],
        "surfaces": {"ldapAgentCount": 2},
        "perAgent": [
            {
                "agentId": "ahenk-001",
                "states": {
                    "ldap_entry_ready": True,
                    "xmpp_identity_ready": True,
                    "register_sent": True,
                    "register_accepted": True,
                    "c_agent_ready": True,
                    "domain_ready": True,
                },
                "highestState": "domain_ready",
                "observability": {},
            },
            {
                "agentId": "ahenk-002",
                "states": {
                    "ldap_entry_ready": True,
                    "xmpp_identity_ready": True,
                    "register_sent": True,
                    "register_accepted": True,
                    "c_agent_ready": True,
                    "domain_ready": True,
                },
                "highestState": "domain_ready",
                "observability": {},
            }
        ],
        "capturedAt": "2026-01-01T00:00:10+00:00",
    }
    _write_json(tmp_path / "registration-verdict.json", verdict)
    _write_json(
        tmp_path / "failure-summary.json",
        {
            "schemaVersion": 1,
            "runId": "run-123",
            "status": "pass",
            "capturedAt": "2026-01-01T00:00:10+00:00",
            "failedChecks": [],
            "taxonomy": [],
        },
    )
    (tmp_path / "registration-events.jsonl").write_text(
        json.dumps(
            {
                "runId": "run-123",
                "attempt": 1,
                "phase": "settle",
                "status": "pass",
                "failedChecks": [],
                "taxonomy": [],
                "capturedAt": "2026-01-01T00:00:10+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        tmp_path / "runtime-operational-report.json",
        {
            "schemaVersion": 1,
            "reportType": "runtime-operational",
            "status": "pass",
            "profile": "dev-fast",
            "topology": {"name": "dev-fast"},
            "support": {
                "mutationSupport": {
                    "supportedDeclaredMutationSteps": [
                        "create_group_via_ui",
                        "create_policy_via_ui",
                    ],
                    "unsupportedDeclaredMutationSteps": [
                        "create_user_via_ui",
                    ],
                },
                "scenarios": {
                    "activeScenarios": ["ui-user-policy-roundtrip"],
                },
                "sessionSupport": {
                    "supportedDeclaredSessionSteps": [
                        "simulate_login",
                        "collect_membership_snapshot",
                    ],
                    "unsupportedDeclaredSessionSteps": [
                        "verify_effect",
                    ],
                },
            },
        },
    )
    return tmp_path


def test_registration_evidence_accepts_valid_bundle(tmp_path):
    _write_valid_evidence_bundle(tmp_path)
    report = validate_registration_evidence(tmp_path)
    assert report["valid"] is True, report["errors"]
    assert report["runtimeSupport"]["runtime-operational-report.json"]["activeScenarios"] == [
        "ui-user-policy-roundtrip"
    ]
    assert report["runtimeSupport"]["runtime-operational-report.json"]["supportedDeclaredSessionSteps"] == [
        "simulate_login",
        "collect_membership_snapshot",
    ]


def test_registration_evidence_rejects_run_id_mismatch(tmp_path):
    _write_valid_evidence_bundle(tmp_path)
    payload = json.loads((tmp_path / "failure-summary.json").read_text(encoding="utf-8"))
    payload["runId"] = "other-run"
    (tmp_path / "failure-summary.json").write_text(json.dumps(payload), encoding="utf-8")
    report = validate_registration_evidence(tmp_path)
    assert report["valid"] is False
    assert "failure-summary.json: runId does not match registration-verdict.json" in report["errors"]


def test_registration_evidence_rejects_missing_agent_state(tmp_path):
    _write_valid_evidence_bundle(tmp_path)
    payload = json.loads((tmp_path / "registration-verdict.json").read_text(encoding="utf-8"))
    del payload["perAgent"][0]["states"]["domain_ready"]
    (tmp_path / "registration-verdict.json").write_text(json.dumps(payload), encoding="utf-8")
    report = validate_registration_evidence(tmp_path)
    assert report["valid"] is False
    assert any("missing states" in item for item in report["errors"])


def test_registration_evidence_rejects_false_green_pass_verdict(tmp_path):
    _write_valid_evidence_bundle(tmp_path)
    payload = json.loads((tmp_path / "registration-verdict.json").read_text(encoding="utf-8"))
    payload["checks"]["ldap_matches_expected"] = False
    (tmp_path / "registration-verdict.json").write_text(json.dumps(payload), encoding="utf-8")
    report = validate_registration_evidence(tmp_path)
    assert report["valid"] is False
    assert "registration-verdict.json: pass verdict contains failed checks" in report["errors"]


def test_registration_evidence_report_renders_runtime_support_context(tmp_path):
    _write_valid_evidence_bundle(tmp_path)
    report = validate_registration_evidence(tmp_path)

    _, markdown_path = write_registration_evidence_report(report, output_dir=tmp_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "## Runtime Support Context" in markdown
    assert "ui-user-policy-roundtrip" in markdown
    assert "create_group_via_ui" in markdown
    assert "collect_membership_snapshot" in markdown
    assert "verify_effect" in markdown
