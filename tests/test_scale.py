"""
Ölçek testleri — yavaş, sadece scale marker ile koşar.
Kullanım: AHENK_COUNT=20 make test-scale
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


@pytest.mark.scale
def test_scale_scenario(runner):
    """scale_test senaryosu PASS olmalı."""
    results = runner.run("orchestrator/legacy_scenarios/scale_test.yml")
    assert results["passed"], f"scale_test başarısız: {results['steps']}"


@pytest.mark.scale
def test_agents_all_registered_ldap(runner):
    """Tüm ajanlar LDAP'ta kayıtlı."""
    count = runner.ldap.get_agent_count()
    assert count == runner.ahenk_count, \
        f"LDAP: beklenen {runner.ahenk_count}, bulunan {count}"


@pytest.mark.scale
def test_agents_all_registered_xmpp(runner):
    """Tüm ajanlar XMPP'te kayıtlı."""
    total = runner.xmpp.get_registered_count()
    agents = total - 1 if total > 0 else 0
    assert agents == runner.ahenk_count, \
        f"XMPP: beklenen {runner.ahenk_count}, bulunan {agents}"
