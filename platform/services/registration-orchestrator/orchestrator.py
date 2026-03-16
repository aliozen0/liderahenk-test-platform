from __future__ import annotations

import json
import os
import time
from pathlib import Path

from platform_runtime.registration import (
    RegistrationCollector,
    append_event,
    build_failure_summary,
    build_run_manifest,
    write_json,
)


class RegistrationOrchestrator:
    def __init__(self) -> None:
        self.collector = RegistrationCollector.from_env()
        self.expected_agents = self.collector.expected_agents
        self.runtime_profile = os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fast")
        self.interval_seconds = int(os.environ.get("PLATFORM_EXPORTER_INTERVAL_SECONDS", "15"))
        self.timeout_seconds = int(os.environ.get("PLATFORM_ORCHESTRATOR_TIMEOUT_SECONDS", "180"))
        self.min_backoff_seconds = int(os.environ.get("PLATFORM_ORCHESTRATOR_MIN_BACKOFF_SECONDS", "2"))
        self.max_backoff_seconds = int(os.environ.get("PLATFORM_ORCHESTRATOR_MAX_BACKOFF_SECONDS", "15"))
        self.artifacts_dir = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.run_manifest = build_run_manifest(
            expected_agents=self.expected_agents,
            runtime_profile=self.runtime_profile,
            timeout_seconds=self.timeout_seconds,
            min_backoff_seconds=self.min_backoff_seconds,
            max_backoff_seconds=self.max_backoff_seconds,
        )
        self.events_path = self.artifacts_dir / "registration-events.jsonl"
        self.events_path.write_text("", encoding="utf-8")
        write_json(self.artifacts_dir / "run-manifest.json", self.run_manifest)

    def _empty_snapshot(self) -> dict:
        return {
            "runtimeProfile": self.runtime_profile,
            "expectedAgents": self.expected_agents,
            "capturedAt": self.run_manifest["startedAt"],
            "ldapAgentIds": [],
            "xmppRegisteredAgentIds": [],
            "xmppConnectedAgentIds": [],
            "cAgentIds": [],
            "domainAgentIds": [],
            "computerTreeAgentIds": [],
            "dashboard": {
                "totalComputerNumber": None,
                "totalOnlineComputerNumber": None,
            },
            "runtimeConfigFingerprint": None,
        }

    def collect_verdict(self, *, timed_out: bool = False) -> tuple[dict, dict]:
        errors: list[str] = []
        try:
            snapshot = self.collector.collect_snapshot()
        except Exception as exc:
            snapshot = self._empty_snapshot()
            errors.append(str(exc))
        evaluation = self.collector.evaluate_snapshot(snapshot, timed_out=timed_out, errors=errors)
        verdict = {
            "schemaVersion": 1,
            "runId": self.run_manifest["runId"],
            "status": evaluation["status"],
            "runtimeProfile": self.runtime_profile,
            "expectedAgents": self.expected_agents,
            "checks": evaluation["checks"],
            "failedChecks": evaluation["failedChecks"],
            "taxonomy": evaluation["taxonomy"],
            "surfaces": evaluation["surfaces"],
            "perAgent": evaluation["perAgent"],
            "capturedAt": evaluation["capturedAt"],
            "snapshot": snapshot,
        }
        return snapshot, verdict

    def write_artifacts(self, *, snapshot: dict, verdict: dict, attempt: int, phase: str) -> None:
        self.run_manifest["lastVerdictAt"] = verdict["capturedAt"]
        self.run_manifest["lastStatus"] = verdict["status"]
        self.run_manifest["attemptCount"] = attempt
        write_json(self.artifacts_dir / "run-manifest.json", self.run_manifest)
        write_json(self.artifacts_dir / "registration-verdict.json", verdict)
        write_json(self.artifacts_dir / "failure-summary.json", build_failure_summary(self.run_manifest, verdict))
        write_json(
            self.artifacts_dir / "registration-snapshot.json",
            {"snapshot": snapshot, "verdict": verdict},
        )
        append_event(
            self.events_path,
            {
                "runId": self.run_manifest["runId"],
                "attempt": attempt,
                "phase": phase,
                "status": verdict["status"],
                "failedChecks": verdict["failedChecks"],
                "taxonomy": verdict["taxonomy"],
                "capturedAt": verdict["capturedAt"],
            },
        )

    def settle_registration(self) -> dict:
        deadline = time.monotonic() + self.timeout_seconds
        backoff_seconds = self.min_backoff_seconds
        attempt = 0
        verdict = {}
        while True:
            attempt += 1
            snapshot, verdict = self.collect_verdict()
            self.write_artifacts(snapshot=snapshot, verdict=verdict, attempt=attempt, phase="settle")
            if verdict["status"] == "pass":
                return verdict
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                snapshot, verdict = self.collect_verdict(timed_out=True)
                self.write_artifacts(snapshot=snapshot, verdict=verdict, attempt=attempt, phase="timeout")
                return verdict
            time.sleep(min(backoff_seconds, max(remaining, 0)))
            backoff_seconds = min(backoff_seconds * 2, self.max_backoff_seconds)

    def run_forever(self) -> None:
        self.settle_registration()
        attempt = self.run_manifest.get("attemptCount", 0)
        while True:
            attempt += 1
            snapshot, verdict = self.collect_verdict()
            self.write_artifacts(snapshot=snapshot, verdict=verdict, attempt=attempt, phase="steady-state")
            time.sleep(self.interval_seconds)


if __name__ == "__main__":
    RegistrationOrchestrator().run_forever()
