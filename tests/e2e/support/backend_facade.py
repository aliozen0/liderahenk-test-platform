from __future__ import annotations

import inspect
import importlib.util
import os
import time
from pathlib import Path
from typing import Any

import requests

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from tests.e2e.config.play_config import PlayConfig
from tests.e2e.support.policy_workflow import PolicyWorkflow


SCENARIO_LOADER_PATH = Path(__file__).resolve().parents[3] / "platform" / "scenarios" / "scenario_loader.py"


def _load_scenario_module():
    spec = importlib.util.spec_from_file_location("platform_scenario_loader", SCENARIO_LOADER_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive branch
        raise RuntimeError(f"Unable to load scenario loader from {SCENARIO_LOADER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackendFacade:
    def __init__(self):
        self.api_adapter = LiderApiAdapter(
            base_url=PlayConfig.API_URL,
            username=PlayConfig.ADMIN_USER,
            password=PlayConfig.ADMIN_PASS,
        )
        self.xmpp_adapter = XmppMessageAdapter(
            api_url=PlayConfig.XMPP_URL,
        )
        self._policy_workflow = PolicyWorkflow(self.api_adapter, self.xmpp_adapter)

    def _get_policy_workflow(self) -> PolicyWorkflow:
        policy_workflow = getattr(self, "_policy_workflow", None)
        if policy_workflow is None:
            policy_workflow = PolicyWorkflow(self.api_adapter, self.xmpp_adapter)
            self._policy_workflow = policy_workflow
        return policy_workflow

    @property
    def policy(self) -> PolicyWorkflow:
        return self._get_policy_workflow()

    def wait_for_agent_registration(self, min_count: int = 1, timeout: int = 60) -> bool:
        return self.api_adapter.wait_for_agents(min_count, timeout)

    def is_agent_connected_xmpp(self) -> bool:
        try:
            return self.xmpp_adapter.get_connected_count() > 0
        except Exception:
            return False

    def get_registered_agent_count(self) -> int:
        return self.api_adapter.get_agent_count()

    def get_dashboard_summary(self) -> dict[str, int]:
        dashboard_info = self.api_adapter.get_dashboard_info() or {}
        return {
            "totalComputers": int(dashboard_info.get("totalComputerNumber") or 0),
            "totalUsers": int(dashboard_info.get("totalUserNumber") or 0),
            "totalSentTasks": int(dashboard_info.get("totalSentTaskNumber") or 0),
            "totalAssignedPolicies": int(dashboard_info.get("totalAssignedPolicyNumber") or 0),
        }

    def get_computer_summary_counts(self, search_dn: str = "agents") -> dict[str, int]:
        summary = self.api_adapter.get_computer_agent_counts(search_dn) or {}
        total = int(summary.get("agentListSize") or 0)
        online = int(summary.get("onlineAgentListSize") or 0)
        return {
            "total": total,
            "online": online,
            "offline": max(total - online, 0),
        }

    def wait_for_platform_readiness(self, min_count: int = 1, timeout: int = 120) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.wait_for_agent_registration(min_count=min_count, timeout=5) and self.is_agent_connected_xmpp():
                return True
            time.sleep(3)
        return False

    def get_agents(self) -> list[dict]:
        return self.api_adapter.get_agent_list()

    def _normalize_agent_label(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("-host"):
            text = text[:-5]
        if "," in text and "=" in text:
            head = text.split(",", 1)[0]
            if "=" in head:
                text = head.split("=", 1)[1]
        return text or None

    def _resolve_agent_record(self, agent_label: str) -> dict[str, Any]:
        target = self._normalize_agent_label(agent_label)
        for agent in self.get_agents():
            candidates = (
                agent.get("jid"),
                agent.get("uid"),
                agent.get("cn"),
                agent.get("hostname"),
                agent.get("distinguishedName"),
                agent.get("dn"),
            )
            normalized = [self._normalize_agent_label(item) for item in candidates]
            if target in normalized:
                return agent
        raise LookupError(f"Agent inventory record could not be resolved for label: {agent_label}")

    def _derive_directory_label(self, distinguished_name: str | None) -> str:
        if not distinguished_name:
            return ""
        parts = [segment.strip() for segment in str(distinguished_name).split(",")]
        for segment in parts[1:]:
            if not segment.lower().startswith("ou="):
                continue
            return segment.split("=", 1)[1]
        return ""

    def get_agent_inventory_summary(self, agent_label: str) -> dict[str, str]:
        agent = self._resolve_agent_record(agent_label)
        online = bool(agent.get("isOnline")) or str(agent.get("agentStatus", "")).lower() == "active"
        distinguished_name = agent.get("distinguishedName") or agent.get("dn")
        return {
            "status": "Çevrimiçi" if online else "Çevrimdışı",
            "computerName": str(agent.get("hostname") or ""),
            "directory": self._derive_directory_label(str(distinguished_name or "")),
            "userDomain": str(agent.get("userDirectoryDomain") or ""),
            "ipAddress": str(agent.get("ipAddresses") or ""),
            "macAddress": str(agent.get("macAddresses") or ""),
            "createDate": str(agent.get("createDate") or ""),
        }

    def get_agent_focus_summary(self, agent_label: str) -> dict[str, int]:
        agent = self._resolve_agent_record(agent_label)
        online = bool(agent.get("isOnline")) or str(agent.get("agentStatus", "")).lower() == "active"
        return {
            "total": 1,
            "online": 1 if online else 0,
            "offline": 0 if online else 1,
        }

    def summarize_command_history_entry(self, entry: dict[str, Any]) -> dict[str, str]:
        task = entry.get("task") or {}
        plugin = task.get("plugin") or {}
        executions = entry.get("commandExecutions") or []
        first_execution = executions[0] if executions else {}
        results = first_execution.get("commandExecutionResults") or []
        first_result = results[0] if results else {}
        response_code = str(first_result.get("responseCode") or "")
        result_label = "Başarılı" if response_code.upper() == "TASK_PROCESSED" else "Bilinmiyor"
        return {
            "taskName": str(plugin.get("name") or task.get("commandClsId") or ""),
            "result": result_label,
            "sender": str(entry.get("commandOwnerUid") or ""),
            "createDate": str(first_execution.get("createDate") or task.get("createDate") or ""),
            "executionDate": str(first_result.get("createDate") or ""),
        }

    def get_latest_command_history_summary(self, agent_dn: str) -> dict[str, str]:
        history = self.api_adapter.get_command_history(agent_dn)
        if not history:
            raise LookupError(f"No command history is available for agent DN: {agent_dn}")
        return self.summarize_command_history_entry(history[0])

    def get_first_agent(self) -> dict:
        agents = self.get_agents()
        if not agents:
            raise LookupError("No registered agents are available for the E2E flow.")
        return agents[0]

    def get_agent_dn(self, agent: dict) -> str:
        distinguished_name = (
            agent.get("distinguishedName")
            or agent.get("dn")
        )
        if not distinguished_name:
            raise KeyError("Agent entry does not expose a distinguished name field.")
        return str(distinguished_name)

    def get_first_agent_dn(self) -> str:
        return self.get_agent_dn(self.get_first_agent())

    def get_directory_user_base_dn(self) -> str:
        return os.getenv("LDAP_USER_BASE_DN", "ou=users,dc=liderahenk,dc=org")

    def get_user_group_base_dn(self) -> str:
        return (
            os.getenv("USER_GROUP_LDAP_BASE_DN")
            or os.getenv("LDAP_GROUPS_OU")
            or "ou=Groups,dc=liderahenk,dc=org"
        )

    def build_directory_user_entry(self, uid: str) -> dict[str, str]:
        resolved_entry = self.find_directory_user_entry(uid)
        if resolved_entry is not None:
            entry = dict(resolved_entry)
            entry.setdefault("type", "USER")
            return entry
        dn = f"uid={uid},{self.get_directory_user_base_dn()}"
        return {
            "distinguishedName": dn,
            "dn": dn,
            "uid": uid,
            "name": uid,
            "type": "USER",
        }

    def _iter_tree_nodes(self, nodes: list[dict] | None) -> list[dict]:
        queue = list(nodes or [])
        flattened: list[dict] = []
        while queue:
            node = queue.pop(0)
            if not isinstance(node, dict):
                continue
            flattened.append(node)
            queue.extend(node.get("childEntries", []) or node.get("children", []) or [])
        return flattened

    def get_directory_user_tree(self) -> list[dict]:
        method = inspect.getattr_static(type(self.api_adapter), "get_directory_user_tree", None)
        if method is None:
            return []
        method = getattr(self.api_adapter, "get_directory_user_tree", None)
        if not callable(method):
            return []
        try:
            return method()
        except Exception:
            return []

    def get_user_group_tree(self) -> list[dict]:
        method = inspect.getattr_static(type(self.api_adapter), "get_user_group_tree", None)
        if method is None:
            return []
        method = getattr(self.api_adapter, "get_user_group_tree", None)
        if not callable(method):
            return []
        try:
            return method()
        except Exception:
            return []

    def find_directory_user_entry(self, uid: str) -> dict[str, Any] | None:
        nodes = self._iter_tree_nodes(self.get_directory_user_tree())
        for node in nodes:
            node_uid = node.get("uid") or node.get("name") or node.get("cn")
            if node_uid == uid:
                return node
        return None

    def wait_for_directory_user(self, uid: str, timeout: int = 30) -> dict[str, Any]:
        started = time.time()
        while time.time() - started < timeout:
            entry = self.find_directory_user_entry(uid)
            if entry is not None:
                return entry
            time.sleep(1)
        raise LookupError(f"Directory user could not be resolved within {timeout} seconds: {uid}")

    def get_existing_user_group_entry(self) -> dict[str, Any]:
        nodes = self._iter_tree_nodes(self.get_user_group_tree())
        preferred_names = {"DomainAdmins", "readers"}
        preferred_entry = None
        fallback_entry = None
        for node in nodes:
            if node.get("type") != "GROUP":
                continue
            dn = node.get("distinguishedName") or node.get("dn")
            if not dn:
                continue
            fallback_entry = fallback_entry or node
            name = node.get("cn") or node.get("name")
            if name in preferred_names:
                preferred_entry = node
                break
        entry = preferred_entry or fallback_entry
        if entry is None:
            raise LookupError("No existing user group entry is available for fallback policy execution.")
        return entry

    def get_existing_user_group_dn(self) -> str:
        entry = self.get_existing_user_group_entry()
        distinguished_name = entry.get("distinguishedName") or entry.get("dn")
        if not distinguished_name:
            raise KeyError("Existing user group entry does not expose a distinguished name field.")
        return str(distinguished_name)

    def get_user_group_entry(self, group_dn: str) -> dict[str, Any]:
        for node in self._iter_tree_nodes(self.get_user_group_tree()):
            distinguished_name = node.get("distinguishedName") or node.get("dn")
            if distinguished_name == group_dn:
                return node
        raise LookupError(f"User group could not be resolved: {group_dn}")

    def _group_member_dns(self, group_entry: dict[str, Any]) -> list[str]:
        attributes_multi = group_entry.get("attributesMultiValues") or {}
        if isinstance(attributes_multi.get("member"), list):
            return [str(member) for member in attributes_multi["member"]]
        attributes = group_entry.get("attributes") or {}
        member = attributes.get("member")
        if isinstance(member, list):
            return [str(item) for item in member]
        if isinstance(member, str):
            return [member]
        return []

    def get_user_group_member_dns(self, group_dn: str) -> list[str]:
        return self._group_member_dns(self.get_user_group_entry(group_dn))

    def wait_for_user_group_membership(self, group_dn: str, user_dn: str, timeout: int = 30) -> dict[str, Any]:
        started = time.time()
        while time.time() - started < timeout:
            entry = self.get_user_group_entry(group_dn)
            if user_dn in self._group_member_dns(entry):
                return entry
            time.sleep(1)
        raise LookupError(
            f"User-group membership could not be verified within {timeout} seconds: {user_dn} -> {group_dn}"
        )

    def load_scenario_pack(self, scenario_name: str) -> dict[str, Any]:
        return _load_scenario_module().load_scenario_pack(scenario_name)

    def _get_adapter_method(self, method_name: str):
        return self._policy_workflow._get_adapter_method(method_name)

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
            descriptor = dict(raw_descriptor)
            descriptor.setdefault("capability", capability)
            descriptor.setdefault("source", descriptor_method_name)
            return descriptor

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
        return self._get_policy_workflow().describe_lifecycle_capabilities(probe=probe)

    def get_supported_mutation_steps(self) -> set[str]:
        return self._get_policy_workflow().get_supported_mutation_steps()

    def add_directory_user_to_existing_group(
        self,
        *,
        group_dn: str,
        user_uid: str,
    ) -> dict[str, Any]:
        membership_capability = self.describe_lifecycle_capabilities()["assign_user_to_group_via_ui"]
        membership_configured = bool(membership_capability.get("configured", membership_capability.get("enabled")))
        if membership_configured is not True:
            raise ValueError(
                "Existing user-group membership update is not currently configured for the API adapter. "
                f"Capability status: {membership_capability.get('status')}."
            )

        checked_entries = [self.build_directory_user_entry(user_uid)]
        return self.api_adapter.add_directory_entries_to_user_group(
            group_dn=group_dn,
            checked_entries=checked_entries,
        )

    def describe_scenario_mutation_support(self, scenario_name: str) -> dict[str, Any]:
        return self._get_policy_workflow().describe_scenario_mutation_support(
            scenario_name, load_scenario_pack=self.load_scenario_pack,
        )

    def _cleanup_user_group_roundtrip_artifacts(
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
            attempts.append(
                {
                    "resource": resource,
                    "identifier": identifier,
                    "method": method_name,
                }
            )
            try:
                getattr(self.api_adapter, method_name)(**kwargs)
            except Exception as exc:
                failures.append(
                    {
                        "resource": resource,
                        "identifier": identifier,
                        "method": method_name,
                        "error": str(exc),
                    }
                )

        if not attempts:
            status = "not_required"
        elif failures:
            status = "partial_failure"
        else:
            status = "completed"
        return {
            "status": status,
            "attempted": attempts,
            "failed": failures,
        }

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
    ) -> dict[str, Any]:
        support = self.describe_scenario_mutation_support(scenario_name)
        required_steps = {
            "create_policy_via_ui",
            "assign_policy_to_group_via_ui",
        }
        if not required_steps.issubset(set(support["supportedSteps"])):
            raise ValueError(
                f"scenario {scenario_name!r} does not expose the required supported mutation steps: {sorted(required_steps)}"
            )

        selected_ou_dn = selected_ou_dn or self.get_user_group_base_dn()
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
                raise ValueError(
                    f"scenario {scenario_name!r} does not currently configure create_user_via_ui"
                )
            active_user_uid = create_user_uid
            created_user_result = self.api_adapter.create_directory_user(
                uid=create_user_uid,
                common_name=create_user_uid.replace("-", " ").title(),
                surname="Scenario",
                selected_ou_dn=self.get_directory_user_base_dn(),
            )

        checked_entries = [self.build_directory_user_entry(active_user_uid)]
        execution_mode = "group_create"
        fallback_reason: str | None = None
        result: dict[str, Any] | None = None
        try:
            if existing_group_dn is not None:
                group_result = self.add_directory_user_to_existing_group(
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
                    existing_group_dn = self.get_existing_user_group_dn()
                    group_result = {
                        "distinguishedName": existing_group_dn,
                        "fallback": "existing_user_group",
                    }
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
            cleanup = self._cleanup_user_group_roundtrip_artifacts(
                policy=policy,
                profile=profile,
                group_dn=group_dn,
                delete_group=delete_group,
            )
        if result is not None:
            result["cleanup"] = cleanup
            return result
        raise RuntimeError("roundtrip execution did not produce a result")

    def _find_tree_agent_entry(self, nodes: list[dict], agent_label: str | None = None) -> dict | None:
        for node in nodes or []:
            if node.get("type") in {"AHENK", "WINDOWS_AHENK"}:
                node_label = node.get("uid") or node.get("cn") or node.get("name")
                if agent_label is None or node_label == agent_label:
                    return node
            child_entry = self._find_tree_agent_entry(
                node.get("childEntries", []) or node.get("children", []),
                agent_label=agent_label,
            )
            if child_entry:
                return child_entry
        return None

    def get_tree_agent_entry(self, agent_label: str | None = None) -> dict:
        tree = self.api_adapter.get_computer_tree()
        entry = self._find_tree_agent_entry(tree, agent_label=agent_label)
        if not entry:
            raise LookupError(
                f"Tree entry could not be resolved for agent: {agent_label or 'first-agent'}."
            )
        return entry

    def get_agent_labels(self) -> list[str]:
        labels = []
        for label, _status in self.get_agent_status_by_label().items():
            labels.append(label)
        return labels

    def get_agent_status_by_label(self) -> dict[str, str | None]:
        statuses: dict[str, str | None] = {}
        for agent in self.get_agents():
            label = agent.get("uid") or agent.get("cn") or agent.get("commonName")
            if not label:
                distinguished_name = agent.get("distinguishedName", "")
                head = distinguished_name.split(",", 1)[0]
                if "=" in head:
                    label = head.split("=", 1)[1]
            if not label:
                label = agent.get("hostname") or agent.get("hostName")
            if isinstance(label, str) and label.endswith("-host"):
                label = label[:-5]
            if not label:
                continue
            statuses[str(label)] = agent.get("agentStatus") or agent.get("status")
        return statuses

    def get_active_agent_labels(self) -> list[str]:
        return [
            label
            for label, status in self.get_agent_status_by_label().items()
            if isinstance(status, str) and status.lower() == "active"
        ]

    def execute_task_and_collect_result(
        self,
        agent_dn: str,
        task_name: str,
        params: dict,
        timeout=30,
        entry: dict = None,
    ) -> dict[str, Any]:
        known_history_ids = {
            item.get("id")
            for item in self.api_adapter.get_command_history(agent_dn)
            if item.get("id") is not None
        }
        task_entry = entry or {"distinguishedName": agent_dn, "type": "COMPUTER"}
        response = self.api_adapter.send_task(
            entry=task_entry,
            command_id=task_name,
            params=params,
        )
        payload: dict[str, Any] | None = None
        try:
            candidate = response.json()
            if isinstance(candidate, dict):
                payload = candidate
        except Exception:
            payload = None

        result = {
            "statusCode": response.status_code,
            "responsePayload": payload,
            "messages": payload.get("messages", []) if isinstance(payload, dict) else [],
            "accepted": response.status_code == 200 and (payload or {}).get("status") != "ERROR",
            "historyDetected": False,
        }
        if result["accepted"] is not True:
            return result

        start_time = time.time()
        while time.time() - start_time < timeout:
            history = self.api_adapter.get_command_history(agent_dn)
            for item in history or []:
                history_id = item.get("id")
                command_id = (
                    item.get("commandId")
                    or item.get("task", {}).get("commandId")
                    or item.get("task", {}).get("commandClsId")
                )
                if command_id == task_name and history_id not in known_history_ids:
                    result["historyDetected"] = True
                    result["historyEntry"] = item
                    return result
            time.sleep(2)
        return result

    def execute_and_verify_task(
        self,
        agent_dn: str,
        task_name: str,
        params: dict,
        timeout=30,
        entry: dict = None,
    ) -> bool:
        result = self.execute_task_and_collect_result(
            agent_dn=agent_dn,
            task_name=task_name,
            params=params,
            timeout=timeout,
            entry=entry,
        )
        return result["accepted"] is True and result["historyDetected"] is True
