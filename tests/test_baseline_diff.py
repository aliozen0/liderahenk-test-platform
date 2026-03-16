from __future__ import annotations

import json

import platform_runtime.golden_baseline as golden_baseline
import yaml

from platform_runtime.golden_baseline import _build_baseline_diff_payload, write_baseline_diff


def _contract():
    with open("platform/contracts/baseline-registry.yaml", "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _baseline_payload():
    return {
        "manifest.json": {
            "baselineName": "stock-liderahenk",
            "capturedAt": "2026-01-01T00:00:00+00:00",
            "source": {"kind": "stock-liderahenk-install", "label": "stock-2026-01-01"},
        },
        "ldap-tree.json": {
            "entries": [
                {"dn": "cn=ahenk-001,ou=Ahenkler,dc=liderahenk,dc=org"},
                {"dn": "cn=ahenk-002,ou=Ahenkler,dc=liderahenk,dc=org"},
            ]
        },
        "config.json": {
            "fields": {
                "ldapRootDn": {"present": True, "source": "c_config.liderConfigParams", "sha256": "a", "value": "dc=liderahenk,dc=org"},
                "xmppPassword": {"present": True, "source": "c_config.liderConfigParams", "sha256": "secret-a"},
            }
        },
        "api-captures/dashboard.json": {
            "payload": {
                "totalComputerNumber": 2,
                "totalOnlineComputerNumber": 2,
            }
        },
        "api-captures/agent-list.json": {
            "agentIds": ["ahenk-001", "ahenk-002"],
        },
        "api-captures/computer-tree.json": {
            "agentIds": ["ahenk-001", "ahenk-002"],
        },
    }


def _pass_verdict():
    return {
        "status": "pass",
        "runtimeProfile": "dev-fidelity",
        "expectedAgents": 2,
    }


def test_build_baseline_diff_payload_passes_when_truth_matches(tmp_path):
    baseline = _baseline_payload()
    payload = _build_baseline_diff_payload(
        baseline_root=tmp_path,
        baseline=baseline,
        live={
            "ldap-tree.json": baseline["ldap-tree.json"],
            "config.json": baseline["config.json"],
            "api-captures/dashboard.json": baseline["api-captures/dashboard.json"],
            "api-captures/agent-list.json": baseline["api-captures/agent-list.json"],
            "api-captures/computer-tree.json": baseline["api-captures/computer-tree.json"],
        },
        live_verdict=_pass_verdict(),
        contract=_contract(),
        verdict_source="artifact",
    )
    assert payload["status"] == "pass"
    assert payload["summary"]["blockingDiffCount"] == 0
    assert payload["summary"]["counts"]["warn"] == 0
    assert payload["diffs"] == []


def test_build_baseline_diff_payload_emits_warning_and_errors(tmp_path):
    baseline = _baseline_payload()
    live = {
        "ldap-tree.json": baseline["ldap-tree.json"],
        "config.json": baseline["config.json"],
        "api-captures/dashboard.json": {"payload": {"totalComputerNumber": 3, "totalOnlineComputerNumber": 2}},
        "api-captures/agent-list.json": {"agentIds": ["ahenk-001", "ahenk-003"]},
        "api-captures/computer-tree.json": baseline["api-captures/computer-tree.json"],
    }
    payload = _build_baseline_diff_payload(
        baseline_root=tmp_path,
        baseline=baseline,
        live=live,
        live_verdict={"status": "fail", "runtimeProfile": "dev-fast", "expectedAgents": 2},
        contract=_contract(),
        verdict_source="live-evaluated",
    )
    assert payload["status"] == "fail"
    assert payload["summary"]["counts"]["warn"] == 1
    assert payload["summary"]["counts"]["error"] == 3
    codes = {item["code"] for item in payload["diffs"]}
    assert "registration_verdict_artifact_missing" in codes
    assert "dashboard_total" in codes
    assert "agent_list_identities" in codes
    assert "registration_verdict_status" in codes


def test_write_baseline_diff_renders_summary_sections(tmp_path):
    payload = _build_baseline_diff_payload(
        baseline_root=tmp_path,
        baseline=_baseline_payload(),
        live={
            "ldap-tree.json": {"entries": []},
            "config.json": {"fields": {}},
            "api-captures/dashboard.json": {"payload": {"totalComputerNumber": 0, "totalOnlineComputerNumber": 0}},
            "api-captures/agent-list.json": {"agentIds": []},
            "api-captures/computer-tree.json": {"agentIds": []},
        },
        live_verdict={"status": "fail", "runtimeProfile": "dev-fast", "expectedAgents": 0},
        contract=_contract(),
        verdict_source="live-evaluated",
    )
    _, markdown_path = write_baseline_diff(payload, output_dir=tmp_path)
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Blocking severity" in markdown
    assert "## Error Diffs" in markdown
    assert "## Warn Diffs" in markdown
    json_payload = json.loads((tmp_path / "baseline-diff.json").read_text(encoding="utf-8"))
    assert json_payload["summary"]["blockingDiffCount"] > 0


def test_compare_with_golden_baseline_falls_back_when_verdict_artifact_is_invalid(tmp_path, monkeypatch):
    baseline = _baseline_payload()
    monkeypatch.setattr(golden_baseline, "load_golden_baseline", lambda root: baseline)
    monkeypatch.setattr(
        golden_baseline,
        "_collect_live_baseline_payload",
        lambda bundle, runtime_db, contract: {
            "ldap-tree.json": baseline["ldap-tree.json"],
            "config.json": baseline["config.json"],
            "api-captures/dashboard.json": baseline["api-captures/dashboard.json"],
            "api-captures/agent-list.json": baseline["api-captures/agent-list.json"],
            "api-captures/computer-tree.json": baseline["api-captures/computer-tree.json"],
        },
    )
    monkeypatch.setattr(golden_baseline, "build_platform_bundle", lambda: object())
    monkeypatch.setattr(
        golden_baseline,
        "RuntimeDbAdapter",
        type("RuntimeDbAdapter", (), {"from_env": staticmethod(lambda: object())}),
    )

    class _Collector:
        def collect_snapshot(self):
            return {}

        def evaluate_snapshot(self, snapshot):
            return _pass_verdict()

    monkeypatch.setattr(
        golden_baseline,
        "RegistrationCollector",
        type("RegistrationCollector", (), {"from_env": staticmethod(lambda: _Collector())}),
    )
    verdict_path = tmp_path / "registration-verdict.json"
    verdict_path.write_text("{invalid", encoding="utf-8")

    payload = golden_baseline.compare_with_golden_baseline(
        baseline_root=tmp_path,
        verdict_path=verdict_path,
    )
    assert payload["status"] == "pass"
    assert payload["comparison"]["verdictSource"] == "artifact-invalid"
    assert payload["summary"]["counts"]["warn"] == 1
