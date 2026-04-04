from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import yaml


TOPOLOGY_ROOT = Path(__file__).resolve().parent
TOPOLOGY_CONTRACT_PATH = TOPOLOGY_ROOT.parent / "contracts" / "topology-profile-contract.yaml"
TOPOLOGY_PROFILES_DIR = TOPOLOGY_ROOT / "profiles"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _int_override(name: str, value: str, minimum: int) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {parsed}")
    return parsed


def _topology_contract() -> dict[str, Any]:
    return _read_yaml(TOPOLOGY_CONTRACT_PATH)


def _profile_path(profile_name: str) -> Path:
    return TOPOLOGY_PROFILES_DIR / f"{profile_name}.yaml"


def available_profiles() -> list[str]:
    return sorted(path.stem for path in TOPOLOGY_PROFILES_DIR.glob("*.yaml"))


def resolve_topology_profile(
    runtime_profile: str,
    *,
    expected_agents: int,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    contract = _topology_contract()
    env_values = dict(os.environ if env is None else env)
    selected_name = env_values.get("TOPOLOGY_PROFILE") or contract["selection"]["runtime_defaults"][runtime_profile]
    profile_path = _profile_path(selected_name)
    if not profile_path.exists():
        raise FileNotFoundError(f"topology profile not found: {selected_name}")

    profile = _read_yaml(profile_path)
    profile_runtime = profile["runtime_profile"]
    if profile_runtime != runtime_profile:
        raise ValueError(
            f"topology profile {selected_name!r} targets runtime {profile_runtime!r}, expected {runtime_profile!r}"
        )

    seed_defaults = profile["seed_defaults"]
    resolved = {
        "name": profile["name"],
        "runtime_profile": runtime_profile,
        "managed_endpoint_count": expected_agents,
        "operators": {
            "count": int(seed_defaults["operators"]["count"]),
            "roles": list(seed_defaults["operators"].get("roles", [])),
        },
        "directory_users": {
            "count": int(seed_defaults["directory_users"]["count"]),
            "archetypes": list(seed_defaults["directory_users"].get("archetypes", [])),
        },
        "user_groups": {
            "count": int(seed_defaults["user_groups"]["count"]),
            "archetypes": list(seed_defaults["user_groups"].get("archetypes", [])),
        },
        "endpoint_groups": {
            "count": int(seed_defaults["endpoint_groups"]["count"]),
            "archetypes": list(seed_defaults["endpoint_groups"].get("archetypes", [])),
        },
        "policy_pack": str(seed_defaults["policy_pack"]),
        "session_pack": str(seed_defaults["session_pack"]),
        "ldap_bind_mode": str(profile.get("ldap_bind_mode", "authenticated-user")),
    }

    for env_name, rule in contract["override_env"].items():
        raw_value = env_values.get(env_name)
        if raw_value is None:
            continue
        target = str(rule["target"])
        if rule["type"] == "int":
            value: Any = _int_override(env_name, raw_value, int(rule.get("min", 1)))
        else:
            value = raw_value.strip()
            if not value:
                raise ValueError(f"{env_name} must not be blank")

        if target == "operators.count":
            resolved["operators"]["count"] = value
        elif target == "directory_users.count":
            resolved["directory_users"]["count"] = value
        elif target == "user_groups.count":
            resolved["user_groups"]["count"] = value
        elif target == "endpoint_groups.count":
            resolved["endpoint_groups"]["count"] = value
        elif target == "policy_pack":
            resolved["policy_pack"] = value
        elif target == "session_pack":
            resolved["session_pack"] = value
        elif target == "ldap_bind_mode":
            resolved["ldap_bind_mode"] = value

    resolved["env"] = {
        "TOPOLOGY_PROFILE": resolved["name"],
        "OPERATOR_COUNT": str(resolved["operators"]["count"]),
        "DIRECTORY_USER_COUNT": str(resolved["directory_users"]["count"]),
        "USER_GROUP_COUNT": str(resolved["user_groups"]["count"]),
        "ENDPOINT_GROUP_COUNT": str(resolved["endpoint_groups"]["count"]),
        "POLICY_PACK": resolved["policy_pack"],
        "SESSION_PACK": resolved["session_pack"],
        "LIDER_LDAP_BIND_MODE": resolved["ldap_bind_mode"],
    }
    return resolved
