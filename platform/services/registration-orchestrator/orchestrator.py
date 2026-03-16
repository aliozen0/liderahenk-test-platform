from __future__ import annotations

import json
import os
import time
from pathlib import Path

from adapters import build_platform_bundle


class RegistrationOrchestrator:
    def __init__(self) -> None:
        self.bundle = build_platform_bundle()
        self.expected_agents = int(os.environ.get("AHENK_COUNT", "1"))
        self.runtime_profile = os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fast")
        self.interval_seconds = int(os.environ.get("PLATFORM_EXPORTER_INTERVAL_SECONDS", "15"))
        self.artifacts_dir = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> dict:
        dashboard = self.bundle.inventory.get_dashboard_info() or {}
        ldap_count = self.bundle.directory.get_agent_count()
        xmpp_registered = max(self.bundle.presence.get_registered_count() - 1, 0)
        xmpp_connected = self.bundle.presence.get_connected_count()
        agent_list = self.bundle.inventory.get_agent_list()
        return {
            "runtimeProfile": self.runtime_profile,
            "expectedAgents": self.expected_agents,
            "ldapAgentCount": ldap_count,
            "xmppRegisteredCount": xmpp_registered,
            "xmppConnectedCount": xmpp_connected,
            "domainAgentCount": len(agent_list),
            "dashboardTotalComputerNumber": dashboard.get("totalComputerNumber"),
            "dashboardTotalOnlineComputerNumber": dashboard.get("totalOnlineComputerNumber"),
            "timestamp": int(time.time()),
        }

    def evaluate(self, snapshot: dict) -> dict:
        drifts = []
        expected = snapshot["expectedAgents"]
        checks = {
            "ldap_matches_expected": snapshot["ldapAgentCount"] == expected,
            "xmpp_registered_matches_expected": snapshot["xmppRegisteredCount"] == expected,
            "domain_agent_count_matches_expected": snapshot["domainAgentCount"] == expected,
            "dashboard_total_matches_expected": snapshot.get("dashboardTotalComputerNumber") == expected,
        }
        if snapshot.get("dashboardTotalOnlineComputerNumber") not in (None, snapshot["xmppConnectedCount"]):
            drifts.append("dashboard_online_count_mismatch")
        for name, passed in checks.items():
            if not passed:
                drifts.append(name)
        return {"checks": checks, "drifts": drifts}

    def write_snapshot(self, snapshot: dict, evaluation: dict) -> None:
        payload = {"snapshot": snapshot, "evaluation": evaluation}
        target = self.artifacts_dir / "registration-snapshot.json"
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def run_forever(self) -> None:
        while True:
            snapshot = self.snapshot()
            evaluation = self.evaluate(snapshot)
            self.write_snapshot(snapshot, evaluation)
            time.sleep(self.interval_seconds)


if __name__ == "__main__":
    RegistrationOrchestrator().run_forever()
