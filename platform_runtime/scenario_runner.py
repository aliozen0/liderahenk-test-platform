from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Callable, Mapping

SCENARIO_LOADER_PATH = Path(__file__).resolve().parents[1] / "platform" / "scenarios" / "scenario_loader.py"


def _load_scenario_loader_module():
    spec = importlib.util.spec_from_file_location("runtime_scenario_loader", SCENARIO_LOADER_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive branch
        raise RuntimeError(f"unable to load scenario loader from {SCENARIO_LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_check(
    *,
    check_id: str,
    category: str,
    description: str,
    passed: bool,
    actual: Any = None,
    expected: Any = None,
    details: Any = None,
) -> dict[str, Any]:
    payload = {
        "id": check_id,
        "category": category,
        "description": description,
        "status": "pass" if passed else "fail",
    }
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if details is not None:
        payload["details"] = details
    return payload


def _parse_runtime_checks(pack: Mapping[str, Any]) -> list[str]:
    runtime_checks = pack.get("runtime_checks", [])
    if runtime_checks is None:
        return []
    if not isinstance(runtime_checks, list):
        raise ValueError(f"scenario pack {pack.get('name')!r} must define runtime_checks as a list")
    normalized: list[str] = []
    for item in runtime_checks:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"scenario pack {pack.get('name')!r} contains an invalid runtime check: {item!r}")
        normalized.append(item.strip())
    return normalized


def resolve_active_scenarios(env: Mapping[str, str] | None = None) -> list[str]:
    env_map = dict(os.environ if env is None else env)
    explicit = [item.strip() for item in env_map.get("PLATFORM_SCENARIO_PACKS", "").split(",") if item.strip()]
    if explicit:
        return list(dict.fromkeys(explicit))

    defaults: list[str] = []
    session_pack = env_map.get("SESSION_PACK", "").strip()
    if session_pack:
        candidate = f"session-{session_pack}"
        loader = _load_scenario_loader_module()
        if candidate in set(loader.available_scenarios()):
            defaults.append(candidate)
    return defaults


def collect_scenario_support_summary(
    *,
    profile: str,
    topology_name: str,
    env: Mapping[str, str] | None = None,
    check_runners: Mapping[str, Callable[[], dict[str, Any]]] | None = None,
    mutation_support: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    env_map = dict(os.environ if env is None else env)
    loader = _load_scenario_loader_module()
    active = resolve_active_scenarios(env_map)
    available = loader.available_scenarios()
    runner_registry = sorted((check_runners or {}).keys())
    mutation_catalog = dict(mutation_support or {})
    scenario_catalog: dict[str, Any] = {}

    for name in available:
        try:
            pack = loader.load_scenario_pack(name)
            runtime_checks = _parse_runtime_checks(pack)
        except Exception as exc:
            scenario_catalog[name] = {
                "status": "load_error",
                "error": str(exc),
                "active": name in active,
            }
            continue

        mutation_steps = [
            step for step in pack["steps"]
            if isinstance(step, str) and "_via_" in step
        ]
        supported_steps = [
            step for step in mutation_steps
            if mutation_catalog.get(step, {}).get("supported") is True
        ]
        unsupported_steps = [
            step for step in mutation_steps
            if step not in supported_steps
        ]
        mutation_step_details = {
            step: mutation_catalog.get(step, {"supported": False})
            for step in mutation_steps
        }
        scenario_catalog[name] = {
            "active": name in active,
            "requiredTopologyProfile": pack["requires"]["topology_profile"],
            "topologyMatch": pack["requires"]["topology_profile"] == topology_name,
            "stepCount": len(pack["steps"]),
            "declaredSteps": list(pack["steps"]),
            "mutationSteps": mutation_steps,
            "mutationStepDetails": mutation_step_details,
            "supportedMutationSteps": supported_steps,
            "unsupportedMutationSteps": unsupported_steps,
            "runtimeChecks": runtime_checks,
            "missingRuntimeChecks": [
                runtime_check for runtime_check in runtime_checks
                if runtime_check not in runner_registry
            ],
        }

    return {
        "profile": profile,
        "topologyProfile": topology_name,
        "activeScenarios": active,
        "availableScenarios": available,
        "runtimeCheckRegistry": runner_registry,
        "scenarios": scenario_catalog,
    }


def collect_scenario_checks(
    *,
    profile: str,
    topology_name: str,
    env: Mapping[str, str] | None = None,
    check_runners: Mapping[str, Callable[[], dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    env_map = dict(os.environ if env is None else env)
    scenario_names = resolve_active_scenarios(env_map)
    checks: list[dict[str, Any]] = []
    report: dict[str, Any] = {"activeScenarios": scenario_names, "scenarios": {}}
    if not scenario_names:
        return checks, report

    runners = dict(check_runners or {})
    for name in scenario_names:
        try:
            loader = _load_scenario_loader_module()
            pack = loader.load_scenario_pack(name)
            runtime_checks = _parse_runtime_checks(pack)
        except Exception as exc:
            report["scenarios"][name] = {"status": "load_error", "error": str(exc)}
            checks.append(
                _build_check(
                    check_id=f"scenario:{name}:load",
                    category="scenario",
                    description=f"Scenario pack {name} loads successfully",
                    passed=False,
                    details=str(exc),
                )
            )
            continue

        expected_profile = pack["requires"]["topology_profile"]
        contract_ok = expected_profile == topology_name and bool(runtime_checks)
        checks.append(
            _build_check(
                check_id=f"scenario:{name}:contract",
                category="scenario",
                description=f"Scenario pack {name} matches topology and defines runtime checks",
                passed=contract_ok,
                actual={
                    "topologyProfile": expected_profile,
                    "runtimeChecks": runtime_checks,
                    "stepCount": len(pack["steps"]),
                },
                expected={"topologyProfile": topology_name, "runtimeChecks": "non-empty"},
            )
        )

        executed_ids: list[str] = []
        scenario_failed = not contract_ok
        for runtime_check in runtime_checks:
            runner = runners.get(runtime_check)
            if runner is None:
                scenario_failed = True
                checks.append(
                    _build_check(
                        check_id=f"scenario:{name}:{runtime_check}",
                        category="scenario",
                        description=f"Scenario runtime check {runtime_check} is registered",
                        passed=False,
                        actual="missing",
                        expected="registered",
                    )
                )
                continue

            base_check = dict(runner())
            executed_ids.append(base_check["id"])
            scenario_check = dict(base_check)
            scenario_check["id"] = f"scenario:{name}:{base_check['id']}"
            scenario_check["category"] = "scenario"
            details = scenario_check.get("details")
            merged_details = dict(details) if isinstance(details, dict) else {}
            if details is not None and not isinstance(details, dict):
                merged_details["runnerDetails"] = details
            merged_details["scenario"] = name
            merged_details["sourceCategory"] = base_check.get("category")
            scenario_check["details"] = merged_details
            if scenario_check["status"] != "pass":
                scenario_failed = True
            checks.append(scenario_check)

        report["scenarios"][name] = {
            "status": "fail" if scenario_failed else "pass",
            "profile": profile,
            "requiredTopologyProfile": expected_profile,
            "runtimeChecks": runtime_checks,
            "executedChecks": executed_ids,
            "stepCount": len(pack["steps"]),
        }
    return checks, report
