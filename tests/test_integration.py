"""
Entegrasyon testleri — ScenarioRunner üzerinden.
make dev çalışıyor olmalı.
"""
import pytest
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.main import ScenarioRunner


@pytest.fixture(scope="module")
def runner():
    return ScenarioRunner()


class TestRegistrationScenario:
    """LDAP + XMPP kayıt tutarlılığı."""

    def test_registration_scenario_passes(self, runner):
        """registration_test.yml senaryosu PASS olmalı."""
        results = runner.run("orchestrator/scenarios/registration_test.yml")
        assert results["passed"], f"registration_test başarısız: {results['steps']}"

    def test_ldap_agent_count(self, runner):
        """LDAP'ta beklenen ajan sayısı."""
        count = runner.ldap.get_agent_count()
        assert count == runner.ahenk_count, \
            f"LDAP: beklenen {runner.ahenk_count}, bulunan {count}"

    def test_xmpp_agent_count(self, runner):
        """XMPP'te beklenen ajan sayısı (lider_sunucu hariç)."""
        total = runner.xmpp.get_registered_count()
        agents = total - 1  # lider_sunucu çıkar
        assert agents >= runner.ahenk_count, \
            f"XMPP: beklenen >={runner.ahenk_count}, bulunan {agents}"


class TestBasicScenario:
    """Temel API erişim ve ajan doğrulama."""

    def test_basic_scenario_passes(self, runner):
        """basic_task.yml senaryosu PASS olmalı."""
        results = runner.run("orchestrator/scenarios/basic_task.yml")
        assert results["passed"], f"basic_task başarısız: {results['steps']}"

    def test_api_health(self, runner):
        """liderapi ayakta ve sağlıklı."""
        assert runner.api.health_check(), "liderapi erişilemez"

    def test_jwt_authenticated(self, runner):
        """JWT token alınmış olmalı."""
        assert runner.api.is_authenticated, "JWT auth başarısız"


class TestAgentConsistency:
    """Ajan kayıt tutarlılık testleri."""

    def test_first_agent_exists_ldap(self, runner):
        """ahenk-001 LDAP'ta mevcut."""
        assert runner.ldap.agent_exists("ahenk-001")

    def test_first_agent_exists_xmpp(self, runner):
        """ahenk-001 XMPP'te kayıtlı."""
        assert runner.xmpp.is_user_registered("ahenk-001")

    def test_last_agent_exists(self, runner):
        """Son ajan her iki serviste de mevcut."""
        last = f"ahenk-{runner.ahenk_count:03d}"
        assert runner.ldap.agent_exists(last), f"{last} LDAP'ta yok"
        assert runner.xmpp.is_user_registered(last), f"{last} XMPP'te yok"


class TestLiderApiRegistration:
    """Lider domain state testleri — registration contract kabul kriterleri."""

    def test_c_agent_count_matches_ahenk_count(self, runner):
        """c_agent tablosunda AHENK_COUNT kadar kayıt olmalı."""
        import os
        import subprocess
        import pymysql

        hosts = [(os.environ.get("MYSQL_HOST", "127.0.0.1"),
                  int(os.environ.get("MYSQL_PORT", "3306")))]
        try:
            mariadb_ip = subprocess.check_output(
                ["docker", "inspect", "-f",
                 "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                 "liderahenk-test-mariadb-1"],
                text=True,
            ).strip()
            if mariadb_ip and all(host != mariadb_ip for host, _ in hosts):
                hosts.append((mariadb_ip, 3306))
        except Exception:
            pass

        passwords = [os.environ.get("MYSQL_PASSWORD"), "DEGISTIR", "secret"]
        conn = None
        last_error = None
        for host, port in hosts:
            for password in passwords:
                if not password:
                    continue
                try:
                    conn = pymysql.connect(
                        host=host,
                        port=port,
                        user=os.environ.get("MYSQL_USER", "lider"),
                        password=password,
                        database=os.environ.get("MYSQL_DATABASE", "liderahenk"),
                        connect_timeout=5,
                    )
                    break
                except Exception as exc:
                    last_error = exc
            if conn:
                break

        assert conn is not None, f"MySQL bağlantısı kurulamadı: {last_error}"
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM c_agent")
        count = cursor.fetchone()[0]
        conn.close()

        expected = int(os.environ.get("AHENK_COUNT", "1"))
        assert count >= expected, \
            f"c_agent: beklenen >={expected}, bulunan {count}"

    def test_dashboard_total_computer_positive(self, runner):
        """Dashboard API totalComputerNumber > 0 dönmeli."""
        info = runner.api.get_dashboard_info()
        assert info is not None, "Dashboard API yanıt vermedi"
        total = info.get("totalComputerNumber", 0)
        assert total > 0, \
            f"totalComputerNumber 0 — c_agent boş veya API hatası"

    def test_agent_list_not_empty(self, runner):
        """agent-info/list en az 1 ajan dönmeli."""
        agents = runner.api.get_agent_list()
        assert agents is not None, "agent-info/list yanıt vermedi"
        assert len(agents) > 0, "Ajan listesi boş"

    def test_first_agent_in_lider_domain(self, runner):
        """ahenk-001 Lider domain state'inde mevcut olmalı."""
        agents = runner.api.get_agent_list()
        jids = [a.get("jid", "") for a in agents if a]
        assert any("ahenk-001" in jid for jid in jids), \
            f"ahenk-001 agent listesinde yok. Bulunanlar: {jids[:3]}"
