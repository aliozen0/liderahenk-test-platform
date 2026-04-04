from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolve_topology_profile_uses_runtime_defaults():
    loader = _load_module("platform/topology/profile_loader.py", "topology_profile_loader")

    topology = loader.resolve_topology_profile("dev-fidelity", expected_agents=10, env={})

    assert topology["name"] == "dev-fidelity"
    assert topology["managed_endpoint_count"] == 10
    assert topology["operators"]["count"] == 3
    assert topology["directory_users"]["count"] == 12
    assert topology["user_groups"]["count"] == 4
    assert topology["endpoint_groups"]["count"] == 3
    assert topology["env"]["POLICY_PACK"] == "baseline-standard"
    assert topology["ldap_bind_mode"] == "service-account"
    assert topology["env"]["LIDER_LDAP_BIND_MODE"] == "service-account"


def test_resolve_topology_profile_applies_env_overrides():
    loader = _load_module("platform/topology/profile_loader.py", "topology_profile_loader")

    topology = loader.resolve_topology_profile(
        "dev-fidelity",
        expected_agents=10,
        env={
            "TOPOLOGY_PROFILE": "dev-fidelity",
            "OPERATOR_COUNT": "5",
            "DIRECTORY_USER_COUNT": "50",
            "USER_GROUP_COUNT": "6",
            "ENDPOINT_GROUP_COUNT": "4",
            "POLICY_PACK": "baseline-heavy",
            "SESSION_PACK": "login-advanced",
            "LIDER_LDAP_BIND_MODE": "authenticated-user",
        },
    )

    assert topology["operators"]["count"] == 5
    assert topology["directory_users"]["count"] == 50
    assert topology["user_groups"]["count"] == 6
    assert topology["endpoint_groups"]["count"] == 4
    assert topology["policy_pack"] == "baseline-heavy"
    assert topology["session_pack"] == "login-advanced"
    assert topology["ldap_bind_mode"] == "authenticated-user"
    assert topology["env"]["DIRECTORY_USER_COUNT"] == "50"


def test_resolve_topology_profile_rejects_runtime_mismatch():
    loader = _load_module("platform/topology/profile_loader.py", "topology_profile_loader")

    with pytest.raises(ValueError, match="targets runtime"):
        loader.resolve_topology_profile(
            "dev-fidelity",
            expected_agents=10,
            env={"TOPOLOGY_PROFILE": "dev-fast"},
        )


def test_bootstrap_runtime_env_includes_topology_exports(monkeypatch):
    bootstrap_runtime = _load_module("platform/scripts/bootstrap_runtime.py", "bootstrap_runtime")
    monkeypatch.setenv("TOPOLOGY_PROFILE", "dev-fidelity")
    monkeypatch.setenv("DIRECTORY_USER_COUNT", "50")
    monkeypatch.setenv("POLICY_PACK", "baseline-heavy")
    monkeypatch.setenv("LIDER_LDAP_BIND_MODE", "authenticated-user")

    env, topology = bootstrap_runtime._runtime_env("dev-fidelity", 10, "liderahenk-test")

    assert env["AHENK_COUNT"] == "10"
    assert env["PLATFORM_RUNTIME_PROFILE"] == "dev-fidelity"
    assert env["PROJECT_NAME"] == "liderahenk-test"
    assert env["TOPOLOGY_PROFILE"] == "dev-fidelity"
    assert env["DIRECTORY_USER_COUNT"] == "50"
    assert env["POLICY_PACK"] == "baseline-heavy"
    assert env["LIDER_LDAP_BIND_MODE"] == "authenticated-user"
    assert topology["directory_users"]["count"] == 50
    assert topology["policy_pack"] == "baseline-heavy"
