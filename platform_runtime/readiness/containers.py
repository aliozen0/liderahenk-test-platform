"""Docker Compose container state inspection and service readiness checks."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .checks import build_check

BOOTSTRAP_MANIFEST_PATH = Path("platform/bootstrap/bootstrap-manifest.yaml")
RUNTIME_READINESS_CONTRACT_PATH = Path("platform/contracts/runtime-readiness.yaml")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _project_name() -> str:
    return os.environ.get("PROJECT_NAME", "liderahenk-test")


def compose_stack(profile: str) -> list[str]:
    bootstrap = _read_yaml(BOOTSTRAP_MANIFEST_PATH)
    return bootstrap["runtime_profiles"][profile]["compose_stack"]


def compose_ps(profile: str) -> list[dict[str, Any]]:
    stack = compose_stack(profile)
    cmd = ["docker", "compose"]
    for path in stack:
        cmd.extend(["-f", path])
    cmd.extend(["-p", _project_name(), "ps", "--all", "--format", "json"])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(Path.cwd()),
        timeout=30,
    )
    if result.returncode != 0:
        return []
    containers: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return containers


def containers_by_service(containers: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in containers:
        service = entry.get("Service") or entry.get("Name")
        if not service:
            continue
        grouped.setdefault(str(service), []).append(entry)
    return grouped


def normalize_state(container: dict[str, Any]) -> str:
    state = str(container.get("State") or "").lower()
    status = str(container.get("Status") or "")
    if state == "running":
        return "running"
    if state == "exited" and "Exited (0)" in status:
        return "completed"
    return state or "unknown"


def service_state_report(profile: str, expected_agents: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contract = _read_yaml(RUNTIME_READINESS_CONTRACT_PATH)
    grouped = containers_by_service(compose_ps(profile))
    checks: list[dict[str, Any]] = []
    services_report: dict[str, Any] = {}
    required_groups = contract["runtime_profiles"][profile]["required_service_groups"]
    for group_name in required_groups:
        for service_name in contract["service_groups"][group_name]:
            expectation = contract["service_expectations"][service_name]
            instances = grouped.get(service_name, [])
            normalized_states = [normalize_state(item) for item in instances]
            services_report[service_name] = {
                "instanceCount": len(instances),
                "states": normalized_states,
            }
            accepted_states = expectation["accepted_states"]
            if expectation["kind"] == "scaled":
                passed = len(instances) == expected_agents and instances and all(
                    state in accepted_states for state in normalized_states
                )
                expected = {"instances": expected_agents, "states": accepted_states}
                actual = {"instances": len(instances), "states": normalized_states}
            else:
                passed = bool(instances) and all(state in accepted_states for state in normalized_states)
                expected = accepted_states
                actual = normalized_states
            checks.append(
                build_check(
                    check_id=f"service:{service_name}",
                    category="docker",
                    description=f"{service_name} service readiness",
                    passed=passed,
                    actual=actual,
                    expected=expected,
                )
            )
    return checks, services_report
