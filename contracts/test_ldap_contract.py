"""
bitnamilegacy/openldap sözleşme testleri.
───────────────────────────────────────────────
Port 1389 — bitnamilegacy non-root default (389 değil!)
Base DN: dc=liderahenk,dc=org
Ajan OU: ou=Ahenkler,dc=liderahenk,dc=org
"""


class TestLdapConnection:
    """LDAP bağlantı testleri."""

    def test_ldap_connection_port_1389(self, ldap):
        """bitnamilegacy port 1389'da erişilebilir."""
        assert ldap.connection_healthy(), \
            "LDAP bağlantısı başarısız (port 1389 kontrol et)"


class TestLdapStructure:
    """LDAP yapısı testleri."""

    def test_ou_ahenkler_exists(self, ldap):
        """ou=Ahenkler organizasyonel birimi mevcut."""
        assert ldap.ou_ahenkler_exists(), \
            "ou=Ahenkler bulunamadı — provisioner çalıştı mı?"

    def test_base_dn_has_ous(self, ldap):
        """Kök DN altında OU'lar mevcut."""
        ous = ldap.list_ous()
        assert len(ous) > 0, \
            "Kök DN altında hiç OU bulunamadı"

    def test_tree_not_empty(self, ldap):
        """LDAP ağacı boş değil."""
        dns = ldap.get_tree_dns()
        assert len(dns) > 1, \
            "LDAP ağacı boş — sadece kök DN var"


class TestLdapAgents:
    """LDAP ajan kayıtları testleri."""

    def test_agent_count_matches_env(self, ldap, agent_count):
        """AHENK_COUNT kadar ajan kaydı mevcut."""
        count = ldap.get_agent_count()
        assert count == agent_count, \
            f"Beklenen {agent_count} ajan, LDAP'ta {count} kayıt"

    def test_first_agent_exists(self, ldap):
        """ahenk-001 kaydı mevcut."""
        assert ldap.agent_exists("ahenk-001"), \
            "ahenk-001 LDAP'ta bulunamadı"

    def test_last_agent_exists(self, ldap, agent_count):
        """Son ajan kaydı mevcut."""
        last = f"ahenk-{agent_count:03d}"
        assert ldap.agent_exists(last), \
            f"{last} LDAP'ta bulunamadı"

    def test_agent_list_sorted(self, ldap, agent_count):
        """Ajan listesi ahenk-001..N formatında sıralı."""
        agents = ldap.list_agents()
        assert len(agents) == agent_count, \
            f"Beklenen {agent_count}, var {len(agents)}"
        assert agents[0] == "ahenk-001", \
            f"İlk ajan ahenk-001 değil: {agents[0]}"
        expected_last = f"ahenk-{agent_count:03d}"
        assert agents[-1] == expected_last, \
            f"Son ajan {expected_last} değil: {agents[-1]}"

    def test_nonexistent_agent(self, ldap):
        """Olmayan ajan False döndürmeli."""
        assert not ldap.agent_exists("ahenk-999"), \
            "ahenk-999 olmamalı ama bulundu"
