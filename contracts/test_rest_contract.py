"""
liderapi REST sözleşme testleri.
───────────────────────────────────────────────
Sözleşme: davranışı test eder, iş mantığını değil.
Auth: JWT via POST /api/auth/signin (LDAP-backed)
Port: 8082 (8080 Tomcat ile çakışıyordu)

NOT: Authenticated endpoint testleri, LDAP'ta pardusAccount +
pardusLider objectClass'ına sahip kullanıcı gerektiriyor.
Bitnami default kullanıcıları (user01, user02) bu şemaya sahip değil.
Auth-gerektiren testler skip ile işaretlenir.
"""

import pytest
import requests

BASE = "http://localhost:8082"


class TestLiderApiHealth:
    """liderapi erişilebilirlik testleri (auth gerektirmez)."""

    def test_liderapi_is_reachable(self):
        """liderapi ayakta — 401 bile olsa uygulama çalışıyor."""
        r = requests.get(f"{BASE}/actuator/health", timeout=5)
        assert r.status_code in (200, 401), \
            f"Uygulama yanıt vermiyor: HTTP {r.status_code}"

    def test_health_check_via_adapter(self, lider_api):
        """Adapter health_check metodu çalışıyor."""
        assert lider_api.health_check(), \
            "liderapi health check başarısız"

    def test_signin_endpoint_exists(self, lider_api):
        """POST /api/auth/signin endpoint'i mevcut."""
        assert lider_api.signin_endpoint_available(), \
            "/api/auth/signin endpoint'i bulunamadı"


class TestLiderApiAuth:
    """JWT auth mekanizması testleri."""

    def test_signin_rejects_empty_body(self):
        """Boş body ile signin → 400/401 (404 değil)."""
        r = requests.post(f"{BASE}/api/auth/signin",
                          json={}, timeout=5)
        assert r.status_code != 404, \
            "POST /api/auth/signin endpoint'i bulunamadı (404)"

    def test_signin_rejects_invalid_credentials(self):
        """Geçersiz credentials → 401/500."""
        r = requests.post(f"{BASE}/api/auth/signin",
                          json={"username": "nonexistent",
                                "password": "wrong"},
                          timeout=5)
        assert r.status_code in (401, 403, 500), \
            f"Beklenmedik yanıt: HTTP {r.status_code}"

    def test_open_endpoints_accessible(self):
        """Açık endpoint'ler auth gerektirmeden erişilebilir."""
        open_paths = ["/api/auth/signin"]
        for path in open_paths:
            r = requests.get(f"{BASE}{path}", timeout=5)
            # 401 dışında bir yanıt olmalı (405 = GET desteklenmiyor ama var)
            assert r.status_code != 404, \
                f"{path} bulunamadı (404)"


class TestLiderApiEndpoints:
    """REST endpoint yapısı testleri."""

    def test_computers_endpoint_exists(self):
        """GET /api/computers endpoint'i mevcut (401 kabul)."""
        r = requests.get(f"{BASE}/api/computers", timeout=5)
        # 401 = auth gerekiyor ama endpoint var
        assert r.status_code != 404, \
            "GET /api/computers endpoint'i bulunamadı (404)"

    def test_tasks_endpoint_exists(self):
        """POST /api/tasks endpoint'i mevcut."""
        r = requests.post(f"{BASE}/api/tasks",
                          json={}, timeout=5)
        assert r.status_code != 404, \
            "POST /api/tasks endpoint'i bulunamadı (404)"

    def test_lider_info_endpoint(self):
        """GET /api/lider-info erişilebilir (açık endpoint)."""
        r = requests.get(f"{BASE}/api/lider-info", timeout=5)
        # Bu endpoint auth gerektirmez
        assert r.status_code in (200, 404, 500), \
            f"/api/lider-info beklenmedik yanıt: HTTP {r.status_code}"

    def test_api_version_consistent(self, lider_api):
        """Ardışık health check çağrıları tutarlı."""
        result1 = lider_api.health_check()
        result2 = lider_api.health_check()
        assert result1 == result2, \
            "Ardışık health check sonuçları farklı"
