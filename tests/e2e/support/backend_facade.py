from __future__ import annotations

import time

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from tests.e2e.config.play_config import PlayConfig


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

    def wait_for_agent_registration(self, min_count: int = 1, timeout: int = 60) -> bool:
        return self.api_adapter.wait_for_agents(min_count, timeout)

    def is_agent_connected_xmpp(self) -> bool:
        try:
            return self.xmpp_adapter.get_connected_count() > 0
        except Exception:
            return False

    def get_registered_agent_count(self) -> int:
        return self.api_adapter.get_agent_count()

    def wait_for_platform_readiness(self, min_count: int = 1, timeout: int = 120) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.wait_for_agent_registration(min_count=min_count, timeout=5) and self.is_agent_connected_xmpp():
                return True
            time.sleep(3)
        return False

    def get_agents(self) -> list[dict]:
        return self.api_adapter.get_agent_list()

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
            if label:
                labels.append(str(label))
        return labels

    def execute_and_verify_task(
        self,
        agent_dn: str,
        task_name: str,
        params: dict,
        timeout=30,
        entry: dict = None,
    ) -> bool:
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
        if response.status_code != 200:
            return False

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
                    return True
            time.sleep(2)

        return False
