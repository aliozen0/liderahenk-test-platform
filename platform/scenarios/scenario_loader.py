from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SCENARIO_ROOT = Path(__file__).resolve().parent
SCENARIO_CONTRACT_PATH = SCENARIO_ROOT.parent / "contracts" / "scenario-pack-contract.yaml"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def available_scenarios() -> list[str]:
    return sorted(path.stem for path in SCENARIO_ROOT.glob("*.yaml"))


def load_scenario_pack(name: str) -> dict[str, Any]:
    contract = _read_yaml(SCENARIO_CONTRACT_PATH)
    scenario_path = SCENARIO_ROOT / f"{name}.yaml"
    if not scenario_path.exists():
        raise FileNotFoundError(f"scenario pack not found: {name}")

    scenario = _read_yaml(scenario_path)
    missing = [field for field in contract["required_fields"] if field not in scenario]
    if missing:
        raise ValueError(f"scenario pack {name!r} missing required fields: {missing}")

    requires = scenario["requires"]
    missing_requires = [field for field in contract["requires_fields"] if field not in requires]
    if missing_requires:
        raise ValueError(f"scenario pack {name!r} missing requires fields: {missing_requires}")

    steps = scenario["steps"]
    if not isinstance(steps, list) or not steps:
        raise ValueError(f"scenario pack {name!r} must define a non-empty steps list")

    for step in steps:
        if not isinstance(step, str) or not step.strip():
            raise ValueError(f"scenario pack {name!r} contains an invalid step: {step!r}")

    return scenario
