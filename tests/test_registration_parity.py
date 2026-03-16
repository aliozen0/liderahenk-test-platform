from __future__ import annotations

from platform_runtime.registration import RegistrationCollector


class TestRegistrationParity:
    def test_registration_surfaces_are_exactly_aligned(self):
        collector = RegistrationCollector.from_env()
        snapshot = collector.collect_snapshot()
        verdict = collector.evaluate_snapshot(snapshot)

        assert verdict["status"] == "pass", (
            f"registration parity failed: checks={verdict['checks']} "
            f"taxonomy={verdict['taxonomy']}"
        )
        assert all(verdict["checks"].values()), f"failed checks: {verdict['failedChecks']}"

    def test_every_expected_agent_reaches_domain_ready(self):
        collector = RegistrationCollector.from_env()
        snapshot = collector.collect_snapshot()
        verdict = collector.evaluate_snapshot(snapshot)
        ready_agents = [item for item in verdict["perAgent"] if item["states"]["domain_ready"]]
        assert len(ready_agents) == collector.expected_agents, (
            f"domain ready agents mismatch: expected={collector.expected_agents} "
            f"actual={len(ready_agents)}"
        )
