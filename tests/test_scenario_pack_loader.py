from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_available_scenarios_lists_seeded_packs():
    loader = _load_module("platform/scenarios/scenario_loader.py", "scenario_pack_loader")

    scenarios = loader.available_scenarios()

    assert "ui-user-policy-roundtrip" in scenarios
    assert "session-login-basic" in scenarios


def test_ui_roundtrip_pack_matches_contract():
    loader = _load_module("platform/scenarios/scenario_loader.py", "scenario_pack_loader")

    scenario = loader.load_scenario_pack("ui-user-policy-roundtrip")

    assert scenario["requires"]["topology_profile"] == "dev-fidelity"
    assert scenario["steps"][:5] == [
        "create_user_via_ui",
        "create_group_via_ui",
        "assign_user_to_group_via_ui",
        "create_policy_via_ui",
        "assign_policy_to_group_via_ui",
    ]


def test_session_pack_remains_small_and_login_focused():
    loader = _load_module("platform/scenarios/scenario_loader.py", "scenario_pack_loader")

    scenario = loader.load_scenario_pack("session-login-basic")

    assert scenario["steps"] == [
        "simulate_login",
        "verify_effect",
        "collect_ui_tree_snapshot",
        "collect_membership_snapshot",
    ]
