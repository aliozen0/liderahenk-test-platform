#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml


BOOTSTRAP_MANIFEST_PATH = Path("platform/bootstrap/bootstrap-manifest.yaml")
RUNTIME_READINESS_CONTRACT_PATH = Path("platform/contracts/runtime-readiness.yaml")
def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_topology_profile_module():
    module_path = Path(__file__).resolve().parents[1] / "topology" / "profile_loader.py"
    spec = importlib.util.spec_from_file_location("topology_profile_loader", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive branch
        raise RuntimeError(f"unable to load topology profile loader from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compose_stack(profile: str) -> list[str]:
    bootstrap = _read_yaml(BOOTSTRAP_MANIFEST_PATH)
    return bootstrap["runtime_profiles"][profile]["compose_stack"]


def _compose_base_cmd(profile: str, project_name: str) -> list[str]:
    cmd = ["docker", "compose"]
    for compose_file in _compose_stack(profile):
        cmd.extend(["-f", compose_file])
    cmd.extend(["-p", project_name])
    return cmd


def _run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(Path.cwd()), env=env, text=True)


def _compose_rm(profile: str, project_name: str, services: list[str], *, env: dict[str, str]) -> None:
    if not services:
        return
    cmd = _compose_base_cmd(profile, project_name) + ["rm", "-sf", *services]
    result = _run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _runtime_env(profile: str, expected_agents: int, project_name: str) -> tuple[dict[str, str], dict[str, Any]]:
    env = os.environ.copy()
    env["AHENK_COUNT"] = str(expected_agents)
    env["PLATFORM_RUNTIME_PROFILE"] = profile
    env["PROJECT_NAME"] = project_name

    topology_module = _load_topology_profile_module()
    topology = topology_module.resolve_topology_profile(
        profile,
        expected_agents=expected_agents,
        env=env,
    )
    env.update(topology["env"])
    return env, topology


def _compose_up(
    *,
    profile: str,
    project_name: str,
    services: list[str],
    env: dict[str, str],
    build: bool,
    scale_agents: int | None,
    no_deps: bool,
    recreate_before_up: list[str] | None,
) -> None:
    if build:
        build_cmd = _compose_base_cmd(profile, project_name) + ["build"]
        build_cmd.extend(services)
        result = _run(build_cmd, env=env)
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    _compose_rm(profile, project_name, recreate_before_up or [], env=env)

    cmd = _compose_base_cmd(profile, project_name) + ["up", "-d", "--no-build"]
    if no_deps:
        cmd.append("--no-deps")
    if scale_agents is not None and "ahenk" in services:
        cmd.extend(["--scale", f"ahenk={scale_agents}"])
    cmd.extend(services)
    result = _run(cmd, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _compose_ps(profile: str, project_name: str, env: dict[str, str]) -> list[dict[str, Any]]:
    cmd = _compose_base_cmd(profile, project_name) + ["ps", "--all", "--format", "json"]
    result = subprocess.run(
        cmd,
        cwd=str(Path.cwd()),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "docker compose ps failed")
    containers: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        containers.append(json.loads(line))
    return containers


def _parse_host_port_binding(port_mapping: Any) -> dict[str, Any] | None:
    if isinstance(port_mapping, dict):
        published = port_mapping.get("published")
        if published is None:
            return None
        host = str(
            port_mapping.get("host_ip")
            or port_mapping.get("hostIp")
            or port_mapping.get("host")
            or "0.0.0.0"
        )
        return {"host": host, "port": int(published)}

    if isinstance(port_mapping, str):
        mapping = port_mapping.split("/", 1)[0]
        parts = mapping.split(":")
        if len(parts) < 2:
            return None
        if len(parts) == 2:
            return {"host": "0.0.0.0", "port": int(parts[0])}
        return {"host": parts[0], "port": int(parts[1])}

    return None


def _declared_host_port_bindings(profile: str) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for compose_file in _compose_stack(profile):
        compose_config = _read_yaml(Path(compose_file)) or {}
        services = compose_config.get("services") or {}
        for service_name, service_config in services.items():
            ports = service_config.get("ports") or []
            for port_mapping in ports:
                binding = _parse_host_port_binding(port_mapping)
                if binding is None:
                    continue
                key = (str(service_name), str(binding["host"]), int(binding["port"]))
                if key in seen:
                    continue
                seen.add(key)
                bindings.append(
                    {
                        "service": str(service_name),
                        "host": str(binding["host"]),
                        "port": int(binding["port"]),
                        "source": compose_file,
                    }
                )
    return bindings


def _project_owned_host_ports(profile: str, project_name: str, env: dict[str, str]) -> set[int]:
    try:
        containers = _compose_ps(profile, project_name, env)
    except RuntimeError:
        return set()

    owned_ports: set[int] = set()
    for container in containers:
        publishers = container.get("Publishers") or []
        if not isinstance(publishers, list):
            continue
        for publisher in publishers:
            if not isinstance(publisher, dict):
                continue
            published_port = publisher.get("PublishedPort")
            if published_port is None:
                continue
            owned_ports.add(int(published_port))
    return owned_ports


def _host_port_available(host: str, port: int) -> bool:
    bind_host = "" if host in {"0.0.0.0", "::"} else host
    family = socket.AF_INET6 if ":" in bind_host and bind_host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, port))
        return True
    except OSError:
        return False


def _host_port_conflicts(profile: str, project_name: str, env: dict[str, str]) -> list[dict[str, Any]]:
    owned_ports = _project_owned_host_ports(profile, project_name, env)
    conflicts: list[dict[str, Any]] = []
    for binding in _declared_host_port_bindings(profile):
        if binding["port"] in owned_ports:
            continue
        if not _host_port_available(binding["host"], binding["port"]):
            conflicts.append(binding)
    return conflicts


def _normalize_state(container: dict[str, Any]) -> str:
    state = str(container.get("State") or "").lower()
    status = str(container.get("Status") or "")
    if state == "running":
        return "running"
    if state == "exited" and "Exited (0)" in status:
        return "completed"
    return state or "unknown"


def _group_by_service(containers: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for container in containers:
        service = str(container.get("Service") or "")
        if not service:
            continue
        grouped.setdefault(service, []).append(
            {
                "state": _normalize_state(container),
                "health": str(container.get("Health") or "").lower(),
            }
        )
    return grouped


def _phase_satisfied(
    *,
    states_by_service: dict[str, list[dict[str, str]]],
    wait_for: dict[str, Any],
    expected_agents: int,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for service, expectation in wait_for.items():
        containers = states_by_service.get(service, [])
        states = [container["state"] for container in containers]
        health_values = [container["health"] for container in containers if container["health"]]
        if isinstance(expectation, dict):
            expected_state = expectation["state"]
            expected_instances = int(expectation.get("instances", expected_agents))
            expected_health = expectation.get("health")
            if len(states) != expected_instances:
                errors.append(
                    f"{service}: expected {expected_instances} instance(s), found {len(states)} ({states or ['missing']})"
                )
                continue
            if any(state != expected_state for state in states):
                errors.append(f"{service}: expected all {expected_state}, found {states}")
                continue
            if expected_health and any(container["health"] != expected_health for container in containers):
                errors.append(
                    f"{service}: expected all health={expected_health}, found {health_values or ['unreported']}"
                )
            continue
        if not states:
            errors.append(f"{service}: no containers")
            continue
        if expectation == "healthy":
            if any(state != "running" for state in states):
                errors.append(f"{service}: expected running+healthy, found states={states}")
                continue
            if not health_values or any(health != "healthy" for health in health_values):
                errors.append(f"{service}: expected health=healthy, found {health_values or ['unreported']}")
            continue
        if any(state != expectation for state in states):
            errors.append(f"{service}: expected {expectation}, found {states}")
    return not errors, errors


def _print_phase_status(name: str, errors: list[str]) -> None:
    if not errors:
        print(f"[bootstrap-runtime] ✅ phase `{name}` ready")
        return
    print(f"[bootstrap-runtime] waiting for phase `{name}`...")
    for error in errors:
        print(f"[bootstrap-runtime]   - {error}")


def bootstrap_runtime(profile: str, expected_agents: int, project_name: str, build: bool) -> int:
    contract = _read_yaml(RUNTIME_READINESS_CONTRACT_PATH)
    profile_contract = contract["runtime_profiles"][profile]
    bootstrap_defaults = contract.get("bootstrap_defaults", {})
    poll_interval = int(bootstrap_defaults.get("poll_interval_seconds", 5))
    default_timeout = int(bootstrap_defaults.get("phase_timeout_seconds", 300))

    env, topology = _runtime_env(profile, expected_agents, project_name)
    print(
        "[bootstrap-runtime] topology "
        f"`{topology['name']}`: operators={topology['operators']['count']}, "
        f"directory_users={topology['directory_users']['count']}, "
        f"user_groups={topology['user_groups']['count']}, "
        f"endpoint_groups={topology['endpoint_groups']['count']}, "
        f"policy_pack={topology['policy_pack']}, session_pack={topology['session_pack']}"
    )

    conflicts = _host_port_conflicts(profile, project_name, env)
    if conflicts:
        print(
            f"[bootstrap-runtime] ❌ host port preflight failed for profile `{profile}`; "
            "bootstrap stopped before any compose phase was started.",
            file=sys.stderr,
        )
        for conflict in conflicts:
            print(
                "[bootstrap-runtime]   - "
                f"{conflict['service']} requires {conflict['host']}:{conflict['port']} "
                f"({conflict['source']})",
                file=sys.stderr,
            )
        print(
            "[bootstrap-runtime] free the conflicting ports or remove stale Docker publishes, then retry.",
            file=sys.stderr,
        )
        return 1

    for phase in profile_contract["bootstrap_phases"]:
        name = phase["name"]
        services = phase["services"]
        timeout = int(phase.get("timeout_seconds", default_timeout))
        scale_agents = expected_agents if phase.get("scale_ahenk") else None
        recreate_before_up = [str(service) for service in phase.get("recreate_before_up", [])]

        print(f"[bootstrap-runtime] starting phase `{name}`: {', '.join(services)}")
        _compose_up(
            profile=profile,
            project_name=project_name,
            services=services,
            env=env,
            build=build,
            scale_agents=scale_agents,
            no_deps=bool(phase.get("no_deps", False)),
            recreate_before_up=recreate_before_up,
        )

        deadline = time.time() + timeout
        last_errors: list[str] = []
        while time.time() < deadline:
            states_by_service = _group_by_service(_compose_ps(profile, project_name, env))
            ready, errors = _phase_satisfied(
                states_by_service=states_by_service,
                wait_for=phase["wait_for"],
                expected_agents=expected_agents,
            )
            if ready:
                _print_phase_status(name, [])
                break
            if errors != last_errors:
                _print_phase_status(name, errors)
                last_errors = errors
            time.sleep(poll_interval)
        else:
            _print_phase_status(name, last_errors)
            print(f"[bootstrap-runtime] ❌ phase `{name}` timed out after {timeout}s", file=sys.stderr)
            return 1

    print("[bootstrap-runtime] stack bootstrapped successfully")
    status_cmd = _compose_base_cmd(profile, project_name) + ["ps"]
    return _run(status_cmd, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap LiderAhenk runtime in deterministic phases.")
    parser.add_argument("--profile", required=True, choices=["dev-fast", "dev-fidelity"])
    parser.add_argument("--agents", required=True, type=int)
    parser.add_argument("--project-name", default=os.environ.get("PROJECT_NAME", "liderahenk-test"))
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()
    return bootstrap_runtime(
        profile=args.profile,
        expected_agents=args.agents,
        project_name=args.project_name,
        build=not args.no_build,
    )


if __name__ == "__main__":
    raise SystemExit(main())
