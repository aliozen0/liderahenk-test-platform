"""Mutation and session step capability analysis."""
from __future__ import annotations

import os
from typing import Any

from adapters.lider_api_adapter import LiderApiAdapter

from .mutation_evidence import load_ui_mutation_evidence


_RUNTIME_VERIFICATION_CACHE: dict[str, dict[str, Any]] = {}


def mark_mutation_runtime_verified(capability: str, *, evidence: dict[str, Any] | None = None) -> None:
    _RUNTIME_VERIFICATION_CACHE[capability] = {
        "verified": True,
        "evidence": dict(evidence or {}),
    }


def get_mutation_runtime_verification(capability: str) -> dict[str, Any] | None:
    return _RUNTIME_VERIFICATION_CACHE.get(capability)


def clear_mutation_runtime_verification(capability: str | None = None) -> None:
    if capability is None:
        _RUNTIME_VERIFICATION_CACHE.clear()
        return
    _RUNTIME_VERIFICATION_CACHE.pop(capability, None)


MUTATION_STEP_CAPABILITIES = {
    "create_user_via_ui": {
        "adapterMethod": "create_directory_user",
        "surface": "directory_user",
        "capabilityEnv": "LIDER_DIRECTORY_USER_CREATE_ENDPOINT",
        "capabilityMethod": "supports_directory_user_create",
    },
    "create_group_via_ui": {
        "adapterMethod": "create_user_group",
        "surface": "user_group",
    },
    "assign_user_to_group_via_ui": {
        "adapterMethod": "create_user_group",
        "surface": "user_group_membership",
        "mode": "membership_on_group_create",
        "note": (
            "Official create-new-group flow accepts checked user entries, so the first "
            "membership assignment is supported during group creation."
        ),
        "conditionalMode": {
            "name": "existing_group_membership_update",
            "adapterMethod": "add_directory_entries_to_user_group",
            "capabilityEnv": "LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT",
            "capabilityMethod": "supports_user_group_membership_update",
        },
    },
    "create_policy_via_ui": {
        "adapterMethod": "create_policy",
        "surface": "policy",
    },
    "assign_policy_to_group_via_ui": {
        "adapterMethod": "execute_policy",
        "surface": "policy_assignment",
    },
}

SESSION_STEP_CAPABILITIES = {
    "simulate_login": {
        "runtimeCheck": "ui_login",
        "surface": "session_login",
    },
    "verify_effect": {
        "surface": "session_effect",
        "supported": True,
        "runtimeCheck": "policy_effect_probe",
        "mode": "policy_command_history",
        "note": (
            "Post-login business-effect verification probe. Executes a lightweight "
            "policy roundtrip and verifies the command execution result appears in "
            "the command history API, proving a real observable side-effect."
        ),
    },
    "collect_ui_tree_snapshot": {
        "surface": "ui_tree_snapshot",
        "supported": True,
        "operationalCheck": "ui_agent_visibility",
        "mode": "runtime_operational_snapshot",
        "note": "Runtime operational checks already verify the UI tree visibility lane.",
    },
    "collect_membership_snapshot": {
        "surface": "membership_snapshot",
        "runtimeCheck": "membership_snapshot_contract",
        "mode": "user_group_tree_summary",
        "note": (
            "Membership evidence is collected as a lightweight summary from the "
            "user-group tree returned by the official Lider API surface."
        ),
    },
    "collect_policy_snapshot": {
        "surface": "policy_snapshot",
        "runtimeCheck": "policy_snapshot_contract",
        "mode": "active_policy_list",
        "note": (
            "Policy snapshot is collected from the active-policies API surface, "
            "providing evidence of policy lifecycle state in the platform."
        ),
    },
}


def mutation_step_support(*, allow_runtime_verification: bool = False) -> dict[str, Any]:
    support: dict[str, Any] = {}
    mutation_evidence = load_ui_mutation_evidence() if allow_runtime_verification else {}
    verified_steps = mutation_evidence.get("verifiedSteps", {}) if isinstance(mutation_evidence, dict) else {}
    for step_name, rule in MUTATION_STEP_CAPABILITIES.items():
        if step_name == "assign_user_to_group_via_ui":
            base_adapter_method = str(rule.get("adapterMethod") or "")
            conditional_mode = dict(rule.get("conditionalMode") or {})
            conditional_adapter_method = str(conditional_mode.get("adapterMethod") or "")
            conditional_capability_method = str(conditional_mode.get("capabilityMethod") or "")
            conditional_capability_env = str(conditional_mode.get("capabilityEnv") or "")
            conditional_configured = bool(
                conditional_capability_env and os.environ.get(conditional_capability_env, "").strip()
            )
            conditional_evidence = verified_steps.get(step_name, {})
            conditional_runtime_verified = (
                allow_runtime_verification
                and isinstance(conditional_evidence, dict)
                and conditional_evidence.get("runtimeVerified") is True
                and conditional_evidence.get("mode") == conditional_mode.get("name")
            )
            supported = bool(base_adapter_method and hasattr(LiderApiAdapter, base_adapter_method))
            note = str(rule.get("note") or "")
            if conditional_runtime_verified:
                note = (
                    f"{note} Existing-group membership mutation is runtime-verified by the "
                    "active ui-user-policy-roundtrip acceptance lane."
                )
            elif conditional_configured:
                note = (
                    f"{note} Existing-group membership mutation is configured via "
                    f"{conditional_capability_env}, but it is not runtime-verified yet."
                )
            elif conditional_capability_env:
                note = (
                    f"{note} Set {conditional_capability_env} to enable existing-group "
                    "membership mutation after the group already exists."
                )
            support[step_name] = {
                "surface": rule["surface"],
                "supported": supported,
                "adapterMethod": base_adapter_method,
                "mode": rule["mode"],
                "note": note,
                "conditionalModes": [
                    {
                        "name": conditional_mode.get("name"),
                        "enabled": conditional_runtime_verified,
                        "configured": conditional_configured,
                        "runtimeVerified": conditional_runtime_verified,
                        "status": (
                            "runtime-verified"
                            if conditional_runtime_verified
                            else "configured" if conditional_configured else "disabled"
                        ),
                        "adapterMethod": conditional_adapter_method,
                        "capabilityEnv": conditional_capability_env,
                        "capabilityMethod": conditional_capability_method,
                    }
                ],
            }
            continue
        method_name = rule.get("adapterMethod")
        supported = bool(method_name and hasattr(LiderApiAdapter, str(method_name)))
        if step_name == "create_user_via_ui":
            capability_method = str(rule.get("capabilityMethod") or "")
            capability_env = str(rule.get("capabilityEnv") or "")
            capability_configured = bool(os.environ.get(capability_env, "").strip()) if capability_env else False
            adapter_supports = bool(
                capability_method and hasattr(LiderApiAdapter, capability_method)
            )
            configured = supported and adapter_supports and capability_configured
            create_user_evidence = verified_steps.get(step_name, {})
            runtime_verified = (
                allow_runtime_verification
                and isinstance(create_user_evidence, dict)
                and create_user_evidence.get("runtimeVerified") is True
            )
            supported = runtime_verified
        support[step_name] = {
            "surface": rule["surface"],
            "supported": supported,
        }
        if method_name:
            support[step_name]["adapterMethod"] = method_name
        if step_name == "create_user_via_ui":
            support[step_name]["capabilityEnv"] = rule["capabilityEnv"]
            support[step_name]["capabilityMethod"] = rule["capabilityMethod"]
            support[step_name]["configured"] = configured
            support[step_name]["runtimeVerified"] = runtime_verified
            support[step_name]["status"] = (
                "runtime-verified"
                if runtime_verified
                else "configured" if configured else "disabled"
            )
            if runtime_verified:
                support[step_name]["mode"] = "ui-first-postcondition"
                support[step_name]["note"] = (
                    "Official directory user create flow is runtime-verified by the active "
                    "ui-user-policy-roundtrip acceptance lane."
                )
            elif configured:
                support[step_name]["mode"] = "configured-not-verified"
                support[step_name]["note"] = (
                    "Official directory user create flow is configured through "
                    f"{rule['capabilityEnv']}, but it is not runtime-verified yet."
                )
            else:
                support[step_name]["note"] = (
                    "Official directory user create endpoint is not configured. "
                    f"Set {rule['capabilityEnv']} to expose create_user_via_ui."
                )
        if rule.get("mode"):
            support[step_name]["mode"] = rule["mode"]
        if rule.get("note"):
            support[step_name]["note"] = rule["note"]
    return support


def session_step_support(*, available_checks: set[str]) -> dict[str, Any]:
    support: dict[str, Any] = {}
    for step_name, rule in SESSION_STEP_CAPABILITIES.items():
        if "runtimeCheck" in rule:
            supported = str(rule["runtimeCheck"]) in available_checks
        else:
            supported = bool(rule.get("supported", False))
        support[step_name] = {
            "surface": rule["surface"],
            "supported": supported,
        }
        if rule.get("runtimeCheck"):
            support[step_name]["runtimeCheck"] = rule["runtimeCheck"]
        if rule.get("operationalCheck"):
            support[step_name]["operationalCheck"] = rule["operationalCheck"]
        if rule.get("mode"):
            support[step_name]["mode"] = rule["mode"]
        if rule.get("note"):
            support[step_name]["note"] = rule["note"]
    return support


def session_support_summary(
    *,
    scenario_support: dict[str, Any],
    available_checks: set[str],
) -> dict[str, Any]:
    session_support = session_step_support(available_checks=available_checks)
    active_session_scenarios: list[str] = []
    declared_session_steps: set[str] = set()
    catalog_session_steps: set[str] = set()
    for name, scenario in scenario_support.get("scenarios", {}).items():
        if not isinstance(scenario, dict):
            continue
        scenario_steps = [
            step
            for step in scenario.get("declaredSteps", [])
            if step in session_support
        ]
        catalog_session_steps.update(scenario_steps)
        if scenario_steps and scenario.get("active") is True:
            active_session_scenarios.append(name)
            declared_session_steps.update(scenario_steps)

    declared_steps = sorted(declared_session_steps)
    catalog_declared_steps = sorted(catalog_session_steps)
    supported_declared_steps = [
        step for step in declared_steps
        if session_support.get(step, {}).get("supported") is True
    ]
    unsupported_declared_steps = [
        step for step in declared_steps
        if step not in supported_declared_steps
    ]
    catalog_supported_declared_steps = [
        step for step in catalog_declared_steps
        if session_support.get(step, {}).get("supported") is True
    ]
    catalog_unsupported_declared_steps = [
        step for step in catalog_declared_steps
        if step not in catalog_supported_declared_steps
    ]
    return {
        "activeScenarios": active_session_scenarios,
        "declaredSteps": declared_steps,
        "supportedDeclaredSteps": supported_declared_steps,
        "unsupportedDeclaredSteps": unsupported_declared_steps,
        "catalogDeclaredSteps": catalog_declared_steps,
        "catalogSupportedDeclaredSteps": catalog_supported_declared_steps,
        "catalogUnsupportedDeclaredSteps": catalog_unsupported_declared_steps,
        "declaredStepCatalog": {
            step: session_support.get(step, {"supported": False})
            for step in declared_steps
        },
        "catalogDeclaredStepCatalog": {
            step: session_support.get(step, {"supported": False})
            for step in catalog_declared_steps
        },
    }


def support_summary(
    *,
    profile: str,
    topology: dict[str, Any],
    env: dict[str, str],
    scenario_runners: dict[str, Any] | None = None,
    scenario_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from platform_runtime.scenario_runner import collect_scenario_support_summary

    if scenario_runners is None:
        from platform_runtime.readiness import _scenario_runner_registry
        scenario_runners = _scenario_runner_registry()

    verified_scenarios = {
        name
        for name, data in ((scenario_report or {}).get("scenarios") or {}).items()
        if isinstance(data, dict) and data.get("status") == "pass"
    }
    mutation_evidence = load_ui_mutation_evidence()
    mutation_support_data = mutation_step_support(
        allow_runtime_verification=bool(mutation_evidence) or "ui-user-policy-roundtrip" in verified_scenarios,
    )
    scenario_support = collect_scenario_support_summary(
        profile=profile,
        topology_name=str(topology.get("name") or profile),
        env=env,
        check_runners=scenario_runners,
        mutation_support=mutation_support_data,
    )
    available_checks = set((scenario_runners or {}).keys())
    available_checks.add("ui_agent_visibility")
    session_support = session_support_summary(
        scenario_support=scenario_support,
        available_checks=available_checks,
    )
    declared_mutation_steps = sorted(
        {
            step
            for item in scenario_support["scenarios"].values()
            if isinstance(item, dict) and item.get("active") is True
            for step in item.get("mutationSteps", [])
        }
    )
    catalog_declared_mutation_steps = sorted(
        {
            step
            for item in scenario_support["scenarios"].values()
            if isinstance(item, dict)
            for step in item.get("mutationSteps", [])
        }
    )
    supported_declared_steps = [
        step for step in declared_mutation_steps
        if mutation_support_data.get(step, {}).get("supported") is True
    ]
    unsupported_declared_steps = [
        step for step in declared_mutation_steps
        if step not in supported_declared_steps
    ]
    catalog_supported_declared_steps = [
        step for step in catalog_declared_mutation_steps
        if mutation_support_data.get(step, {}).get("supported") is True
    ]
    catalog_unsupported_declared_steps = [
        step for step in catalog_declared_mutation_steps
        if step not in catalog_supported_declared_steps
    ]
    return {
        "topology": {
            "profile": topology.get("name"),
            "managedEndpoints": topology.get("managedEndpoints"),
            "operatorCount": topology.get("operatorCount"),
            "directoryUserCount": topology.get("directoryUserCount"),
            "userGroupCount": topology.get("userGroupCount"),
            "endpointGroupCount": topology.get("endpointGroupCount"),
            "policyPack": topology.get("policyPack"),
            "sessionPack": topology.get("sessionPack"),
        },
        "scenarios": scenario_support,
        "mutationSupport": {
            "catalog": mutation_support_data,
            "declaredSteps": declared_mutation_steps,
            "supportedDeclaredSteps": supported_declared_steps,
            "unsupportedDeclaredSteps": unsupported_declared_steps,
            "catalogDeclaredSteps": catalog_declared_mutation_steps,
            "catalogSupportedDeclaredSteps": catalog_supported_declared_steps,
            "catalogUnsupportedDeclaredSteps": catalog_unsupported_declared_steps,
            "declaredStepCatalog": {
                step: mutation_support_data.get(step, {"supported": False})
                for step in declared_mutation_steps
            },
            "catalogDeclaredStepCatalog": {
                step: mutation_support_data.get(step, {"supported": False})
                for step in catalog_declared_mutation_steps
            },
        },
        "sessionSupport": session_support,
    }
