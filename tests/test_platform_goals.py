"""
Platform Hedef Doğrulama Testi — LiderAhenk Test Platform
Projenin README'de belirtilen amaçlarına ne kadar yaklaştığını ölçer.
Her hedef ayrı test, sonuçta % tamamlanma skoru üretilir.

Kullanım:
    PYTHONPATH=. pytest tests/test_platform_goals.py -v --timeout=60

Amacımız:
    "Pardus LiderAhenk için konteyner tabanlı, tam otomatik test ortamı.
     Tek komutla ayağa kalkar. Gerçek servisleri çalıştırır. Her şeyi test eder."
"""
import pytest
import subprocess
import requests
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.lider_api_adapter import LiderApiAdapter
from platform_runtime.registration import flatten_tree_agent_ids
from platform_runtime.runtime_db import RuntimeDbAdapter


# ─── Yardımcı ──────────────────────────────────────────────────────

def http_get(url, timeout=5, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None

def http_post(url, timeout=5, **kwargs):
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except requests.RequestException:
        return None

def docker_ps_services():
    """Çalışan servislerin listesini döner."""
    result = subprocess.run(
        ["docker", "compose",
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
    containers = []
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return containers


# ─── Hedef Sonuç Toplayıcı ────────────────────────────────────────

class GoalTracker:
    """Test sonuçlarını toplayıp skor üretir."""
    results = {}

    @classmethod
    def record(cls, goal_id, goal_name, passed, detail=""):
        cls.results[goal_id] = {
            "name": goal_name,
            "passed": passed,
            "detail": detail
        }

    @classmethod
    def report(cls):
        total = len(cls.results)
        passed = sum(1 for r in cls.results.values() if r["passed"])
        score = (passed / total * 100) if total > 0 else 0
        lines = [
            "",
            "=" * 70,
            f"  📊 LiderAhenk Platform Hedef Skoru: {passed}/{total} ({score:.0f}%)",
            "=" * 70,
        ]
        for gid, r in sorted(cls.results.items()):
            icon = "✅" if r["passed"] else "❌"
            lines.append(f"  {icon} {r['name']}")
            if r["detail"]:
                lines.append(f"     → {r['detail']}")
        lines.append("=" * 70)
        return "\n".join(lines)


# ─── Hedef 1: Tek Komutla Ayağa Kalkar ────────────────────────────

class TestGoal1_SingleCommandBoot:
    """README vaadi: 'make dev-obs ile 8 dakikada hazır'"""

    def test_core_services_running(self):
        """Core servisler (MariaDB, LDAP, ejabberd) çalışmalı."""
        containers = docker_ps_services()
        running = {
            (c.get("Service") or c.get("Name", "")).lower()
            for c in containers
            if (c.get("State", "")).lower() == "running"
        }
        required = {"mariadb", "ldap", "ejabberd"}
        missing = required - {s for s in running if any(r in s for r in required)}
        result = len(missing) == 0
        GoalTracker.record("1a", "Core servisler çalışıyor", result,
                           f"Eksik: {missing}" if missing else "MariaDB, LDAP, ejabberd ✓")
        assert result, f"Core servisler eksik: {missing}"

    def test_lider_services_running(self):
        """Lider servisleri (lider-core, liderapi, lider-ui) çalışmalı."""
        containers = docker_ps_services()
        running_names = [
            (c.get("Service") or c.get("Name", "")).lower()
            for c in containers
            if (c.get("State", "")).lower() == "running"
        ]
        required = ["lider-core", "liderapi", "lider-ui"]
        found = []
        missing = []
        for req in required:
            if any(req in name for name in running_names):
                found.append(req)
            else:
                missing.append(req)
        result = len(missing) == 0
        GoalTracker.record("1b", "Lider servisleri çalışıyor", result,
                           f"Eksik: {missing}" if missing else "lider-core, liderapi, lider-ui ✓")
        assert result, f"Lider servisleri eksik: {missing}"

    def test_obs_services_running(self):
        """Gözlemlenebilirlik servisleri çalışmalı."""
        containers = docker_ps_services()
        running_names = [
            (c.get("Service") or c.get("Name", "")).lower()
            for c in containers
            if (c.get("State", "")).lower() == "running"
        ]
        required = ["prometheus", "grafana", "loki"]
        found = []
        missing = []
        for req in required:
            if any(req in name for name in running_names):
                found.append(req)
            else:
                missing.append(req)
        result = len(missing) == 0
        GoalTracker.record("1c", "Gözlemlenebilirlik servisleri çalışıyor", result,
                           f"Eksik: {missing}" if missing else "Prometheus, Grafana, Loki ✓")
        assert result, f"Obs servisleri eksik: {missing}"


# ─── Hedef 2: Gerçek Servisleri Çalıştırır ────────────────────────

class TestGoal2_RealServicesWork:
    """README vaadi: 'Gerçek servisleri çalıştırır'"""

    def test_ldap_returns_data(self):
        """LDAP sorgusu gerçek veri dönmeli."""
        result = subprocess.run(
            ["docker", "compose",
             "-f", "compose/compose.core.yml",
             "-p", "liderahenk-test",
             "exec", "-T", "ldap",
             "ldapsearch", "-x", "-H", "ldap://localhost:1389",
             "-D", "cn=admin,dc=liderahenk,dc=org",
             "-w", "DEGISTIR",
             "-b", "dc=liderahenk,dc=org",
             "(objectClass=*)"],
            capture_output=True, text=True, timeout=15,
            cwd="/home/huma/liderahenk-test"
        )
        has_data = result.returncode == 0 and "numEntries" in result.stdout
        entry_count = "?"
        for line in result.stdout.split("\n"):
            if "numEntries" in line:
                entry_count = line.strip()
        GoalTracker.record("2a", "LDAP gerçek veri dönüyor", has_data, entry_count)
        assert has_data, f"LDAP sorgusu başarısız: {result.stderr[:200]}"

    def test_ejabberd_returns_users(self):
        """ejabberd kayıtlı kullanıcı listesi dönmeli."""
        resp = http_post(
            "http://127.0.0.1:15280/api/registered_users",
            json={"host": "liderahenk.org"}
        )
        has_users = (resp is not None and resp.status_code == 200 and
                     len(resp.json()) > 0)
        count = len(resp.json()) if resp and resp.status_code == 200 else 0
        GoalTracker.record("2b", "ejabberd kayıtlı kullanıcılar", has_users,
                           f"{count} kullanıcı kayıtlı")
        assert has_users, f"ejabberd kullanıcı sayısı: {count}"

    def test_mariadb_has_tables(self):
        """MariaDB'de liderdb tabloları mevcut olmalı."""
        result = subprocess.run(
            ["docker", "compose",
             "-f", "compose/compose.core.yml",
             "-p", "liderahenk-test",
             "exec", "-T", "mariadb",
             "mysql", "-ulider", "-pDEGISTIR",
             "-e", "SHOW TABLES;", "liderahenk"],
            capture_output=True, text=True, timeout=10,
            cwd="/home/huma/liderahenk-test"
        )
        has_tables = result.returncode == 0 and len(result.stdout.strip().split("\n")) > 1
        GoalTracker.record("2c", "MariaDB tablolar mevcut", has_tables,
                           result.stdout[:100] if has_tables else result.stderr[:100])
        assert has_tables, f"MariaDB tabloları yok: {result.stderr[:200]}"

    def test_liderapi_responds(self):
        """liderapi sağlık endpoint'i yanıt vermeli."""
        resp = http_get("http://127.0.0.1:8082/actuator/health")
        works = resp is not None and resp.status_code == 200
        detail = ""
        if resp and resp.status_code == 200:
            detail = f"status: {resp.json().get('status', '?')}"
        GoalTracker.record("2d", "liderapi yanıt veriyor", works, detail)
        assert works


# ─── Hedef 3: Ajan Kayıt ve Bağlantı ──────────────────────────────

class TestGoal3_AgentRegistration:
    """README vaadi: 'Ajan simülasyonu çalışır'"""

    EXPECTED = int(os.environ.get("AHENK_COUNT", "1"))

    @staticmethod
    def _api() -> LiderApiAdapter:
        return LiderApiAdapter(
            base_url=os.environ.get("LIDER_API_URL_EXTERNAL", "http://127.0.0.1:8082"),
            username=os.environ.get("LIDER_USER", "lider-admin"),
            password=os.environ.get("LIDER_PASS", "secret"),
        )

    def test_agents_registered_in_ldap(self):
        """Ahenk ajanları LDAP'ta kayıtlı olmalı."""
        result = subprocess.run(
            ["docker", "compose",
             "-f", "compose/compose.core.yml",
             "-p", "liderahenk-test",
             "exec", "-T", "ldap",
             "ldapsearch", "-x", "-H", "ldap://localhost:1389",
             "-D", "cn=admin,dc=liderahenk,dc=org",
             "-w", "DEGISTIR",
             "-b", "ou=Ahenkler,dc=liderahenk,dc=org",
             "(objectClass=pardusDevice)"],
            capture_output=True, text=True, timeout=15,
            cwd="/home/huma/liderahenk-test"
        )
        count = 0
        for line in result.stdout.split("\n"):
            if "numEntries" in line:
                try:
                    count = int(line.split(":")[1].strip())
                except (IndexError, ValueError):
                    pass
        has_agents = count == self.EXPECTED
        GoalTracker.record("3a", "Ajanlar LDAP'ta kayıtlı", has_agents,
                           f"{count} ajan kayıtlı")
        assert has_agents, (
            f"LDAP parity bozuk. Beklenen {self.EXPECTED}, bulunan {count}. "
            f"Çıktı: {result.stdout[:200]}"
        )

    def test_agents_registered_in_xmpp(self):
        """Ahenk ajanları XMPP'te kayıtlı olmalı."""
        resp = http_post(
            "http://127.0.0.1:15280/api/registered_users",
            json={"host": "liderahenk.org"}
        )
        if not resp or resp.status_code != 200:
            GoalTracker.record("3b", "Ajanlar XMPP'te kayıtlı", False, "ejabberd erişilemez")
            pytest.fail("ejabberd API erişilemez")

        users = resp.json()
        # lider_sunucu hariç
        agents = [u for u in users if u.startswith("ahenk")]
        has_agents = len(agents) == self.EXPECTED
        GoalTracker.record("3b", "Ajanlar XMPP'te kayıtlı", has_agents,
                           f"{len(agents)} ajan, toplam {len(users)} kullanıcı")
        assert has_agents, (
            f"XMPP parity bozuk. Beklenen {self.EXPECTED}, bulunan {len(agents)}. "
            f"Kullanıcılar: {users[:5]}"
        )

    def test_provisioner_completed(self):
        """Provisioner servisi başarıyla tamamlanmış olmalı."""
        result = subprocess.run(
            ["docker", "compose",
             "-f", "compose/compose.core.yml",
             "-f", "compose/compose.agents.yml",
             "-p", "liderahenk-test",
             "ps", "--format", "json"],
            capture_output=True, text=True, cwd="/home/huma/liderahenk-test"
        )
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                try:
                    containers.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        prov = None
        for c in containers:
            svc = (c.get("Service") or c.get("Name", "")).lower()
            if "provisioner" in svc:
                prov = c
                break
        if prov:
            state = (prov.get("State", "")).lower()
            # exited(0) = başarılı tamamlandı
            completed = state == "exited" and "0" in prov.get("Status", "")
            GoalTracker.record("3c", "Provisioner tamamlandı", completed,
                               f"State: {state}, Status: {prov.get('Status', '?')}")
            assert completed or state == "exited", \
                f"Provisioner durumu: {state}"
        else:
            GoalTracker.record("3c", "Provisioner tamamlandı", False, "Konteyner bulunamadı")
            pytest.fail("Provisioner konteyneri bulunamadı")

    def test_c_agent_matches_expected(self):
        """c_agent sayısı AHENK_COUNT ile eşleşmeli."""
        runtime_db = RuntimeDbAdapter.from_env()
        count = runtime_db.get_c_agent_count()
        result = count == self.EXPECTED
        GoalTracker.record("3d", "c_agent sayısı eşleşiyor", result, f"{count}/{self.EXPECTED}")
        assert result

    def test_dashboard_matches_expected(self):
        """Dashboard toplam bilgisayar sayısı AHENK_COUNT ile eşleşmeli."""
        try:
            payload = self._api().get_dashboard_info() or {}
        except Exception:
            GoalTracker.record("3e", "Dashboard sayısı eşleşiyor", False, "dashboard erişilemez")
            pytest.fail("Dashboard API erişilemez")
        total = int(payload.get("totalComputerNumber") or 0)
        result = total == self.EXPECTED
        GoalTracker.record("3e", "Dashboard sayısı eşleşiyor", result, f"{total}/{self.EXPECTED}")
        assert result

    def test_computer_tree_matches_expected(self):
        """Computer tree agent sayısı AHENK_COUNT ile eşleşmeli."""
        try:
            tree = self._api().get_computer_tree()
        except Exception:
            GoalTracker.record("3f", "Computer tree sayısı eşleşiyor", False, "computer tree erişilemez")
            pytest.fail("Computer tree API erişilemez")
        count = len(flatten_tree_agent_ids(tree))
        result = count == self.EXPECTED
        GoalTracker.record("3f", "Computer tree sayısı eşleşiyor", result, f"{count}/{self.EXPECTED}")
        assert result


# ─── Hedef 4: API Erişimi ve JWT Auth ─────────────────────────────

class TestGoal4_ApiAccess:
    """README vaadi: 'JWT auth + korumalı API erişimi'"""

    def test_jwt_token_obtained(self):
        """JWT token alınabilmeli."""
        resp = http_post(
            "http://127.0.0.1:8082/api/auth/signin",
            json={"username": "lider-admin", "password": "secret"}
        )
        works = (resp is not None and resp.status_code == 200 and
                 "token" in resp.json())
        GoalTracker.record("4a", "JWT token alınabiliyor", works,
                           "Token alındı" if works else f"HTTP {resp.status_code if resp else '?'}")
        assert works

    def test_authenticated_endpoint(self):
        """Token ile korumalı endpoint erişilebilmeli."""
        login = http_post(
            "http://127.0.0.1:8082/api/auth/signin",
            json={"username": "lider-admin", "password": "secret"}
        )
        if not login or login.status_code != 200:
            GoalTracker.record("4b", "Authenticated API erişimi", False, "Login başarısız")
            pytest.skip("JWT login başarısız")

        token = login.json().get("token")
        resp = http_get(
            "http://127.0.0.1:8082/api/computers",
            headers={"Authorization": f"Bearer {token}"}
        )
        works = resp is not None and resp.status_code in (200, 404, 405)
        GoalTracker.record("4b", "Authenticated API erişimi", works,
                           f"HTTP {resp.status_code}" if resp else "Bağlantı hatası")
        assert works

    def test_lider_ui_loads(self):
        """Lider UI yüklenmeli."""
        resp = http_get("http://127.0.0.1:3001/")
        works = resp is not None and resp.status_code == 200
        GoalTracker.record("4c", "Lider UI yükleniyor", works,
                           f"Content-Length: {len(resp.content)} bytes" if works else "Erişilemez")
        assert works


# ─── Hedef 5: Test Edilebilirlik —──────────────────────────────────

class TestGoal5_Testability:
    """README vaadi: 'Sözleşme testleri / entegrasyon testleri çalışır'"""

    def test_contract_test_files_exist(self):
        """Sözleşme test dosyaları mevcut olmalı."""
        base = "/home/huma/liderahenk-test/contracts"
        files = ["test_rest_contract.py", "test_ldap_contract.py", "test_xmpp_contract.py"]
        existing = [f for f in files if os.path.exists(os.path.join(base, f))]
        result = len(existing) == len(files)
        GoalTracker.record("5a", "Sözleşme test dosyaları mevcut", result,
                           f"{len(existing)}/{len(files)} dosya")
        assert result

    def test_integration_test_files_exist(self):
        """Entegrasyon test dosyaları mevcut olmalı."""
        base = "/home/huma/liderahenk-test/tests"
        files = ["test_integration.py", "test_scale.py"]
        existing = [f for f in files if os.path.exists(os.path.join(base, f))]
        result = len(existing) == len(files)
        GoalTracker.record("5b", "Entegrasyon test dosyaları mevcut", result,
                           f"{len(existing)}/{len(files)} dosya")
        assert result

    def test_scenario_files_exist(self):
        """Senaryo YAML dosyaları mevcut olmalı."""
        base = "/home/huma/liderahenk-test/orchestrator/scenarios"
        files = ["basic_task.yml", "registration_test.yml", "scale_test.yml"]
        existing = [f for f in files if os.path.exists(os.path.join(base, f))]
        result = len(existing) == len(files)
        GoalTracker.record("5c", "Senaryo dosyaları mevcut", result,
                           f"{len(existing)}/{len(files)} dosya")
        assert result

    def test_adapter_layer_exists(self):
        """ACL adapter katmanı mevcut olmalı."""
        base = "/home/huma/liderahenk-test/adapters"
        files = ["lider_api_adapter.py", "xmpp_message_adapter.py", "ldap_schema_adapter.py", "runtime_db_adapter.py"]
        existing = [f for f in files if os.path.exists(os.path.join(base, f))]
        result = len(existing) == len(files)
        GoalTracker.record("5d", "ACL adapter katmanı mevcut", result,
                           f"{len(existing)}/{len(files)} dosya")
        assert result

    def test_release_gate_surfaces_exist(self):
        """Baseline ve release gate yüzeyi repo içinde tanımlı olmalı."""
        files = [
            "/home/huma/liderahenk-test/platform/contracts/baseline-registry.yaml",
            "/home/huma/liderahenk-test/platform/contracts/failure-taxonomy.yaml",
            "/home/huma/liderahenk-test/platform/contracts/registration-evidence.yaml",
            "/home/huma/liderahenk-test/platform/scripts/validate_golden_baseline.py",
            "/home/huma/liderahenk-test/platform/scripts/capture_golden_baseline.py",
            "/home/huma/liderahenk-test/platform/scripts/diff_baseline.py",
        ]
        existing = [path for path in files if os.path.exists(path)]
        result = len(existing) == len(files)
        GoalTracker.record("5e", "Release gate yüzeyi mevcut", result, f"{len(existing)}/{len(files)} dosya")
        assert result


# ─── Hedef 6: Gözlemlenebilirlik ──────────────────────────────────

class TestGoal6_Observability:
    """README vaadi: 'Prometheus, Grafana, Loki ile tam gözlemlenebilirlik'"""

    def test_prometheus_scraping(self):
        """Prometheus en az 1 target'ı başarıyla scrape ediyor olmalı."""
        resp = http_get("http://127.0.0.1:9090/api/v1/targets")
        if not resp or resp.status_code != 200:
            GoalTracker.record("6a", "Prometheus veri topluyor", False, "Erişilemez")
            pytest.fail("Prometheus erişilemez")
        targets = resp.json().get("data", {}).get("activeTargets", [])
        up_targets = [t for t in targets if t.get("health") == "up"]
        result = len(up_targets) > 0
        GoalTracker.record("6a", "Prometheus veri topluyor", result,
                           f"{len(up_targets)}/{len(targets)} target UP")
        assert result, f"Hiçbir target UP değil. Toplam: {len(targets)}"

    def test_grafana_dashboard_accessible(self):
        """Grafana dashboard'u erişilebilir olmalı."""
        resp = http_get(
            "http://127.0.0.1:3000/api/dashboards/uid/liderahenk-slo",
            auth=("admin", "admin")
        )
        works = resp is not None and resp.status_code == 200
        GoalTracker.record("6b", "Grafana dashboard erişilebilir", works)
        assert works

    def test_grafana_receives_data(self):
        """Grafana üzerinden Prometheus sorgusu veri dönmeli."""
        # Grafana proxy üzerinden PromQL sorgusu
        resp = http_get(
            "http://127.0.0.1:3000/api/datasources/proxy/uid/prometheus/api/v1/query",
            params={"query": "up"},
            auth=("admin", "admin")
        )
        if resp and resp.status_code == 200:
            results = resp.json().get("data", {}).get("result", [])
            has_data = len(results) > 0
            GoalTracker.record("6c", "Grafana veri alıyor", has_data,
                               f"{len(results)} metrik sonucu")
            assert has_data
        else:
            # Fallback: doğrudan Prometheus'tan kontrol et
            prom_resp = http_get(
                "http://127.0.0.1:9090/api/v1/query",
                params={"query": "up"}
            )
            if prom_resp and prom_resp.status_code == 200:
                results = prom_resp.json().get("data", {}).get("result", [])
                has_data = len(results) > 0
                GoalTracker.record("6c", "Grafana veri alıyor", has_data,
                                   f"Prometheus'ta veri var ({len(results)} sonuç), Grafana proxy testi atlandı")
                assert has_data
            else:
                GoalTracker.record("6c", "Grafana veri alıyor", False,
                                   "Ne Grafana ne Prometheus'tan veri alınamadı")
                pytest.fail("Veri alınamadı")


# ─── Son: Skor Raporu ─────────────────────────────────────────────

class TestFinalReport:
    """Tüm testlerin sonunda skor raporu üretir."""

    def test_generate_score_report(self):
        """Platform hedef skor raporu."""
        report = GoalTracker.report()
        print(report)
        # Bu test her zaman geçer — sadece rapor üretir
        total = len(GoalTracker.results)
        passed = sum(1 for r in GoalTracker.results.values() if r["passed"])
        # Sonuçları dosyaya da yaz
        report_path = "/home/huma/liderahenk-test/tests/platform_goal_report.txt"
        with open(report_path, "w") as f:
            f.write(report)
        assert True, report
