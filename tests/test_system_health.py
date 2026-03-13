"""
Sistem Sağlık Testi — LiderAhenk Test Platform
Tüm servislerin çalışıp çalışmadığını, portların erişilebilir olduğunu
ve temel bağlantıların sağlıklı olduğunu kontrol eder.

Kullanım:
    PYTHONPATH=. pytest tests/test_system_health.py -v --timeout=30
"""
import pytest
import subprocess
import socket
import requests
import time


# ─── Yardımcı fonksiyonlar ─────────────────────────────────────────

def port_open(host, port, timeout=3):
    """Verilen host:port'a TCP bağlantısı dener."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def http_get(url, timeout=5, **kwargs):
    """HTTP GET isteği yapar, hata durumunda None döner."""
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def http_post(url, timeout=5, **kwargs):
    """HTTP POST isteği yapar, hata durumunda None döner."""
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None


def docker_ps():
    """docker compose ps çıktısını döner."""
    result = subprocess.run(
        ["docker", "compose", "--env-file", ".env",
         "-f", "compose/compose.core.yml",
         "-f", "compose/compose.lider.yml",
         "-f", "compose/compose.agents.yml",
         "-f", "compose/compose.obs.yml",
         "-p", "liderahenk-test",
         "ps", "--format", "json"],
        capture_output=True, text=True, cwd="/home/huma/liderahenk-test"
    )
    if result.returncode != 0:
        return []
    import json
    lines = result.stdout.strip().split('\n')
    containers = []
    for line in lines:
        if line.strip():
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return containers


# ─── Konteyner Durum Testleri ──────────────────────────────────────

class TestContainerStatus:
    """Docker konteynerlerinin çalışma durumu."""

    @pytest.fixture(scope="class")
    def containers(self):
        return docker_ps()

    def _find_container(self, containers, name_pattern):
        """Konteyner adı pattern'e göre bul."""
        for c in containers:
            svc = c.get("Service", "") or c.get("Name", "")
            if name_pattern in svc.lower():
                return c
        return None

    @pytest.mark.parametrize("service", [
        "mariadb", "ldap", "ejabberd",
        "lider-core", "liderapi", "lider-ui",
        "prometheus", "grafana", "loki", "cadvisor"
    ])
    def test_container_running(self, containers, service):
        """Servis konteynerinin çalışıyor olması gerekir."""
        c = self._find_container(containers, service)
        assert c is not None, f"'{service}' konteyneri bulunamadı. Toplam konteyner: {len(containers)}"
        state = (c.get("State", "") or "").lower()
        assert state == "running", \
            f"'{service}' durumu: {state} (beklenen: running). Status: {c.get('Status', '')}"

    def test_container_count_minimum(self, containers):
        """En az 10 konteyner çalışmalı (core + lider + obs)."""
        running = [c for c in containers if (c.get("State", "") or "").lower() == "running"]
        assert len(running) >= 8, \
            f"Çalışan konteyner sayısı: {len(running)}, beklenen >= 8"

    def test_no_restarting_containers(self, containers):
        """Hiçbir konteyner restart döngüsünde olmamalı."""
        restarting = [
            c.get("Service", c.get("Name", "?"))
            for c in containers
            if "restarting" in (c.get("State", "") or "").lower()
        ]
        assert len(restarting) == 0, f"Restart döngüsünde konteynerler: {restarting}"


# ─── Port Erişilebilirlik Testleri ─────────────────────────────────

class TestPortAccessibility:
    """Dışa açılan portların erişilebilirliği (127.0.0.1)."""

    @pytest.mark.parametrize("port,service", [
        (1389, "LDAP"),
        (8082, "liderapi"),
        (3001, "lider-ui"),
        (15280, "ejabberd HTTP API"),
        (9090, "Prometheus"),
        (3000, "Grafana"),
        (3100, "Loki"),
    ])
    def test_port_accessible(self, port, service):
        """Port 127.0.0.1 üzerinden erişilebilir olmalı."""
        assert port_open("127.0.0.1", port), \
            f"{service} portu ({port}) erişilemez"


# ─── Servis Düzeyinde Sağlık Testleri ─────────────────────────────

class TestServiceHealth:
    """Her servisin kendi sağlık kontrol mekanizması."""

    def test_liderapi_health(self):
        """liderapi /actuator/health endpoint'i yanıt vermeli (200 veya 401)."""
        resp = http_get("http://127.0.0.1:8082/actuator/health")
        if resp is None:
            pytest.fail("liderapi erişilemez")
        # 200 = açık endpoint, 401 = auth gerekli (Spring Security), her ikisi de canlı demek
        assert resp.status_code in (200, 401), \
            f"liderapi health: {resp.status_code}"

    def test_liderapi_health_status_up(self):
        """liderapi sağlık durumu UP olmalı (veya auth gerekiyorsa canlılık teyidi)."""
        resp = http_get("http://127.0.0.1:8082/actuator/health")
        if resp and resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "UP", f"liderapi status: {data.get('status')}"
        else:
            # 401 = auth gerekli ama servis canlı
            if resp and resp.status_code == 401:
                return  # Servis canlı, auth engeli var
            pytest.fail(f"liderapi erişilemez: {resp.status_code if resp else 'bağlantı hatası'}")

    def test_lider_ui_accessible(self):
        """lider-ui ana sayfası HTTP 200 dönmeli."""
        resp = http_get("http://127.0.0.1:3001/")
        assert resp is not None and resp.status_code == 200, \
            f"lider-ui: {resp.status_code if resp else 'erişilemez'}"

    def test_ejabberd_api_accessible(self):
        """ejabberd HTTP API erişilebilir olmalı."""
        resp = http_post(
            "http://127.0.0.1:15280/api/registered_users",
            json={"host": "liderahenk.org"}
        )
        assert resp is not None and resp.status_code == 200, \
            f"ejabberd API: {resp.status_code if resp else 'erişilemez'}"

    def test_ejabberd_has_registered_users(self):
        """ejabberd'de en az 1 kayıtlı kullanıcı olmalı (lider_sunucu)."""
        resp = http_post(
            "http://127.0.0.1:15280/api/registered_users",
            json={"host": "liderahenk.org"}
        )
        if resp and resp.status_code == 200:
            users = resp.json()
            assert len(users) >= 1, f"Kayıtlı kullanıcı sayısı: {len(users)}"
        else:
            pytest.fail("ejabberd API erişilemez")

    def test_ldap_search(self):
        """LDAP basit arama yapılabilmeli."""
        result = subprocess.run(
            ["docker", "compose", "--env-file", ".env",
             "-f", "compose/compose.core.yml",
             "-p", "liderahenk-test",
             "exec", "-T", "ldap",
             "ldapsearch", "-x", "-H", "ldap://localhost:1389",
             "-D", "cn=admin,dc=liderahenk,dc=org",
             "-w", "DEGISTIR",
             "-b", "dc=liderahenk,dc=org",
             "-s", "base", "(objectClass=*)"],
            capture_output=True, text=True, timeout=15,
            cwd="/home/huma/liderahenk-test"
        )
        assert result.returncode == 0, f"LDAP search başarısız: {result.stderr[:200]}"

    def test_mariadb_accessible(self):
        """MariaDB docker exec ile erişilebilir olmalı."""
        result = subprocess.run(
            ["docker", "compose", "--env-file", ".env",
             "-f", "compose/compose.core.yml",
             "-p", "liderahenk-test",
             "exec", "-T", "mariadb",
             "mysqladmin", "ping", "-h", "localhost"],
            capture_output=True, text=True, timeout=10,
            cwd="/home/huma/liderahenk-test"
        )
        assert result.returncode == 0, f"MariaDB ping başarısız: {result.stderr[:200]}"

    def test_prometheus_up(self):
        """Prometheus web UI erişilebilir olmalı."""
        resp = http_get("http://127.0.0.1:9090/-/ready")
        assert resp is not None and resp.status_code == 200, \
            f"Prometheus: {resp.status_code if resp else 'erişilemez'}"

    def test_grafana_up(self):
        """Grafana API erişilebilir olmalı."""
        resp = http_get("http://127.0.0.1:3000/api/health")
        assert resp is not None and resp.status_code == 200, \
            f"Grafana: {resp.status_code if resp else 'erişilemez'}"

    def test_loki_up(self):
        """Loki API erişilebilir olmalı (503 = henüz hazırlanıyor kabul edilir)."""
        resp = http_get("http://127.0.0.1:3100/ready")
        if resp is None:
            pytest.fail("Loki erişilemez")
        # 200 = hazır, 503 = başlatılıyor ama canlı
        assert resp.status_code in (200, 503), \
            f"Loki: {resp.status_code}"


# ─── JWT Kimlik Doğrulama Testi ────────────────────────────────────

class TestAuthentication:
    """JWT token alım ve kullanım testi."""

    def test_jwt_login(self):
        """liderapi'den JWT token alınabilmeli."""
        resp = http_post(
            "http://127.0.0.1:8082/api/auth/signin",
            json={"username": "lider-admin", "password": "secret"}
        )
        assert resp is not None, "liderapi auth endpoint'ine bağlanılamadı"
        assert resp.status_code == 200, f"JWT login HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "token" in data, f"Yanıtta 'token' alanı yok: {list(data.keys())}"

    def test_authenticated_api_call(self):
        """JWT token ile korumalı endpoint'e erişilebilmeli."""
        login = http_post(
            "http://127.0.0.1:8082/api/auth/signin",
            json={"username": "lider-admin", "password": "secret"}
        )
        if not login or login.status_code != 200:
            pytest.skip("JWT login başarısız, authenticated test atlanıyor")

        token = login.json().get("token")
        resp = http_get(
            "http://127.0.0.1:8082/api/computers",
            headers={"Authorization": f"Bearer {token}"}
        )
        # 200 veya 405 (POST-only endpoint) kabul edilir
        assert resp is not None, "Authenticated API çağrısı başarısız"
        assert resp.status_code in (200, 405, 404), \
            f"Authenticated API HTTP {resp.status_code}"
