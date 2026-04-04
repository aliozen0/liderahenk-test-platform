from __future__ import annotations

import os
import logging
import time
import json
from typing import Any, Optional
from urllib.parse import quote

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

    def _post_multipart(
        self,
        path: str,
        *,
        fields: Optional[dict[str, str]] = None,
        params: Optional[dict] = None,
        timeout: int = 15,
    ):
        files = {
            key: (None, "" if value is None else str(value))
            for key, value in (fields or {}).items()
        }
        return self.session.post(f"{self.base_url}{path}", files=files, params=params, timeout=timeout)

    def _get(self, path: str, *, params: Optional[dict] = None, timeout: int = 15):
        return self.session.get(f"{self.base_url}{path}", params=params, timeout=timeout)

    def _options(self, path: str, *, timeout: int = 10):
        return self.session.options(f"{self.base_url}{path}", timeout=timeout)

    def _delete(self, path: str, *, timeout: int = 15):
        return self.session.delete(f"{self.base_url}{path}", timeout=timeout)

    def _coerce_json_response(self, response: requests.Response) -> dict[str, Any]:
        if not response.content:
            return {"statusCode": response.status_code}
        try:
            payload = response.json()
        except ValueError:
            return {
                "statusCode": response.status_code,
                "rawBody": response.text,
            }
        if isinstance(payload, dict):
            return payload
        return {
            "statusCode": response.status_code,
            "payload": payload,
        }

    def get_dashboard_info(self) -> Optional[dict]:
        try:
            response = self._post("/api/dashboard/info", json={})
            if response.status_code == 200:
                return response.json()
            logger.warning("Dashboard info başarısız: HTTP %s", response.status_code)
        except Exception as exc:
            logger.error("Dashboard info hatası: %s", exc)
        return None

    def get_computer_agent_counts(self, search_dn: str = "agents") -> Optional[dict[str, Any]]:
        try:
            response = self._post_form(
                "/api/lider/computer/agent-list-size",
                data={"searchDn": search_dn},
            )
            if response.status_code == 200:
                payload = self._coerce_json_response(response)
                return payload if isinstance(payload, dict) else None
            logger.warning("Computer agent count başarısız: HTTP %s", response.status_code)
        except Exception as exc:
            logger.error("Computer agent count hatası: %s", exc)
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

    def get_user_group_tree(self) -> list[dict]:
        response = self._post("/api/lider/user-groups/groups", json={})
        response.raise_for_status()
        nodes = response.json()
        nodes = nodes if isinstance(nodes, list) else nodes.get("entries", [])
        for node in nodes:
            dn = node.get("distinguishedName")
            if not dn:
                continue
            child_response = self._post_form("/api/lider/user-groups/ou-details", data={"uid": dn})
            child_response.raise_for_status()
            node["childEntries"] = child_response.json() or []
        return nodes

    def get_directory_user_tree(self) -> list[dict]:
        response = self._post("/api/lider/user/users", json={})
        response.raise_for_status()
        nodes = response.json()
        nodes = nodes if isinstance(nodes, list) else nodes.get("entries", [])
        for node in nodes:
            dn = node.get("distinguishedName")
            if not dn:
                continue
            child_response = self._post_form("/api/lider/user/ou-details", data={"uid": dn})
            child_response.raise_for_status()
            node["childEntries"] = child_response.json() or []
        return nodes

    def get_user_tree(self) -> list[dict]:
        return self.get_directory_user_tree()

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

    def _mutation_step_runtime_verified(self, step_name: str, *, mode: str | None = None) -> bool:
        from platform_runtime.readiness.mutation_evidence import load_ui_mutation_evidence

        evidence = load_ui_mutation_evidence() or {}
        verified_steps = evidence.get("verifiedSteps", {}) if isinstance(evidence, dict) else {}
        step_evidence = verified_steps.get(step_name)
        if not isinstance(step_evidence, dict):
            return False
        if step_evidence.get("runtimeVerified") is not True:
            return False
        if mode is not None and step_evidence.get("mode") != mode:
            return False
        return True

    def _write_ui_mutation_verification(
        self,
        *,
        step_name: str,
        mode: str,
        subject_dn: str | None = None,
        group_dn: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        from platform_runtime.readiness.mutation_evidence import (
            load_ui_mutation_evidence,
            write_ui_mutation_evidence,
        )

        payload = load_ui_mutation_evidence() or {}
        verified_steps = dict(payload.get("verifiedSteps") or {})
        step_payload = dict(verified_steps.get(step_name) or {})
        step_payload["runtimeVerified"] = True
        step_payload["mode"] = mode
        if subject_dn is not None:
            step_payload["subjectDn"] = subject_dn
        if group_dn is not None:
            step_payload["groupDn"] = group_dn
        if extra:
            step_payload.update(extra)
        verified_steps[step_name] = step_payload
        payload["verifiedSteps"] = verified_steps
        payload.setdefault("source", "LiderApiAdapter")
        write_ui_mutation_evidence(payload)

    def find_directory_user_entry(self, uid: str) -> dict[str, Any] | None:
        target = str(uid).strip()
        target_suffix = f"uid={target},"
        for node in self._iter_tree_nodes(self.get_directory_user_tree()):
            node_uid = str(node.get("uid") or node.get("name") or node.get("cn") or "").strip()
            distinguished_name = str(node.get("distinguishedName") or node.get("dn") or "").strip()
            if node_uid == target:
                return node
            if distinguished_name == target or distinguished_name.startswith(target_suffix):
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

    def find_user_group_entry(self, group_dn: str) -> dict[str, Any] | None:
        target = str(group_dn).strip()
        for node in self._iter_tree_nodes(self.get_user_group_tree()):
            distinguished_name = str(node.get("distinguishedName") or node.get("dn") or "").strip()
            if distinguished_name == target:
                return node
        return None

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
        entry = self.find_user_group_entry(group_dn)
        return self._group_member_dns(entry) if entry is not None else []

    def wait_for_user_group_membership(
        self,
        group_dn: str,
        member_dns: list[str] | str,
        timeout: int = 30,
    ) -> dict[str, Any]:
        desired_dns = [member_dns] if isinstance(member_dns, str) else [str(item) for item in member_dns]
        started = time.time()
        while time.time() - started < timeout:
            entry = self.find_user_group_entry(group_dn)
            if entry is not None:
                current_dns = set(self._group_member_dns(entry))
                if all(dn in current_dns for dn in desired_dns):
                    return entry
            time.sleep(1)
        raise LookupError(
            f"User-group membership could not be verified within {timeout} seconds: {desired_dns} -> {group_dn}"
        )

    def _configured_endpoint(self, env_name: str) -> str | None:
        endpoint = os.environ.get(env_name, "").strip()
        if not endpoint:
            return None
        return endpoint if endpoint.startswith("/") else f"/{endpoint}"

    def _probe_endpoint_capability(self, endpoint: str, *, timeout: int = 5) -> dict[str, Any]:
        try:
            response = self._options(endpoint, timeout=timeout)
        except requests.RequestException as exc:
            return {
                "probed": True,
                "probeMethod": "OPTIONS",
                "serverReachable": False,
                "routeLikelyPresent": False,
                "error": str(exc),
            }

        status_code = response.status_code
        return {
            "probed": True,
            "probeMethod": "OPTIONS",
            "serverReachable": True,
            "routeLikelyPresent": status_code in {200, 204, 401, 403, 405},
            "statusCode": status_code,
        }

    def _endpoint_capability(
        self,
        *,
        capability: str,
        env_name: str,
        endpoint: str | None,
        probe: bool,
    ) -> dict[str, Any]:
        descriptor: dict[str, Any] = {
            "capability": capability,
            "env": env_name,
            "endpoint": endpoint,
            "configured": endpoint is not None,
            "runtimeVerified": False,
            "enabled": False,
        }
        if endpoint is None:
            descriptor["status"] = "disabled"
            descriptor["reason"] = f"Set {env_name} to enable {capability}."
            return descriptor

        descriptor["status"] = "configured"
        descriptor["reason"] = (
            f"{capability} is configured via {env_name}, but runtime verification is still required."
        )
        if probe:
            descriptor["probe"] = self._probe_endpoint_capability(endpoint)
        return descriptor

    def directory_user_create_endpoint(self) -> str | None:
        return self._configured_endpoint("LIDER_DIRECTORY_USER_CREATE_ENDPOINT")

    def user_group_membership_update_endpoint(self) -> str | None:
        return self._configured_endpoint("LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT")

    def directory_user_create_capability(self, *, probe: bool = False) -> dict[str, Any]:
        descriptor = self._endpoint_capability(
            capability="create_user_via_ui",
            env_name="LIDER_DIRECTORY_USER_CREATE_ENDPOINT",
            endpoint=self.directory_user_create_endpoint(),
            probe=probe,
        )
        if self._mutation_step_runtime_verified("create_user_via_ui", mode="ui-first-postcondition"):
            descriptor["runtimeVerified"] = True
            descriptor["enabled"] = True
            descriptor["status"] = "runtime-verified"
            descriptor["reason"] = "Official directory user create flow is runtime-verified by a postcondition proof."
        return descriptor

    def user_group_membership_update_capability(self, *, probe: bool = False) -> dict[str, Any]:
        descriptor = self._endpoint_capability(
            capability="assign_user_to_group_via_ui",
            env_name="LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT",
            endpoint=self.user_group_membership_update_endpoint(),
            probe=probe,
        )
        if self._mutation_step_runtime_verified("assign_user_to_group_via_ui", mode="existing_group_membership_update"):
            descriptor["runtimeVerified"] = True
            descriptor["enabled"] = True
            descriptor["status"] = "runtime-verified"
            descriptor["reason"] = (
                "Official existing-group membership update flow is runtime-verified by a postcondition proof."
            )
        return descriptor

    def supports_directory_user_create(self) -> bool:
        return bool(self.directory_user_create_capability()["runtimeVerified"])

    def supports_user_group_membership_update(self) -> bool:
        return bool(self.user_group_membership_update_capability()["runtimeVerified"])

    def create_directory_user(
        self,
        *,
        uid: str,
        common_name: str,
        surname: str,
        selected_ou_dn: str,
        password: str = "Secret123!",
        mail: str | None = None,
        privileges: list[str] | None = None,
        extra_attributes: Optional[dict[str, list[str]]] = None,
    ) -> dict[str, Any]:
        endpoint = self.directory_user_create_endpoint()
        if endpoint is None:
            raise NotImplementedError(
                "Official directory user create endpoint is not configured. "
                "Set LIDER_DIRECTORY_USER_CREATE_ENDPOINT to enable create_user_via_ui."
            )

        extra_attributes = dict(extra_attributes or {})
        telephone_number = (
            (extra_attributes.get("telephoneNumber") or ["(555) 123-4567"])[0]
            if isinstance(extra_attributes.get("telephoneNumber"), list)
            else extra_attributes.get("telephoneNumber", "(555) 123-4567")
        )
        postal_address = (
            (extra_attributes.get("homePostalAddress") or ["LiderAhenk UI acceptance flow"])[0]
            if isinstance(extra_attributes.get("homePostalAddress"), list)
            else extra_attributes.get("homePostalAddress", "LiderAhenk UI acceptance flow")
        )

        response = self._post_multipart(
            endpoint,
            fields={
                "parentName": selected_ou_dn,
                "uid": uid,
                "cn": common_name,
                "sn": surname,
                "mail": mail or f"{uid}@liderahenk.org",
                "telephoneNumber": telephone_number,
                "homePostalAddress": postal_address,
                "userPassword": password,
            },
        )
        response.raise_for_status()
        response_data = self._coerce_json_response(response)
        verified_entry = self.wait_for_directory_user(uid)
        verified_dn = str(
            verified_entry.get("distinguishedName")
            or verified_entry.get("dn")
            or response_data.get("distinguishedName")
            or response_data.get("dn")
            or f"uid={uid},{selected_ou_dn}"
        )
        self._write_ui_mutation_verification(
            step_name="create_user_via_ui",
            mode="ui-first-postcondition",
            subject_dn=verified_dn,
            extra={
                "endpoint": endpoint,
                "uid": uid,
            },
        )
        response_data["runtimeVerified"] = True
        response_data["verifiedDn"] = verified_dn
        return response_data

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

    def delete_policy(self, policy_id: int) -> dict[str, Any]:
        response = self._delete(f"/api/policy/delete/id/{policy_id}")
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return self._coerce_json_response(response)

    def delete_profile(self, profile_id: int) -> dict[str, Any]:
        response = self._delete(f"/api/profile/delete/id/{profile_id}")
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return self._coerce_json_response(response)

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

    def delete_computer_group(self, dn: str) -> dict[str, Any]:
        encoded_dn = quote(dn, safe="")
        response = self._delete(f"/api/lider/computer-groups/delete-entry/dn/{encoded_dn}")
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return self._coerce_json_response(response)

    def create_user_group(self, group_name: str, checked_entries: list[dict], selected_ou_dn: str) -> dict:
        response = self._post(
            "/api/lider/user-groups/create-new-group",
            json={
                "groupName": group_name,
                "checkedEntries": json.dumps(checked_entries),
                "selectedOUDN": selected_ou_dn,
            },
        )
        response.raise_for_status()
        return self._coerce_json_response(response)

    def delete_user_group(self, dn: str) -> dict[str, Any]:
        encoded_dn = quote(dn, safe="")
        response = self._delete(f"/api/lider/user-groups/delete-entry/dn/{encoded_dn}")
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()
        return self._coerce_json_response(response)

    def add_directory_entries_to_user_group(self, group_dn: str, checked_entries: list[dict]) -> dict[str, Any]:
        endpoint = self.user_group_membership_update_endpoint()
        if endpoint is None:
            raise NotImplementedError(
                "Official user-group membership update endpoint is not configured. "
                "Set LIDER_USER_GROUP_ADD_MEMBER_ENDPOINT to enable add-user-to-group mutation."
            )

        response = self._post(
            endpoint,
            json={
                "checkedEntries": json.dumps(checked_entries),
                "groupDN": group_dn,
            },
        )
        response.raise_for_status()
        response_data = self._coerce_json_response(response)
        member_dns = [
            str(entry.get("distinguishedName"))
            for entry in checked_entries
            if isinstance(entry, dict) and entry.get("distinguishedName")
        ]
        if member_dns:
            self.wait_for_user_group_membership(group_dn, member_dns)
            self._write_ui_mutation_verification(
                step_name="assign_user_to_group_via_ui",
                mode="existing_group_membership_update",
                subject_dn=member_dns[0],
                group_dn=group_dn,
                extra={
                    "endpoint": endpoint,
                    "memberDns": member_dns,
                },
            )
            response_data["runtimeVerified"] = True
            response_data["verifiedGroupDn"] = group_dn
        return response_data

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
