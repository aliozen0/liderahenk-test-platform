from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from adapters import PlatformAdapterBundle, build_platform_bundle
from platform_runtime.runtime_db import RuntimeDbAdapter


FAILURE_TAXONOMY_PATH = Path("platform/contracts/failure-taxonomy.yaml")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_agent_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "@" in text:
        text = text.split("@", 1)[0]
    if "/" in text:
        text = text.split("/", 1)[0]
    if "," in text and "=" in text:
        head = text.split(",", 1)[0]
        if "=" in head:
            text = head.split("=", 1)[1]
    if text.endswith("-host"):
        text = text[:-5]
    return text


def flatten_tree_agent_ids(nodes: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []

    def walk(entries: list[dict[str, Any]]) -> None:
        for node in entries or []:
            node_type = str(node.get("type") or node.get("nodeType") or "")
            if node_type in {"AHENK", "WINDOWS_AHENK"}:
                label = (
                    node.get("uid")
                    or node.get("cn")
                    or node.get("name")
                    or node.get("distinguishedName")
                )
                normalized = normalize_agent_id(label)
                if normalized:
                    found.append(normalized)
            children = node.get("childEntries", []) or node.get("children", [])
            walk(children)

    walk(nodes or [])
    return sorted(dict.fromkeys(found))


def _identity_from_domain_agent(agent: dict[str, Any]) -> str | None:
    fields = [
        agent.get("jid"),
        agent.get("uid"),
        agent.get("hostname"),
        agent.get("commonName"),
        agent.get("distinguishedName"),
    ]
    for field in fields:
        normalized = normalize_agent_id(field)
        if normalized:
            return normalized
    return None


def _identity_from_c_agent(agent: dict[str, Any]) -> str | None:
    for key in ("jid", "hostname", "agent_id", "client_id", "dn"):
        normalized = normalize_agent_id(agent.get(key))
        if normalized:
            return normalized
    return None


def _first_attr_value(entry: dict[str, Any], key: str) -> Any:
    value = entry.get("attrs", {}).get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _identity_from_ldap_entry(entry: dict[str, Any]) -> str | None:
    for candidate in (
        _first_attr_value(entry, "cn"),
        _first_attr_value(entry, "uid"),
        entry.get("dn"),
    ):
        normalized = normalize_agent_id(candidate)
        if normalized:
            return normalized
    return None


def _hash_payload(payload: Any) -> str:
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(data).hexdigest()


@dataclass
class RegistrationCollector:
    bundle: PlatformAdapterBundle
    runtime_db: RuntimeDbAdapter
    expected_agents: int
    runtime_profile: str

    @classmethod
    def from_env(cls) -> "RegistrationCollector":
        return cls(
            bundle=build_platform_bundle(),
            runtime_db=RuntimeDbAdapter.from_env(),
            expected_agents=int(os.environ.get("AHENK_COUNT", "1")),
            runtime_profile=os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fast"),
        )

    def collect_snapshot(self) -> dict[str, Any]:
        dashboard = self.bundle.inventory.get_dashboard_info() or {}
        agent_list = self.bundle.inventory.get_agent_list()
        computer_tree = self.bundle.inventory.get_computer_tree()
        ldap_entries = self.bundle.directory.search_entries(
            f"ou=Ahenkler,{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
            "(objectClass=device)",
            attributes=["cn", "uid", "host"],
        )
        ldap_ids = sorted(
            dict.fromkeys(
                normalized
                for entry in ldap_entries
                for normalized in [_identity_from_ldap_entry(entry)]
                if normalized
            )
        )
        xmpp_registered = sorted(
            dict.fromkeys(
                agent_id
                for user in self.bundle.presence.list_registered_users()
                for agent_id in [normalize_agent_id(user)]
                if agent_id and agent_id != "lider_sunucu"
            )
        )
        xmpp_connected = sorted(
            dict.fromkeys(
                agent_id
                for user in self.bundle.presence.list_connected_users()
                for agent_id in [normalize_agent_id(user)]
                if agent_id and agent_id != "lider_sunucu"
            )
        )
        c_agent_rows = self.runtime_db.list_c_agents()
        c_agent_ids = sorted(
            dict.fromkeys(
                normalized
                for row in c_agent_rows
                for normalized in [_identity_from_c_agent(row)]
                if normalized
            )
        )
        domain_agent_ids = sorted(
            dict.fromkeys(
                normalized
                for row in agent_list
                for normalized in [_identity_from_domain_agent(row)]
                if normalized
            )
        )
        tree_agent_ids = flatten_tree_agent_ids(computer_tree)
        runtime_config = self.runtime_db.get_config_json()
        return {
            "runtimeProfile": self.runtime_profile,
            "expectedAgents": self.expected_agents,
            "capturedAt": utc_now(),
            "ldapAgentIds": ldap_ids,
            "xmppRegisteredAgentIds": xmpp_registered,
            "xmppConnectedAgentIds": xmpp_connected,
            "cAgentIds": c_agent_ids,
            "domainAgentIds": domain_agent_ids,
            "computerTreeAgentIds": tree_agent_ids,
            "dashboard": {
                "totalComputerNumber": dashboard.get("totalComputerNumber"),
                "totalOnlineComputerNumber": dashboard.get("totalOnlineComputerNumber"),
            },
            "runtimeConfigFingerprint": _hash_payload(runtime_config),
        }

    def evaluate_snapshot(
        self,
        snapshot: dict[str, Any],
        *,
        timed_out: bool = False,
        errors: list[str] | None = None,
    ) -> dict[str, Any]:
        errors = errors or []
        ldap_ids = snapshot["ldapAgentIds"]
        xmpp_registered = snapshot["xmppRegisteredAgentIds"]
        xmpp_connected = snapshot["xmppConnectedAgentIds"]
        c_agent_ids = snapshot["cAgentIds"]
        domain_agent_ids = snapshot["domainAgentIds"]
        tree_ids = snapshot["computerTreeAgentIds"]
        dashboard = snapshot["dashboard"]
        expected = snapshot["expectedAgents"]

        checks = {
            "ldap_matches_expected": len(ldap_ids) == expected,
            "xmpp_registered_matches_expected": len(xmpp_registered) == expected,
            "xmpp_connected_matches_expected": len(xmpp_connected) == expected,
            "c_agent_matches_expected": len(c_agent_ids) == expected,
            "domain_agent_list_matches_expected": len(domain_agent_ids) == expected,
            "computer_tree_matches_expected": len(tree_ids) == expected,
            "dashboard_total_matches_expected": dashboard.get("totalComputerNumber") == expected,
            "dashboard_online_matches_xmpp_connected": dashboard.get("totalOnlineComputerNumber") == len(xmpp_connected),
            "ldap_matches_xmpp_registered": ldap_ids == xmpp_registered,
            "ldap_matches_c_agent": ldap_ids == c_agent_ids,
            "c_agent_matches_domain_agent_list": c_agent_ids == domain_agent_ids,
            "c_agent_matches_computer_tree": c_agent_ids == tree_ids,
        }

        taxonomy: list[dict[str, Any]] = []
        if errors:
            taxonomy.append(
                {
                    "code": "adapter_error",
                    "severity": FAILURE_TAXONOMY["adapter_error"]["severity"],
                    "details": errors,
                }
            )

        failed_checks = [name for name, passed in checks.items() if not passed]
        if timed_out and failed_checks:
            taxonomy.append(
                {
                    "code": "registration_timeout",
                    "severity": FAILURE_TAXONOMY["registration_timeout"]["severity"],
                    "details": failed_checks,
                }
            )
        elif failed_checks:
            taxonomy.append(
                {
                    "code": "registration_projection_mismatch",
                    "severity": FAILURE_TAXONOMY["registration_projection_mismatch"]["severity"],
                    "details": failed_checks,
                }
            )

        status = "pass" if not taxonomy and all(checks.values()) else "fail"
        per_agent = self._build_per_agent_state(
            ldap_ids=ldap_ids,
            xmpp_registered=xmpp_registered,
            xmpp_connected=xmpp_connected,
            c_agent_ids=c_agent_ids,
            domain_agent_ids=domain_agent_ids,
            tree_ids=tree_ids,
        )
        return {
            "status": status,
            "checks": checks,
            "taxonomy": taxonomy,
            "failedChecks": failed_checks,
            "surfaces": {
                "ldapAgentCount": len(ldap_ids),
                "xmppRegisteredCount": len(xmpp_registered),
                "xmppConnectedCount": len(xmpp_connected),
                "cAgentCount": len(c_agent_ids),
                "domainAgentCount": len(domain_agent_ids),
                "computerTreeAgentCount": len(tree_ids),
                "dashboardTotalComputerNumber": dashboard.get("totalComputerNumber"),
                "dashboardTotalOnlineComputerNumber": dashboard.get("totalOnlineComputerNumber"),
            },
            "perAgent": per_agent,
            "capturedAt": snapshot["capturedAt"],
        }

    def _build_per_agent_state(
        self,
        *,
        ldap_ids: list[str],
        xmpp_registered: list[str],
        xmpp_connected: list[str],
        c_agent_ids: list[str],
        domain_agent_ids: list[str],
        tree_ids: list[str],
    ) -> list[dict[str, Any]]:
        all_ids = sorted(
            dict.fromkeys(
                ldap_ids + xmpp_registered + xmpp_connected + c_agent_ids + domain_agent_ids + tree_ids
            )
        )
        states: list[dict[str, Any]] = []
        for agent_id in all_ids:
            state_flags = {
                "ldap_entry_ready": agent_id in ldap_ids,
                "xmpp_identity_ready": agent_id in xmpp_registered,
                "register_sent": agent_id in xmpp_connected,
                "register_accepted": agent_id in domain_agent_ids,
                "c_agent_ready": agent_id in c_agent_ids,
                "domain_ready": (
                    agent_id in ldap_ids
                    and agent_id in xmpp_registered
                    and agent_id in xmpp_connected
                    and agent_id in c_agent_ids
                    and agent_id in domain_agent_ids
                    and agent_id in tree_ids
                ),
            }
            reached = [name for name, present in state_flags.items() if present]
            states.append(
                {
                    "agentId": agent_id,
                    "states": state_flags,
                    "highestState": reached[-1] if reached else "missing",
                    "observability": {
                        "register_sent": "inferred_from_xmpp_connected",
                        "register_accepted": "inferred_from_domain_inventory",
                    },
                }
            )
        return states


with FAILURE_TAXONOMY_PATH.open("r", encoding="utf-8") as _taxonomy_file:
    FAILURE_TAXONOMY = yaml.safe_load(_taxonomy_file)["classes"]


def build_run_manifest(
    *,
    expected_agents: int,
    runtime_profile: str,
    timeout_seconds: int,
    min_backoff_seconds: int,
    max_backoff_seconds: int,
    run_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "runId": run_id or str(uuid.uuid4()),
        "runtimeProfile": runtime_profile,
        "expectedAgents": expected_agents,
        "startedAt": utc_now(),
        "timeoutSeconds": timeout_seconds,
        "backoff": {
            "minSeconds": min_backoff_seconds,
            "maxSeconds": max_backoff_seconds,
        },
    }


def build_failure_summary(run_manifest: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "runId": run_manifest["runId"],
        "status": verdict["status"],
        "capturedAt": verdict["capturedAt"],
        "failedChecks": verdict["failedChecks"],
        "taxonomy": verdict["taxonomy"],
    }


def append_event(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
