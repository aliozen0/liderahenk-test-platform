"""
ejabberd HTTP API sözleşme testleri.
───────────────────────────────────────────────
Admin kullanıcı: lider_sunucu@liderahenk.org
API port: 5280
VHosts: localhost, liderahenk.org
"""


class TestEjabberdApi:
    """ejabberd HTTP API erişilebilirlik testleri."""

    def test_ejabberd_api_reachable(self, xmpp):
        """ejabberd HTTP API 5280'de erişilebilir."""
        assert xmpp.api_healthy(), \
            "ejabberd API yanıt vermedi (port 5280)"

    def test_registered_count_positive(self, xmpp):
        """En az bir kayıtlı kullanıcı var."""
        count = xmpp.get_registered_count()
        assert count > 0, \
            f"Kayıtlı kullanıcı yok (count={count})"


class TestEjabberdVhosts:
    """Virtual host testleri."""

    def test_liderahenk_vhost_exists(self, xmpp):
        """liderahenk.org vhost kayıtlı."""
        assert xmpp.vhost_exists("liderahenk.org"), \
            "liderahenk.org vhost bulunamadı"

    def test_localhost_vhost_exists(self, xmpp):
        """localhost vhost kayıtlı."""
        assert xmpp.vhost_exists("localhost"), \
            "localhost vhost bulunamadı"


class TestEjabberdUsers:
    """XMPP kullanıcı testleri."""

    def test_lider_sunucu_registered(self, xmpp):
        """lider_sunucu sistem kullanıcısı kayıtlı."""
        assert xmpp.is_user_registered("lider_sunucu"), \
            "lider_sunucu@liderahenk.org kayıtlı değil"

    def test_ahenk_agents_registered(self, xmpp, agent_count):
        """AHENK_COUNT kadar ajan XMPP'te kayıtlı."""
        count = xmpp.get_registered_count()
        # lider_sunucu + N ajan = en az N+1
        assert count >= agent_count, \
            f"Beklenen en az {agent_count}, XMPP'te {count} kayıt"

    def test_first_ahenk_registered(self, xmpp):
        """ahenk-001 XMPP'te kayıtlı."""
        assert xmpp.is_user_registered("ahenk-001"), \
            "ahenk-001@liderahenk.org kayıtlı değil"

    def test_registration_idempotent(self, xmpp):
        """Aynı kullanıcıyı tekrar kaydetmek hata vermemeli."""
        result = xmpp.register_user("ahenk-001", "test-pass")
        assert result is True, \
            "Tekrar kayıt (409) idempotent değil"

    def test_user_list_contains_agents(self, xmpp):
        """Kullanıcı listesinde ajan kayıtları var."""
        users = xmpp.list_registered_users()
        ahenk_users = [u for u in users if u.startswith("ahenk-")]
        assert len(ahenk_users) > 0, \
            "Kullanıcı listesinde hiç ahenk-* kullanıcısı yok"
