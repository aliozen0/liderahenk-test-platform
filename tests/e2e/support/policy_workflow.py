"""
PolicyWorkflow — extracted from BackendFacade to satisfy SRP.
Handles policy roundtrip execution, lifecycle capability resolution,
and scenario mutation support analysis.
"""
from __future__ import annotations

import inspect
import os
from typing import Any

import requests

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter


class PolicyWorkflow:
    """Orchestrates user-group policy lifecycle for testing."""

    def __init__(self, api_adapter: LiderApiAdapter, xmpp_adapter: XmppMessageAdapter):
        self.api_adapter = api_adapter
        self.xmpp_adapter = xmpp_adapter

    # ── Lifecycle capability resolution ──

    def _get_adapter_method(self, method_name: str):
        try:
            inspect.getattr_static(self.api_adapter, method_name)
        except AttributeError:
            return None
        method = getattr(self.api_adapter, method_name, None)
        return method if callable(method) else None

    def _legacy_lifecycle_capability(
        self,
        *,
        capability: str,
        method_name: str,
        enabled_reason: str,
        disabled_reason: str,
    ) -> dict[str, Any] | None:
        legacy_method = self._get_adapter_method(method_name)
        if legacy_method is None:
            return None
        enabled = legacy_method() is True
        return {
            "capability": capability,
            "enabled": enabled,
            "status": "legacy-bool",
            "reason": enabled_reason if enabled else disabled_reason,
            "source": method_name,
        }

    def _normalize_lifecycle_descriptor(
        self,
        *,
        capability: str,
        descriptor: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        normalized = dict(descriptor)
        normalized.setdefault("capability", capability)
        normalized.setdefault("source", source)

        if isinstance(normalized.get("runtimeVerified"), bool):
            normalized.setdefault("configured", bool(normalized.get("endpoint")))
            normalized["enabled"] = bool(normalized["runtimeVerified"])
            return normalized

        status = normalized.get("status")
        if status == "configured":
            normalized["configured"] = True
            normalized["runtimeVerified"] = False
            normalized["enabled"] = False
            normalized.setdefault("mode", "configured-not-verified")
            return normalized

        if status == "disabled":
            normalized.setdefault("configured", False)
            normalized["runtimeVerified"] = False
            normalized["enabled"] = False
            return normalized

        return normalized

    def _resolve_lifecycle_capability(
        self,
        *,
        capability: str,
        descriptor_method_name: str,
        legacy_method_name: str,
        missing_reason: str,
        invalid_reason: str,
        legacy_enabled_reason: str,
        legacy_disabled_reason: str,
        probe: bool,
    ) -> dict[str, Any]:
        descriptor_method = self._get_adapter_method(descriptor_method_name)
        raw_descriptor = None
        if descriptor_method is not None:
            try:
                raw_descriptor = descriptor_method(probe=probe)
            except TypeError:
                raw_descriptor = descriptor_method()

        if isinstance(raw_descriptor, dict) and isinstance(raw_descriptor.get("enabled"), bool):
            return self._normalize_lifecycle_descriptor(
                capability=capability,
                descriptor=raw_descriptor,
                source=descriptor_method_name,
            )

        legacy_descriptor = self._legacy_lifecycle_capability(
            capability=capability,
            method_name=legacy_method_name,
            enabled_reason=legacy_enabled_reason,
            disabled_reason=legacy_disabled_reason,
        )
        if legacy_descriptor is not None:
            if raw_descriptor is not None:
                legacy_descriptor["fallbackFrom"] = descriptor_method_name
                legacy_descriptor["fallbackReason"] = invalid_reason
            return legacy_descriptor

        if raw_descriptor is not None:
            return {
                "capability": capability,
                "enabled": False,
                "status": "invalid",
                "reason": invalid_reason,
                "source": descriptor_method_name,
                "rawType": type(raw_descriptor).__name__,
            }

        return {
            "capability": capability,
            "enabled": False,
            "status": "unknown",
            "reason": missing_reason,
        }

    def describe_lifecycle_capabilities(self, *, probe: bool = False) -> dict[str, Any]:
        return {
            "create_user_via_ui": self._resolve_lifecycle_capability(
                capability="create_user_via_ui",
                descriptor_method_name="directory_user_create_capability",
                legacy_method_name="supports_directory_user_create",
                missing_reason="Adapter does not expose directory_user_create_capability() or supports_directory_user_create().",
                invalid_reason="Adapter returned an invalid directory_user_create_capability() descriptor.",
                legacy_enabled_reason="Adapter reports create_user_via_ui support via supports_directory_user_create().",
                legacy_disabled_reason="Adapter reports create_user_via_ui is disabled via supports_directory_user_create().",
                probe=probe,
            ),
            "assign_user_to_group_via_ui": self._resolve_lifecycle_capability(
                capability="assign_user_to_group_via_ui",
                descriptor_method_name="user_group_membership_update_capability",
                legacy_method_name="supports_user_group_membership_update",
                missing_reason=(
                    "Adapter does not expose user_group_membership_update_capability() "
                    "or supports_user_group_membership_update()."
                ),
                invalid_reason="Adapter returned an invalid user_group_membership_update_capability() descriptor.",
                legacy_enabled_reason=(
                    "Adapter reports assign_user_to_group_via_ui support via "
                    "supports_user_group_membership_update()."
                ),
                legacy_disabled_reason=(
                    "Adapter reports assign_user_to_group_via_ui is disabled via "
                    "supports_user_group_membership_update()."
                ),
                probe=probe,
            ),
        }

    def get_supported_mutation_steps(self) -> set[str]:
        supported = {
            "create_group_via_ui",
            "assign_user_to_group_via_ui",
            "create_policy_via_ui",
            "assign_policy_to_group_via_ui",
        }
        if self.describe_lifecycle_capabilities()["create_user_via_ui"]["enabled"] is True:
            supported.add("create_user_via_ui")
        return supported

    # ── Scenario mutation support ──

    def describe_scenario_mutation_support(self, scenario_name: str, *, load_scenario_pack) -> dict[str, Any]:
        scenario = load_scenario_pack(scenario_name)
        mutation_steps = [step for step in scenario["steps"] if step.endswith("_via_ui")]
        supported_steps = [step for step in mutation_steps if step in self.get_supported_mutation_steps()]
        unsupported_steps = [step for step in mutation_steps if step not in self.get_supported_mutation_steps()]
        return {
            "name": scenario["name"],
            "mutationSteps": mutation_steps,
            "supportedSteps": supported_steps,
            "unsupportedSteps": unsupported_steps,
        }

    # ── Cleanup ──

    def cleanup_roundtrip_artifacts(
        self,
        *,
        policy: dict[str, Any] | None = None,
        profile: dict[str, Any] | None = None,
        group_dn: str | None = None,
        delete_group: bool = False,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []

        operations = []
        policy_id = (policy or {}).get("id") or (policy or {}).get("policyId")
        if policy_id is not None:
            operations.append(("policy", str(policy_id), "delete_policy", {"policy_id": int(policy_id)}))
        profile_id = (profile or {}).get("id") or (profile or {}).get("profileId")
        if profile_id is not None:
            operations.append(("profile", str(profile_id), "delete_profile", {"profile_id": int(profile_id)}))
        if delete_group and group_dn:
            operations.append(("group", group_dn, "delete_user_group", {"dn": group_dn}))

        for resource, identifier, method_name, kwargs in operations:
            attempts.append({"resource": resource, "identifier": identifier, "method": method_name})
            try:
                getattr(self.api_adapter, method_name)(**kwargs)
            except Exception as exc:
                failures.append({"resource": resource, "identifier": identifier, "method": method_name, "error": str(exc)})

        if not attempts:
            status = "not_required"
        elif failures:
            status = "partial_failure"
        else:
            status = "completed"
        return {"status": status, "attempted": attempts, "failed": failures}

    # ── Policy roundtrip ──

    def execute_user_group_policy_roundtrip(
        self,
        scenario_name: str,
        *,
        group_name: str,
        user_uid: str = "user-standard-001",
        create_user_uid: str | None = None,
        existing_group_dn: str | None = None,
        selected_ou_dn: str | None = None,
        script_contents: str = "#!/bin/bash\nprintf 'policy-roundtrip\\n'",
        load_scenario_pack,
        build_directory_user_entry,
        get_directory_user_base_dn,
        get_user_group_base_dn,
        get_existing_user_group_dn,
        add_directory_user_to_existing_group,
    ) -> dict[str, Any]:
        support = self.describe_scenario_mutation_support(scenario_name, load_scenario_pack=load_scenario_pack)
        required_steps = {"create_policy_via_ui", "assign_policy_to_group_via_ui"}
        if not required_steps.issubset(set(support["supportedSteps"])):
            raise ValueError(
                f"scenario {scenario_name!r} does not expose the required supported mutation steps: {sorted(required_steps)}"
            )

        selected_ou_dn = selected_ou_dn or get_user_group_base_dn()
        created_user_result: dict[str, Any] | None = None
        active_user_uid = user_uid
        group_result: dict[str, Any] | None = None
        profile: dict[str, Any] | None = None
        policy: dict[str, Any] | None = None
        group_dn: str | None = existing_group_dn
        cleanup: dict[str, Any] | None = None
        delete_group = False
        if create_user_uid is not None:
            create_user_capability = self.describe_lifecycle_capabilities()["create_user_via_ui"]
            create_user_configured = bool(create_user_capability.get("configured", create_user_capability.get("enabled")))
            if create_user_configured is not True:
                raise ValueError(f"scenario {scenario_name!r} does not currently configure create_user_via_ui")
            active_user_uid = create_user_uid
            created_user_result = self.api_adapter.create_directory_user(
                uid=create_user_uid,
                common_name=create_user_uid.replace("-", " ").title(),
                surname="Scenario",
                selected_ou_dn=get_directory_user_base_dn(),
            )

        checked_entries = [build_directory_user_entry(active_user_uid)]
        execution_mode = "group_create"
        fallback_reason: str | None = None
        result: dict[str, Any] | None = None
        try:
            if existing_group_dn is not None:
                group_result = add_directory_user_to_existing_group(
                    group_dn=existing_group_dn,
                    user_uid=active_user_uid,
                )
                execution_mode = "existing_group_membership_update"
            else:
                try:
                    group_result = self.api_adapter.create_user_group(
                        group_name=group_name,
                        checked_entries=checked_entries,
                        selected_ou_dn=selected_ou_dn,
                    )
                    group_dn = (
                        group_result.get("distinguishedName")
                        or group_result.get("dn")
                        or f"cn={group_name},{selected_ou_dn}"
                    )
                    delete_group = True
                except requests.HTTPError as exc:
                    response = getattr(exc, "response", None)
                    status_code = getattr(response, "status_code", None)
                    if create_user_uid is not None or status_code not in {406, 417}:
                        raise
                    existing_group_dn = get_existing_user_group_dn()
                    group_result = {"distinguishedName": existing_group_dn, "fallback": "existing_user_group"}
                    group_dn = existing_group_dn
                    execution_mode = "existing_group_fallback"
                    fallback_reason = f"create_user_group returned HTTP {status_code}"

            profile_label = f"{group_name}-script-profile"
            policy_label = f"{group_name}-policy"
            profile = self.api_adapter.create_script_profile(
                label=profile_label,
                description=f"Scenario {scenario_name} script profile",
                script_contents=script_contents,
            )
            policy = self.api_adapter.create_policy(
                label=policy_label,
                description=f"Scenario {scenario_name} policy",
                profiles=[profile],
                active=False,
            )
            policy_id = int(policy.get("id") or policy.get("policyId"))
            group_dn = (
                group_result.get("distinguishedName")
                or group_result.get("dn")
                or existing_group_dn
                or f"cn={group_name},{selected_ou_dn}"
            )
            execution_response = self.api_adapter.execute_policy(policy_id=policy_id, dn=group_dn)
            applied_steps = set(required_steps)
            if execution_mode == "group_create":
                applied_steps.add("create_group_via_ui")
                applied_steps.add("assign_user_to_group_via_ui")
            elif execution_mode == "existing_group_membership_update":
                applied_steps.add("assign_user_to_group_via_ui")
            if created_user_result is not None:
                applied_steps.add("create_user_via_ui")
            result = {
                "scenario": scenario_name,
                "appliedSteps": sorted(applied_steps),
                "createdUser": created_user_result,
                "activeUserUid": active_user_uid,
                "groupName": group_name,
                "groupDn": group_dn,
                "groupResult": group_result,
                "profile": profile,
                "policy": policy,
                "policyExecutionStatusCode": execution_response.status_code,
                "executionMode": execution_mode,
                "fallbackReason": fallback_reason,
            }
        finally:
            cleanup = self.cleanup_roundtrip_artifacts(
                policy=policy, profile=profile, group_dn=group_dn, delete_group=delete_group,
            )
        if result is not None:
            result["cleanup"] = cleanup
            return result
        raise RuntimeError("roundtrip execution did not produce a result")
