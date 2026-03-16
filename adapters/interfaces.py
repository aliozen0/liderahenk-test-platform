from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class DirectoryUser:
    dn: str
    uid: str
    cn: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectoryGroup:
    dn: str
    cn: str
    member_dns: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentNode:
    dn: str
    uid: str
    cn: str
    hostname: str | None = None
    node_type: str | None = None
    online: bool | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentGroup:
    dn: str
    cn: str
    member_dns: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


class DirectoryAdapter(Protocol):
    def connection_healthy(self) -> bool: ...
    def get_tree_dns(self) -> list[str]: ...
    def search_entries(self, base_dn: str, ldap_filter: str, attributes: list[str] | None = None, scope: int | None = None) -> list[dict]: ...
    def get_agent_count(self) -> int: ...
    def list_agents(self) -> list[str]: ...


class AgentInventoryAdapter(Protocol):
    def get_dashboard_info(self) -> dict | None: ...
    def get_agent_list(self, page: int = 1, size: int = 100) -> list[dict]: ...
    def get_computer_tree(self) -> list[dict]: ...
    def get_computer_group_tree(self) -> list[dict]: ...


class TaskDispatchAdapter(Protocol):
    def send_task(self, entry: dict, command_id: str, params: dict, *, task_parts: bool = False, cron_expression: str | None = None): ...
    def get_plugin_tasks(self) -> list[dict]: ...


class PolicyDispatchAdapter(Protocol):
    def create_script_profile(self, label: str, description: str, script_contents: str, script_type: int = 0, script_params: str = "") -> dict: ...
    def create_policy(self, label: str, description: str, profiles: list[dict], active: bool = False) -> dict: ...
    def execute_policy(self, policy_id: int, dn: str, dn_type: str = "GROUP"): ...


class PresenceAdapter(Protocol):
    def api_healthy(self) -> bool: ...
    def get_registered_count(self) -> int: ...
    def get_connected_count(self) -> int: ...
    def is_user_registered(self, username: str) -> bool: ...
    def list_registered_users(self) -> list[str]: ...
    def list_connected_users(self) -> list[str]: ...
