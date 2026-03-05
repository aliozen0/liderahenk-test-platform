"""
bitnamilegacy/openldap sarmalayıcı.
───────────────────────────────────────────────
Port: 1389 (non-root default — 389 değil!)
Base DN: dc=liderahenk,dc=org
Admin DN: cn=admin,dc=liderahenk,dc=org
Ajan OU: ou=Ahenkler,dc=liderahenk,dc=org
"""

import logging
import ldap3
from typing import Optional

logger = logging.getLogger(__name__)


class LdapSchemaAdapter:
    """bitnamilegacy/openldap LDAP istemcisi."""

    def __init__(self, host: str, port: int = 1389,
                 base_dn: str = None, admin_dn: str = None,
                 admin_pass: str = None):
        self.host = host
        self.port = port           # 1389 — bitnamilegacy default
        self.base_dn = base_dn
        self.admin_dn = admin_dn
        self.admin_pass = admin_pass

    def _connect(self) -> ldap3.Connection:
        """Yeni LDAP bağlantısı oluştur."""
        server = ldap3.Server(self.host, port=self.port,
                              get_info=ldap3.ALL)
        conn = ldap3.Connection(server, user=self.admin_dn,
                                password=self.admin_pass,
                                auto_bind=True)
        return conn

    # ── Ajan İşlemleri ────────────────────────────────────────

    def get_agent_count(self) -> int:
        """ou=Ahenkler altındaki device sayısı."""
        conn = self._connect()
        try:
            conn.search(f"ou=Ahenkler,{self.base_dn}",
                        "(objectClass=device)",
                        search_scope=ldap3.LEVEL)
            return len(conn.entries)
        finally:
            conn.unbind()

    def agent_exists(self, agent_id: str) -> bool:
        """Belirli bir ajan LDAP'ta mevcut mu?"""
        conn = self._connect()
        try:
            conn.search(f"ou=Ahenkler,{self.base_dn}",
                        f"(cn={agent_id})",
                        search_scope=ldap3.LEVEL)
            return len(conn.entries) > 0
        finally:
            conn.unbind()

    def list_agents(self) -> list[str]:
        """Kayıtlı ajan CN'lerini sıralı döndür."""
        conn = self._connect()
        try:
            conn.search(f"ou=Ahenkler,{self.base_dn}",
                        "(objectClass=device)",
                        search_scope=ldap3.LEVEL,
                        attributes=["cn"])
            agents = [str(e.cn) for e in conn.entries]
            return sorted(agents)
        finally:
            conn.unbind()

    # ── OU İşlemleri ──────────────────────────────────────────

    def ou_ahenkler_exists(self) -> bool:
        """ou=Ahenkler organizasyonel birimi mevcut mu?"""
        conn = self._connect()
        try:
            conn.search(self.base_dn,
                        "(ou=Ahenkler)",
                        search_scope=ldap3.LEVEL)
            return len(conn.entries) > 0
        finally:
            conn.unbind()

    def list_ous(self) -> list[str]:
        """Kök DN altındaki OU'ları listele."""
        conn = self._connect()
        try:
            conn.search(self.base_dn,
                        "(objectClass=organizationalUnit)",
                        search_scope=ldap3.LEVEL,
                        attributes=["ou"])
            return sorted([str(e.ou) for e in conn.entries])
        finally:
            conn.unbind()

    # ── Genel LDAP ────────────────────────────────────────────

    def search_entries(self, base_dn: str, ldap_filter: str,
                       attributes: list[str] = None,
                       scope: int = ldap3.SUBTREE) -> list[dict]:
        """Genel amaçlı LDAP arama."""
        conn = self._connect()
        try:
            conn.search(base_dn, ldap_filter,
                        search_scope=scope,
                        attributes=attributes or ["*"])
            return [
                {"dn": str(e.entry_dn),
                 "attrs": dict(e.entry_attributes_as_dict)}
                for e in conn.entries
            ]
        finally:
            conn.unbind()

    def get_tree_dns(self) -> list[str]:
        """Kök DN altındaki tüm entry DN'lerini döndür."""
        conn = self._connect()
        try:
            conn.search(self.base_dn, "(objectClass=*)",
                        search_scope=ldap3.SUBTREE,
                        attributes=[])
            return sorted([str(e.entry_dn) for e in conn.entries])
        finally:
            conn.unbind()

    # ── Health ────────────────────────────────────────────────

    def connection_healthy(self) -> bool:
        """LDAP bağlantısı kurabiliyor mu?"""
        try:
            conn = self._connect()
            conn.unbind()
            return True
        except Exception as e:
            logger.error("LDAP bağlantı hatası: %s", e)
            return False
