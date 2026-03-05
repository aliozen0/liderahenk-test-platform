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
