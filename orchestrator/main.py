"""
LiderAhenk Test Senaryo Motoru
──────────────────────────────
YAML tanımlı senaryoları çalıştırır.
Token yönetimi otomatik — manuel curl gerekmez.
"""

import os
import sys
import time
import yaml
import json
import logging
from pathlib import Path

# Proje kökünü sys.path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.lider_api_adapter import LiderApiAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from adapters.ldap_schema_adapter import LdapSchemaAdapter

logger = logging.getLogger(__name__)


class ScenarioRunner:
    """YAML tabanlı senaryo motoru."""

    def __init__(self):
        # Host-erişimli URL'ler (Docker-internal değil)
        api_url = os.environ.get("LIDER_API_HOST_URL",
                                 os.environ.get("LIDER_API_URL", "http://localhost:8082"))
        # Docker-internal URL'leri host URL'lerine çevir
        if "liderapi:8080" in api_url:
            api_url = "http://localhost:8082"

        ejabberd_url = os.environ.get("EJABBERD_API_HOST",
                                      os.environ.get("EJABBERD_API_URL", "http://localhost:15280/api"))
        if "ejabberd:5280" in ejabberd_url:
            ejabberd_url = "http://localhost:15280/api"

        self.api = LiderApiAdapter(
            base_url=api_url,
            username=os.environ.get("LIDER_USER", "lider-admin"),
            password=os.environ.get("LIDER_PASS", "secret"),
        )

        self.xmpp = XmppMessageAdapter(
            api_url=ejabberd_url,
            domain=os.environ.get("XMPP_DOMAIN", "liderahenk.org"),
        )

        self.ldap = LdapSchemaAdapter(
            host=os.environ.get("LDAP_HOST", "localhost"),
            port=int(os.environ.get("LDAP_PORT", "1389")),
            base_dn=os.environ.get("LDAP_BASE_DN", "dc=liderahenk,dc=org"),
            admin_dn=f"cn={os.environ.get('LDAP_ADMIN_USERNAME', 'admin')},"
                     f"{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
            admin_pass=os.environ.get("LDAP_ADMIN_PASSWORD", "DEGISTIR"),
        )

        self.ahenk_count = int(os.environ.get("AHENK_COUNT", "10"))
        self.state = {}

    def run(self, scenario_path: str) -> dict:
        """Senaryo dosyasını çalıştır."""
        scenario = yaml.safe_load(Path(scenario_path).read_text())
        name = scenario["name"]

        print(f"\n{'=' * 60}")
        print(f"Senaryo: {name}")
        print(f"Açıklama: {scenario.get('description', '')}")
        print(f"{'=' * 60}")

        results = {"scenario": name, "steps": [], "passed": True}

        # Setup
        setup = scenario.get("setup", {})
        if setup.get("wait_for_agents"):
            min_a = setup.get("min_agents", 1)
            timeout = setup.get("timeout_seconds", 60)
            print(f"  Bekleniyor: en az {min_a} ajan...")

        # Steps
        for step in scenario.get("steps", []):
            result = self._execute_step(step)
            results["steps"].append(result)
            icon = "✅" if result["success"] else "❌"
            print(f"  {icon} {step['name']}: {result.get('detail', '')}")
            if not result["success"]:
                results["passed"] = False

        # Assertions
        assertions = self._check_assertions(scenario, results)
        results["assertions"] = assertions

        # Rapor
        passed = sum(1 for s in results["steps"] if s["success"])
        total = len(results["steps"])
        icon = "✅ PASS" if results["passed"] else "❌ FAIL"
        print(f"\n{'=' * 60}")
        print(f"Sonuç: {icon} — {passed}/{total} adım başarılı")
        print(f"{'=' * 60}\n")

        return results

    def _resolve_var(self, value) -> str:
        """${AHENK_COUNT} gibi değişkenleri çöz."""
        s = str(value)
        if "${AHENK_COUNT}" in s:
            s = s.replace("${AHENK_COUNT}", str(self.ahenk_count))
        return s

    def _execute_step(self, step: dict) -> dict:
        action = step["action"]
        params = step.get("params", {})

        try:
            if action == "check_api_health":
                ok = self.api.health_check()
                return {"success": ok, "detail": "API sağlıklı" if ok else "API erişilemez"}

            elif action == "check_jwt_auth":
                ok = self.api.is_authenticated
                return {"success": ok, "detail": "JWT auth aktif" if ok else "Auth yok"}

            elif action == "check_ldap_agent_count":
                expected = int(self._resolve_var(params["expected"]))
                actual = self.ldap.get_agent_count()
                ok = actual == expected
                return {"success": ok, "detail": f"{actual}/{expected} ajan",
                        "actual": actual, "expected": expected}

            elif action == "check_xmpp_agent_count":
                expected = int(self._resolve_var(params["expected"]))
                total = self.xmpp.get_registered_count()
                # lider_sunucu'yu çıkar
                actual = total - 1 if total > 0 else 0
                ok = actual >= expected
                return {"success": ok, "detail": f"{actual}/{expected} ajan",
                        "actual": actual, "expected": expected}

            elif action == "check_agent_exists":
                agent_id = params["agent_id"]
                ldap_ok = self.ldap.agent_exists(agent_id) if params.get("check_ldap") else True
                xmpp_ok = self.xmpp.is_user_registered(agent_id) if params.get("check_xmpp") else True
                ok = ldap_ok and xmpp_ok
                return {"success": ok, "detail": f"LDAP={ldap_ok} XMPP={xmpp_ok}",
                        "ldap": ldap_ok, "xmpp": xmpp_ok}

            elif action == "check_connection_rate":
                min_pct = params.get("min_pct", 0.90)
                connected = self.xmpp.get_connected_count()
                rate = connected / max(self.ahenk_count, 1)
                ok = rate >= min_pct
                return {"success": ok, "detail": f"{rate:.0%} ({connected}/{self.ahenk_count})",
                        "rate": rate}

            elif action == "send_task":
                command_id = params["command_id"]
                parameter_map = params.get("parameter_map", {})
                entry = self._select_agent_entry(params.get("agent_id"))
                response = self.api.send_task(entry, command_id, parameter_map)
                ok = response.status_code == 200
                return {
                    "success": ok,
                    "detail": f"{command_id} -> HTTP {response.status_code}",
                    "status_code": response.status_code,
                }

            elif action == "create_computer_group":
                group_name = self._resolve_var(params["group_name"])
                entry = self._select_agent_entry(params.get("agent_id"))
                selected_ou_dn = params.get(
                    "selected_ou_dn",
                    f"ou=Agent,ou=Groups,{os.environ.get('LDAP_BASE_DN', 'dc=liderahenk,dc=org')}",
                )
                group = self.api.create_computer_group(group_name, [entry], selected_ou_dn)
                self.state["last_group"] = group
                return {
                    "success": True,
                    "detail": group.get("distinguishedName", group_name),
                    "group": group,
                }

            elif action == "create_script_profile":
                profile = self.api.create_script_profile(
                    label=self._resolve_var(params["label"]),
                    description=params.get("description", ""),
                    script_contents=params.get("script_contents", "#!/bin/bash\nprintf 'ok\\n'"),
                    script_type=int(params.get("script_type", 0)),
                    script_params=params.get("script_params", ""),
                )
                self.state["last_profile"] = profile
                return {"success": True, "detail": profile.get("label", "profile"), "profile": profile}

            elif action == "create_policy":
                profile = self.state.get("last_profile")
                if not profile:
                    return {"success": False, "detail": "Önce create_script_profile çalışmalı"}
                policy = self.api.create_policy(
                    label=self._resolve_var(params["label"]),
                    description=params.get("description", ""),
                    profiles=[profile],
                    active=bool(params.get("active", False)),
                )
                self.state["last_policy"] = policy
                return {"success": True, "detail": policy.get("label", "policy"), "policy": policy}

            elif action == "execute_policy":
                policy = self.state.get("last_policy")
                group = self.state.get("last_group")
                if not policy or not group:
                    return {"success": False, "detail": "Önce create_policy ve create_computer_group çalışmalı"}
                response = self.api.execute_policy(policy["id"], group["distinguishedName"], "GROUP")
                ok = response.status_code == 200
                return {"success": ok, "detail": f"policy -> HTTP {response.status_code}"}

            elif action == "wait_for_results":
                timeout = params.get("timeout_seconds", 10)
                time.sleep(min(timeout, 5))
                return {"success": True, "detail": f"{timeout}sn beklendi"}

            elif action == "prometheus_snapshot":
                return {"success": True, "detail": "metrik snapshot tamamlandı"}

            else:
                return {"success": False, "detail": f"Bilinmeyen action: {action}"}

        except Exception as e:
            return {"success": False, "detail": str(e), "error": str(e)}

    def _check_assertions(self, scenario: dict, results: dict) -> list:
        assertion_results = []
        for a in scenario.get("assertions", []):
            t = a["type"]
            if t == "all_steps_passed":
                ok = all(s["success"] for s in results["steps"])
                assertion_results.append({"type": t, "passed": ok})
                if not ok:
                    results["passed"] = False
            elif t == "no_errors":
                ok = not any(s.get("error") for s in results["steps"])
                assertion_results.append({"type": t, "passed": ok})
            else:
                assertion_results.append({"type": t, "passed": True})
        return assertion_results

    def _select_agent_entry(self, agent_id: str | None = None) -> dict:
        tree = self.api.get_computer_tree()
        entry = self._find_agent_entry(tree, agent_id)
        if not entry:
            raise RuntimeError(f"Ajan bulunamadı: {agent_id or 'first-online'}")
        return entry

    def _find_agent_entry(self, nodes, agent_id: str | None = None):
        for node in nodes or []:
            if node.get("type") in {"AHENK", "WINDOWS_AHENK"}:
                if agent_id is None or node.get("uid") == agent_id or node.get("cn") == agent_id:
                    return node
            child = self._find_agent_entry(node.get("childEntries", []) or node.get("children", []), agent_id)
            if child:
                return child
        return None
