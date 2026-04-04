import requests

BASE = "http://localhost:8082"


class TestLiderApiHealth:
    def test_liderapi_is_reachable(self):
        response = requests.get(f"{BASE}/actuator/health", timeout=5)
        assert response.status_code in (200, 401), f"Uygulama yanıt vermiyor: HTTP {response.status_code}"

    def test_health_check_via_adapter(self, lider_api):
        assert lider_api.health_check(), "liderapi health check başarısız"

    def test_signin_endpoint_exists(self, lider_api):
        assert lider_api.signin_endpoint_available(), "/api/auth/signin endpoint'i bulunamadı"


class TestLiderApiAuth:
    def test_signin_rejects_empty_body(self):
        response = requests.post(f"{BASE}/api/auth/signin", json={}, timeout=5)
        assert response.status_code != 404, "POST /api/auth/signin endpoint'i bulunamadı (404)"

    def test_signin_rejects_invalid_credentials(self):
        response = requests.post(
            f"{BASE}/api/auth/signin",
            json={"username": "nonexistent", "password": "wrong"},
            timeout=5,
        )
        assert response.status_code in (401, 403, 500), f"Beklenmedik yanıt: HTTP {response.status_code}"


class TestLiderApiV1Surface:
    def test_dashboard_info_available(self, lider_api):
        payload = lider_api.get_dashboard_info()
        assert isinstance(payload, dict), "Dashboard payload alınamadı"
        assert "totalComputerNumber" in payload, "Dashboard contract eksik: totalComputerNumber"

    def test_agent_info_list_available(self, lider_api):
        agents = lider_api.get_agent_list()
        assert isinstance(agents, list), "Agent info list payload list değil"

    def test_plugin_task_catalog_filtered(self, lider_api):
        tasks = lider_api.get_plugin_tasks()
        command_ids = {task.get("commandId") for task in tasks}
        assert "EXECUTE_SCRIPT" in command_ids, "EXECUTE_SCRIPT görünmüyor"
        assert "GET_FILE_CONTENT" in command_ids, "GET_FILE_CONTENT görünmüyor"
        assert "MANAGE_USB" not in command_ids, "V1 dışı USB görevi katalogda görünmemeli"
        assert "SETUP-VNC-SERVER" not in command_ids, "V1 dışı remote-access görevi katalogda görünmemeli"

    def test_plugin_profile_catalog_filtered(self, lider_api):
        profiles = lider_api.get_plugin_profiles()
        pages = {profile.get("page") for profile in profiles}
        assert "execute-script-profile" in pages, "Script profile görünmüyor"
        assert "usb-profile" not in pages, "USB profile V1'de görünmemeli"
        assert "browser-profile" not in pages, "Browser profile V1'de görünmemeli"

    def test_execute_script_endpoint_exists(self):
        response = requests.post(f"{BASE}/api/lider/task/execute/script", json={}, timeout=5)
        assert response.status_code != 404, "Script execute endpoint bulunamadı"

    def test_policy_endpoints_exist(self, lider_api):
        active = lider_api.get_active_policies()
        assert isinstance(active, list), "Active policy list payload list değil"
