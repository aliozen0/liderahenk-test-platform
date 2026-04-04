"""Policy roundtrip execution, group reconciliation, and failure diagnosis."""
from __future__ import annotations

import os
import uuid
from typing import Any

import requests

from adapters.lider_api_adapter import LiderApiAdapter

from .checks import build_check
from .service_logs import tail_service_logs, search_service_logs


def find_group_entry(nodes: list[dict[str, Any]], *, group_name: str) -> dict[str, Any] | None:
    for node in nodes or []:
        node_name = str(node.get("cn") or node.get("name") or "")
        if node_name == group_name:
            return node
        child = find_group_entry(
            node.get("childEntries", []) or node.get("children", []),
            group_name=group_name,
        )
        if child:
            return child
    return None


def create_computer_group_with_reconciliation(
    api: LiderApiAdapter,
    *,
    group_name: str,
    checked_entries: list[dict[str, Any]],
    selected_ou_dn: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    try:
        return (
            api.create_computer_group(
                group_name=group_name,
                checked_entries=checked_entries,
                selected_ou_dn=selected_ou_dn,
            ),
            None,
        )
    except requests.HTTPError as exc:
        response = exc.response
        status_code = getattr(response, "status_code", None)
        if status_code != 417:
            raise
        group_tree = api.get_computer_group_tree()
        reconciled_group = find_group_entry(group_tree, group_name=group_name)
        if reconciled_group is None:
            raise
        return (
            reconciled_group,
            {
                "mode": "group_tree_reconciliation",
                "httpStatus": status_code,
                "groupName": group_name,
                "responseText": (response.text or "")[:500] if response is not None else "",
            },
        )


def policy_roundtrip_failure_details(exc: Exception, *, stage: str) -> dict[str, Any]:
    details: dict[str, Any] = {
        "stage": stage,
        "error": str(exc),
    }
    if not isinstance(exc, requests.HTTPError):
        return details

    response = exc.response
    details["httpStatus"] = getattr(response, "status_code", None)
    details["responseText"] = ((response.text or "")[:500] if response is not None else "")
    log_tail = tail_service_logs("liderapi", tail=160)
    details["liderapiLogTailAvailable"] = log_tail["available"]
    if log_tail["available"] is not True and log_tail.get("error"):
        details["liderapiLogError"] = log_tail["error"]

    lines = [line for line in log_tail.get("tail", "").splitlines() if line.strip()]
    search_window = search_service_logs("liderapi", since="20m")
    details["liderapiLogSearchAvailable"] = search_window["available"]
    if search_window["available"] is not True and search_window.get("error"):
        details["liderapiLogSearchError"] = search_window["error"]

    searched_lines = [line for line in search_window.get("logs", "").splitlines() if line.strip()]
    matched_lines: list[str] = []
    for source_lines in (searched_lines, lines):
        for original in source_lines:
            lowered = original.lower()
            if "computergroupscontroller.createnewagentgroup" in lowered or "no write access to parent" in lowered:
                matched_lines.append(original.strip())
        if matched_lines:
            break

    if matched_lines:
        details["diagnosis"] = {
            "classification": "ldap_parent_write_denied",
            "likelyCause": (
                "Lider API computer-group creation appears to run with an authenticated bind "
                "that cannot write to the parent OU, which matches the authenticated-user "
                "LDAP bind mode failure seen in ComputerGroupsController.createNewAgentGroup."
            ),
            "evidenceLines": matched_lines[-6:],
        }
    else:
        details["liderapiLogTail"] = lines[-20:]
    return details


def cleanup_roundtrip_artifacts(
    api: LiderApiAdapter,
    *,
    policy: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    group_dn: str | None = None,
    delete_group_method: str,
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
    if group_dn:
        operations.append(("group", group_dn, delete_group_method, {"dn": group_dn}))

    for resource, identifier, method_name, kwargs in operations:
        attempts.append(
            {
                "resource": resource,
                "identifier": identifier,
                "method": method_name,
            }
        )
        try:
            method = getattr(api, method_name)
            method(**kwargs)
        except Exception:  # pragma: no cover - exercised through callers
            failures.append(
                {
                    "resource": resource,
                    "identifier": identifier,
                    "method": method_name,
                    "error": "cleanup_failed",
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


def run_policy_roundtrip_check() -> dict[str, Any]:
    api = LiderApiAdapter(
        base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
        username=os.environ.get("LIDER_USER", "lider-admin"),
        password=os.environ.get("LIDER_PASS", "secret"),
    )

    def find_first_agent(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
        for node in nodes or []:
            if node.get("type") in {"AHENK", "WINDOWS_AHENK"}:
                return node
            child = find_first_agent(node.get("childEntries", []) or node.get("children", []))
            if child:
                return child
        return None

    stage = "get_computer_tree"
    group: dict[str, Any] | None = None
    profile: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None
    try:
        tree = api.get_computer_tree()
        entry = find_first_agent(tree)
        if not entry:
            return build_check(
                check_id="policy_roundtrip",
                category="operational",
                description="Policy roundtrip can target at least one agent group",
                passed=False,
                details="No computer tree root entry available",
            )

        token = uuid.uuid4().hex[:8]
        group_name = f"rt-group-{token}"
        profile_label = f"rt-profile-{token}"
        policy_label = f"rt-policy-{token}"
        selected_ou_dn = os.environ.get(
            "LDAP_AGENT_GROUPS_OU",
            f"ou=AgentGroups,{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
        )
        stage = "create_computer_group"
        group, reconciliation = create_computer_group_with_reconciliation(
            api,
            group_name=group_name,
            checked_entries=[entry],
            selected_ou_dn=selected_ou_dn,
        )
        stage = "create_script_profile"
        profile = api.create_script_profile(
            label=profile_label,
            description="Runtime readiness policy roundtrip",
            script_contents="#!/bin/bash\nprintf 'runtime-policy-roundtrip\\n'",
        )
        stage = "create_policy"
        policy = api.create_policy(
            label=policy_label,
            description="Runtime readiness policy",
            profiles=[profile],
            active=False,
        )
        stage = "execute_policy"
        response = api.execute_policy(policy["id"], group["distinguishedName"], "GROUP")
        cleanup = cleanup_roundtrip_artifacts(
            api,
            policy=policy,
            profile=profile,
            group_dn=group.get("distinguishedName"),
            delete_group_method="delete_computer_group",
        )
        details = {
            "groupDn": group.get("distinguishedName"),
            "profileLabel": profile.get("label"),
            "policyLabel": policy.get("label"),
            "cleanup": cleanup,
        }
        if reconciliation is not None:
            details["groupCreateReconciliation"] = reconciliation
        return build_check(
            check_id="policy_roundtrip",
            category="operational",
            description="Policy roundtrip can create group/profile/policy and execute it",
            passed=response.status_code == 200 and cleanup["status"] == "completed",
            actual=response.status_code,
            expected=200,
            details=details,
        )
    except Exception as exc:
        cleanup = cleanup_roundtrip_artifacts(
            api,
            policy=policy,
            profile=profile,
            group_dn=group.get("distinguishedName") if isinstance(group, dict) else None,
            delete_group_method="delete_computer_group",
        )
        failure_details = policy_roundtrip_failure_details(exc, stage=stage)
        if cleanup["status"] != "not_required":
            failure_details["cleanup"] = cleanup
        return build_check(
            check_id="policy_roundtrip",
            category="operational",
            description="Policy roundtrip can create group/profile/policy and execute it",
            passed=False,
            actual=type(exc).__name__,
            expected="successful operational roundtrip",
            details=failure_details,
        )
