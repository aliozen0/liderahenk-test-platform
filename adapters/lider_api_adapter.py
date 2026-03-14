from __future__ import annotations

import logging
import time
import json
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class LiderApiAdapter:
    AUTH_ENDPOINT = "/api/auth/signin"
    REFRESH_ENDPOINT = "/api/auth/refresh-token"

    COMMAND_ENDPOINTS = {
        "EXECUTE_SCRIPT": "/api/lider/task/execute/script",
        "GET_FILE_CONTENT": "/api/lider/task/execute/file-management",
        "WRITE_TO_FILE": "/api/lider/task/execute/file-management",
        "RESOURCE_INFO_FETCHER": "/api/lider/task/execute/resource-usage",
        "AGENT_INFO": "/api/lider/task/execute/resource-usage",
        "REPOSITORIES": "/api/lider/task/execute/repositories",
        "PACKAGE_SOURCES": "/api/lider/task/execute/repositories",
        "PACKAGES": "/api/lider/task/execute/package-install-remove",
        "INSTALLED_PACKAGES": "/api/lider/task/execute/installed-packages",
        "PACKAGE_MANAGEMENT": "/api/lider/task/execute/installed-packages",
        "CHECK_PACKAGE": "/api/lider/task/execute/check-package",
        "GET_USERS": "/api/lider/task/execute/local-user",
        "ADD_USER": "/api/lider/task/execute/local-user",
        "EDIT_USER": "/api/lider/task/execute/local-user",
        "DELETE_USER": "/api/lider/task/execute/local-user",
        "GET_NETWORK_INFORMATION": "/api/lider/task/execute/network-management",
        "ADD_DNS": "/api/lider/task/execute/network-management",
        "DELETE_DNS": "/api/lider/task/execute/network-management",
        "ADD_DOMAIN": "/api/lider/task/execute/network-management",
        "DELETE_DOMAIN": "/api/lider/task/execute/network-management",
        "ADD_HOST": "/api/lider/task/execute/network-management",
        "DELETE_HOST": "/api/lider/task/execute/network-management",
        "ADD_NETWORK": "/api/lider/task/execute/network-management",
        "DELETE_NETWORK": "/api/lider/task/execute/network-management",
        "CHANGE_HOSTNAME": "/api/lider/task/execute/network-management",
        "ALLOW_PORT": "/api/lider/task/execute/network-management",
        "BLOCK_PORT": "/api/lider/task/execute/network-management",
    }

    def __init__(self, base_url: str, version: str = None, username: str = None, password: str = None):
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.session = requests.Session()
        self._token = None
        self._refresh_token = None
        self._authenticated = False

        if username and password:
            self._authenticate(username, password)

    def _authenticate(self, username: str, password: str) -> bool:
        try:
            response = requests.post(
                f"{self.base_url}{self.AUTH_ENDPOINT}",
                json={"username": username, "password": password},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                self._token = data.get("token")
                self._refresh_token = data.get("refreshToken")
                self.session.headers.update({"Authorization": f"Bearer {self._token}"})
                self._authenticated = True
                logger.info("JWT auth başarılı: %s", username)
                return True
            logger.warning("JWT auth başarısız: HTTP %s — %s", response.status_code, response.text[:200])
            return False
        except requests.RequestException as exc:
            logger.error("Auth bağlantı hatası: %s", exc)
            return False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    def refresh_token(self) -> bool:
        if not self._refresh_token:
            return False
        try:
            response = requests.post(
                f"{self.base_url}{self.REFRESH_ENDPOINT}",
                json={"refreshToken": self._refresh_token},
                timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                self._token = data.get("token")
                self.session.headers.update({"Authorization": f"Bearer {self._token}"})
                return True
        except requests.RequestException:
            pass
        return False

    def _post(self, path: str, json: Optional[dict] = None, *, params: Optional[dict] = None, timeout: int = 15):
        return self.session.post(f"{self.base_url}{path}", json=json or {}, params=params, timeout=timeout)

    def _post_form(self, path: str, data: Optional[dict] = None, *, params: Optional[dict] = None, timeout: int = 15):
        return self.session.post(f"{self.base_url}{path}", data=data or {}, params=params, timeout=timeout)

    def _get(self, path: str, *, params: Optional[dict] = None, timeout: int = 15):
        return self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)

    def _delete(self, path: str, *, timeout: int = 15):
        return self.session.delete(f"{self.base_url}{path}", timeout=timeout)

    def get_dashboard_info(self) -> Optional[dict]:
        try:
            response = self._post("/api/dashboard/info", json={})
            if response.status_code == 200:
                return response.json()
            logger.warning("Dashboard info başarısız: HTTP %s", response.status_code)
        except Exception as exc:
            logger.error("Dashboard info hatası: %s", exc)
        return None

    def get_agent_list(self, page: int = 1, size: int = 100) -> list[dict]:
        try:
            response = self._post(
                "/api/lider/agent-info/list",
                json={
                    "pageNumber": page,
                    "pageSize": size,
                    "agentStatus": "ALL",
                    "status": "",
                    "dn": "",
                    "hostname": "",
                    "macAddress": "",
                    "ipAddress": "",
                    "brand": "",
                    "model": "",
                    "processor": "",
                    "osVersion": "",
                    "agentVersion": "",
                    "diskType": "",
                    "selectedOUDN": "",
                    "groupName": "",
                    "groupDN": "",
                    "sessionReportType": "",
                },
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data.get("content"), list):
                    return data["content"]
                if isinstance(data.get("agents"), dict):
                    return data["agents"].get("content", [])
        except Exception as exc:
            logger.error("Agent list hatası: %s", exc)
        return []

    def get_agent_count(self) -> int:
        return len(self.get_agent_list())

    def get_computer_tree(self) -> list[dict]:
        response = self._post("/api/lider/computer/computers", json={})
        response.raise_for_status()
        nodes = response.json()
        nodes = nodes if isinstance(nodes, list) else nodes.get("entries", [])
        for node in nodes:
            dn = node.get("distinguishedName")
            if not dn:
                continue
            child_response = self._post_form("/api/lider/computer/ou-details", data={"uid": dn})
            child_response.raise_for_status()
            node["childEntries"] = child_response.json() or []
        return nodes

    def get_computer_group_tree(self) -> list[dict]:
        response = self._post("/api/lider/computer-groups/groups", json={})
        response.raise_for_status()
        nodes = response.json()
        nodes = nodes if isinstance(nodes, list) else nodes.get("entries", [])
        for node in nodes:
            dn = node.get("distinguishedName")
            if not dn:
                continue
            child_response = self._post_form("/api/lider/computer-groups/ou-details", data={"uid": dn})
            child_response.raise_for_status()
            node["childEntries"] = child_response.json() or []
        return nodes

    def get_plugin_tasks(self) -> list[dict]:
        response = self._post("/api/get-plugin-task-list", json={})
        response.raise_for_status()
        return response.json()

    def get_plugin_task(self, command_id: str) -> dict:
        for task in self.get_plugin_tasks():
            if task.get("commandId") == command_id:
                return task
        raise KeyError(f"plugin task not found: {command_id}")

    def get_plugin_profiles(self) -> list[dict]:
        response = self._post("/api/get-plugin-profile-list", json={})
        response.raise_for_status()
        return response.json()

    def get_profiles(self, plugin_name: str) -> list[dict]:
        response = self._post("/api/profile/list", params={"name": plugin_name}, json={})
        response.raise_for_status()
        return response.json()

    def create_script_profile(self, label: str, description: str, script_contents: str, script_type: int = 0, script_params: str = "") -> dict:
        plugin_profile = next(
            profile for profile in self.get_plugin_profiles()
            if profile.get("page") == "execute-script-profile"
        )
        response = self._post(
            "/api/profile/add",
            json={
                "label": label,
                "description": description,
                "profileData": {
                    "SCRIPT_TYPE": script_type,
                    "SCRIPT_CONTENTS": script_contents,
                    "SCRIPT_PARAMS": script_params,
                },
                "plugin": plugin_profile["plugin"],
            },
        )
        response.raise_for_status()
        return response.json()

    def create_policy(self, label: str, description: str, profiles: list[dict], active: bool = False) -> dict:
        response = self._post(
            "/api/policy/add",
            json={
                "label": label,
                "description": description,
                "active": active,
                "profiles": profiles,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_active_policies(self) -> list[dict]:
        response = self._get("/api/policy/active-policies")
        response.raise_for_status()
        return response.json()

    def execute_policy(self, policy_id: int, dn: str, dn_type: str = "GROUP") -> requests.Response:
        return self._post(
            "/api/policy/execute",
            json={
                "id": policy_id,
                "dnType": dn_type,
                "dnList": [dn],
            },
        )

    def create_computer_group(self, group_name: str, checked_entries: list[dict], selected_ou_dn: str) -> dict:
        response = self._post(
            "/api/lider/computer-groups/create-new-agent-group",
            json={
                "groupName": group_name,
                "checkedEntries": json.dumps(checked_entries),
                "selectedOUDN": selected_ou_dn,
            },
        )
        response.raise_for_status()
        return response.json()

    def send_task(
        self,
        entry: dict,
        command_id: str,
        params: dict,
        *,
        task_parts: bool = False,
        cron_expression: Optional[str] = None,
    ) -> requests.Response:
        endpoint = self.COMMAND_ENDPOINTS.get(command_id)
        if endpoint is None:
            raise KeyError(f"unsupported command id: {command_id}")

        task = dict(self.get_plugin_task(command_id))
        task["commandId"] = command_id
        task["parameterMap"] = params
        task["dnList"] = [entry["distinguishedName"]]
        task["entryList"] = [entry]
        task["dnType"] = entry["type"]
        task["taskParts"] = task_parts
        task["cronExpression"] = cron_expression
        return self._post(endpoint, json=task)

    def get_command_history(self, dn: str) -> list[dict]:
        response = self._get(f"/api/command/dn/{dn}")
        response.raise_for_status()
        return response.json()

    def get_command_result(self, result_id: int) -> dict:
        response = self._get(f"/api/command/command-execution-result/id/{result_id}")
        response.raise_for_status()
        return response.json()

    def wait_for_agents(self, min_count: int, timeout: int = 120) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            try:
                if self.get_agent_count() >= min_count:
                    return True
            except Exception:
                pass
            time.sleep(5)
        return False

    def get_server_info(self) -> dict:
        response = requests.get(f"{self.base_url}/api/lider-info", timeout=5)
        response.raise_for_status()
        return response.json()

    def health_check(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/actuator/health", timeout=5)
            return response.status_code in (200, 401)
        except Exception:
            return False

    def signin_endpoint_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}{self.AUTH_ENDPOINT}", timeout=5)
            return response.status_code in (200, 401, 405)
        except Exception:
            return False
