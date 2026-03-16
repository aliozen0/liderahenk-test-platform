from __future__ import annotations
"""
ejabberd HTTP API sarmalayıcı.
───────────────────────────────────────────────
ejabberd/ecs: Alpine tabanlı (/bin/sh, bash yok)
API port: 5280
Admin kullanıcı: lider_sunucu@liderahenk.org

ejabberd HTTP API, POST-tabanlı JSON endpoint'ler kullanır.
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class XmppMessageAdapter:
    """ejabberd HTTP API istemcisi."""

    def __init__(self, api_url: str, admin_user: str = None,
                 admin_pass: str = None, domain: str = "liderahenk.org"):
        self.api = api_url.rstrip("/")        # http://ejabberd:5280/api
        self.domain = domain                  # liderahenk.org
        # ejabberd API kimlik doğrulaması (gerekirse)
        self._auth = None
        if admin_user and admin_pass:
            self._auth = (admin_user, admin_pass)

    # ── Kullanıcı Yönetimi ────────────────────────────────────

    def register_user(self, username: str, password: str) -> bool:
        """Idempotent kayıt: 409 → zaten var → True döner."""
        r = requests.post(
            f"{self.api}/register",
            json={"user": username, "host": self.domain,
                  "password": password},
            timeout=10,
        )
        if r.status_code in (200, 201):
            logger.info("XMPP kayıt: %s@%s oluşturuldu", username, self.domain)
            return True
        elif r.status_code == 409:
            logger.debug("XMPP kayıt: %s@%s zaten mevcut", username, self.domain)
            return True
        else:
            logger.error("XMPP kayıt hatası: %s → HTTP %s",
                         username, r.status_code)
            return False

    def unregister_user(self, username: str) -> bool:
        """Kullanıcı sil."""
        r = requests.post(
            f"{self.api}/unregister",
            json={"user": username, "host": self.domain},
            timeout=10,
        )
        return r.status_code in (200, 201)

    def is_user_registered(self, username: str) -> bool:
        """Kullanıcı kayıtlı mı?"""
        r = requests.post(
            f"{self.api}/check_account",
            json={"user": username, "host": self.domain},
            timeout=10,
        )
        return r.status_code == 200

    def list_registered_users(self) -> list[str]:
        """Domain'deki kayıtlı kullanıcılar."""
        r = requests.post(
            f"{self.api}/registered_users",
            json={"host": self.domain},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def list_connected_users(self) -> list[str]:
        """Bağlı kullanıcıları normalize edilmemiş halleriyle döndür."""
        r = requests.post(
            f"{self.api}/connected_users",
            json={},
            timeout=10,
        )
        r.raise_for_status()
        payload = r.json()
        if isinstance(payload, list):
            result = []
            for item in payload:
                if isinstance(item, dict):
                    for key in ("jid", "user", "username"):
                        value = item.get(key)
                        if value:
                            result.append(str(value))
                            break
                else:
                    result.append(str(item))
            return result
        return []

    # ── İstatistik ────────────────────────────────────────────

    def get_registered_count(self) -> int:
        """Toplam kayıtlı kullanıcı sayısı."""
        r = requests.post(
            f"{self.api}/registered_users",
            json={"host": self.domain},
            timeout=10,
        )
        r.raise_for_status()
        users = r.json()
        return len(users) if isinstance(users, list) else int(users)

    def get_connected_count(self) -> int:
        """Bağlı kullanıcı sayısı."""
        users = self.list_connected_users()
        return len(users) if isinstance(users, list) else int(users)

    # ── VHost ─────────────────────────────────────────────────

    def get_vhosts(self) -> list[str]:
        """Kayıtlı virtual host'lar."""
        r = requests.post(
            f"{self.api}/registered_vhosts",
            json={},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def vhost_exists(self, vhost: str) -> bool:
        """Belirli bir vhost kayıtlı mı?"""
        return vhost in self.get_vhosts()

    # ── Health ────────────────────────────────────────────────

    def api_healthy(self) -> bool:
        """ejabberd HTTP API erişilebilir mi?"""
        try:
            self.get_registered_count()
            return True
        except Exception:
            return False
