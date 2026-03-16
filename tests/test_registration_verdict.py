from __future__ import annotations

from platform_runtime.registration import RegistrationCollector


def _collector() -> RegistrationCollector:
    return RegistrationCollector(
        bundle=None,  # type: ignore[arg-type]
        runtime_db=None,  # type: ignore[arg-type]
        expected_agents=2,
        runtime_profile="dev-fast",
    )


def test_projection_mismatch_is_classified():
    collector = _collector()
    snapshot = {
        "expectedAgents": 2,
        "capturedAt": "2026-01-01T00:00:00+00:00",
        "ldapAgentIds": ["ahenk-001", "ahenk-002"],
        "xmppRegisteredAgentIds": ["ahenk-001"],
        "xmppConnectedAgentIds": ["ahenk-001"],
        "cAgentIds": ["ahenk-001"],
        "domainAgentIds": ["ahenk-001"],
        "computerTreeAgentIds": ["ahenk-001"],
        "dashboard": {
            "totalComputerNumber": 1,
            "totalOnlineComputerNumber": 1,
        },
    }
    verdict = collector.evaluate_snapshot(snapshot)
    assert verdict["status"] == "fail"
    assert verdict["taxonomy"][0]["code"] == "registration_projection_mismatch"


def test_timeout_is_classified():
    collector = _collector()
    snapshot = {
        "expectedAgents": 2,
        "capturedAt": "2026-01-01T00:00:00+00:00",
        "ldapAgentIds": ["ahenk-001"],
        "xmppRegisteredAgentIds": ["ahenk-001"],
        "xmppConnectedAgentIds": [],
        "cAgentIds": [],
        "domainAgentIds": [],
        "computerTreeAgentIds": [],
        "dashboard": {
            "totalComputerNumber": 0,
            "totalOnlineComputerNumber": 0,
        },
    }
    verdict = collector.evaluate_snapshot(snapshot, timed_out=True)
    assert verdict["status"] == "fail"
    assert verdict["taxonomy"][0]["code"] == "registration_timeout"
