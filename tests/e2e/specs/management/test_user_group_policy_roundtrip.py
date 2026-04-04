from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from platform_runtime.readiness.mutation_evidence import write_ui_mutation_evidence
from tests.e2e.pages.dashboard_page import DashboardPage
from tests.e2e.pages.policy_management_page import PolicyManagementPage
from tests.e2e.pages.user_management_page import UserManagementPage


pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_user_group_policy_roundtrip_is_executed_from_authenticated_ui(
    authenticated_page,
    ready_backend,
):
    dashboard_page = DashboardPage(authenticated_page)
    assert dashboard_page.is_dashboard_visible(), (
        "Authenticated UI session did not land on a visible dashboard surface."
    )

    user_uid = f"ui-rt-{uuid.uuid4().hex[:8]}"
    user_mail = f"{user_uid}@liderahenk.org"
    user_password = "Secret1A"

    user_page = UserManagementPage(authenticated_page)
    user_page.load()
    assert user_page.is_user_management_visible(), (
        "User management surface did not become visible."
    )
    user_page.open_user_create_dialog_from_root()
    user_page.assert_user_create_dialog_visible()
    create_response = user_page.create_user_via_dialog(
        uid=user_uid,
        common_name="Ui",
        surname="Roundtrip",
        mail=user_mail,
        password=user_password,
    )
    assert create_response["statusCode"] == 200, (
        f"UI user creation request failed for {user_uid}: {create_response!r}"
    )

    user_entry = ready_backend.wait_for_directory_user(user_uid, timeout=30)
    user_dn = str(user_entry.get("distinguishedName") or user_entry.get("dn"))
    assert user_dn, f"Created directory user did not expose a distinguished name: {user_entry!r}"

    user_page.open_group_management()
    assert user_page.is_group_management_visible(), (
        "LDAP user group management surface did not become visible."
    )
    user_page.expand_tree_item_by_key("ou=groups,dc=liderahenk,dc=org")
    group_label = "readers"
    group_dn = f"cn={group_label},ou=groups,dc=liderahenk,dc=org"
    before_members = set(ready_backend.get_user_group_member_dns(group_dn))

    membership_response = user_page.add_existing_user_to_group_by_key(
        group_key=group_dn,
        user_uid=user_uid,
    )
    assert membership_response["statusCode"] == 200, (
        f"UI existing-group membership request failed for {user_uid}: {membership_response!r}"
    )

    updated_group = ready_backend.wait_for_user_group_membership(group_dn, user_dn, timeout=30)
    updated_members = set(ready_backend.get_user_group_member_dns(group_dn))
    assert user_dn in updated_members, (
        f"Backend evidence did not confirm membership for {user_dn} in {group_dn}: {updated_group!r}"
    )
    assert len(updated_members) >= len(before_members), "Group membership count regressed after UI update."

    policy_page = PolicyManagementPage(authenticated_page)
    policy_page.load()
    assert policy_page.is_policy_management_visible(), (
        "Policy management surface did not become visible."
    )
    policy_page.assert_tabs_visible()
    policy_page.open_add_policy_dialog()
    policy_page.assert_policy_dialog_visible()
    policy_page.close_policy_dialog()
    policy_page.assert_profile_list_visible()

    profile = ready_backend.api_adapter.create_script_profile(
        label=f"{user_uid}-profile",
        description="UI-first acceptance script profile",
        script_contents="#!/bin/bash\nprintf 'ui-user-policy-roundtrip\\n'",
    )
    policy = ready_backend.api_adapter.create_policy(
        label=f"{user_uid}-policy",
        description="UI-first acceptance policy",
        profiles=[profile],
        active=False,
    )
    execution_response = ready_backend.api_adapter.execute_policy(
        policy_id=int(policy.get("id") or policy.get("policyId")),
        dn=group_dn,
    )
    cleanup = ready_backend.policy.cleanup_roundtrip_artifacts(
        policy=policy,
        profile=profile,
    )
    assert execution_response.status_code == 200, (
        f"Policy execution failed for UI-mutated group {group_dn}: HTTP {execution_response.status_code}"
    )
    assert cleanup["status"] == "completed", (
        f"Policy/profile cleanup failed after UI-first roundtrip: {cleanup!r}"
    )

    write_ui_mutation_evidence(
        {
            "scenario": "ui-user-policy-roundtrip",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "verifiedSteps": {
                "create_user_via_ui": {
                    "runtimeVerified": True,
                    "uid": user_uid,
                    "userDn": user_dn,
                    "request": create_response,
                },
                "assign_user_to_group_via_ui": {
                    "runtimeVerified": True,
                    "mode": "existing_group_membership_update",
                    "groupDn": group_dn,
                    "userDn": user_dn,
                    "request": membership_response,
                },
            },
        }
    )

    dashboard_page.load()
    assert dashboard_page.is_dashboard_visible(), (
        "Dashboard surface was not stable after the UI-first mutation roundtrip."
    )
