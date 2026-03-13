from __future__ import annotations
"""
LiderAhenk REST API soyutlaması.
───────────────────────────────────────────────
Auth mekanizması: JWT — POST /api/auth/signin
  Payload  : {"username": "<uid>", "password": "<ldap_pass>"}
  Response : {"token": "...", "refreshToken": "...", "type": "Bearer", ...}
  Header   : Authorization: Bearer <token>

LDAP kullanıcı filtresi (tersine mühendislik):
  (&(objectClass=pardusAccount)(objectClass=pardusLider)
    (liderPrivilege=ROLE_USER)(uid=$username))

Açık endpoint'ler (auth gerektirmez):
  /api/auth/signin, /api/auth/verify-otp, /api/auth/refresh-token,
  /api/forgot-password/**, /api/lider-info/**, /liderws/**

liderapi port: 8082 (8080 host Tomcat ile çakışıyordu)
"""

import os
import time
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class LiderApiAdapter:
    """LiderAhenk REST API istemcisi."""

    AUTH_ENDPOINT = "/api/auth/signin"
    REFRESH_ENDPOINT = "/api/auth/refresh-token"

    def __init__(self, base_url: str, version: str = None,
                 username: str = None, password: str = None):
        self.base_url = base_url.rstrip("/")
        self.version = version
        self.session = requests.Session()
        self._token = None
        self._refresh_token = None
        self._authenticated = False

        if username and password:
            self._authenticate(username, password)

    # ── Auth ──────────────────────────────────────────────────

    def _authenticate(self, username: str, password: str) -> bool:
        """
        JWT login: POST /api/auth/signin → Bearer token.
        Kullanıcı LDAP'ta pardusAccount + pardusLider objectClass'ına
        sahip olmalıdır.
        """
        try:
            r = requests.post(
                f"{self.base_url}{self.AUTH_ENDPOINT}",
                json={"username": username, "password": password},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                self._token = data.get("token")
                self._refresh_token = data.get("refreshToken")
                self.session.headers.update({
                    "Authorization": f"Bearer {self._token}"
                })
                self._authenticated = True
                logger.info("JWT auth başarılı: %s", username)
                return True
            else:
                logger.warning(
                    "JWT auth başarısız: HTTP %s — %s",
                    r.status_code, r.text[:200],
                )
                return False
        except requests.RequestException as e:
            logger.error("Auth bağlantı hatası: %s", e)
            return False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    def refresh_token(self) -> bool:
        """Mevcut refresh token ile yeni JWT al."""
        if not self._refresh_token:
            return False
        try:
            r = requests.post(
                f"{self.base_url}{self.REFRESH_ENDPOINT}",
                json={"refreshToken": self._refresh_token},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                self._token = data.get("token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self._token}"
                })
                return True
        except requests.RequestException:
            pass
        return False

    # ── API URL ───────────────────────────────────────────────

    def _api_url(self, path: str) -> str:
        """API URL oluştur. version varsa prefix ekle."""
        clean = path.lstrip("/")
        if self.version:
            return f"{self.base_url}/api/{self.version}/{clean}"
        return f"{self.base_url}/api/{clean}"

    # ── Endpoints ─────────────────────────────────────────────

    def get_agents(self) -> list[dict]:
        """Kayıtlı ajanları döndür — POST /api/lider/computer/computers"""
        r = self.session.post(
            f"{self.base_url}/api/lider/computer/computers",
            json={},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        return data.get("content", data.get("entries", []))

    def _auth_headers(self) -> dict[str, str]:
        """Geçerli JWT varsa explicit auth header üret."""
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def get_dashboard_info(self) -> Optional[dict]:
        """Dashboard bilgisi — POST /api/dashboard/info"""
        try:
            r = self.session.post(
                f"{self.base_url}/api/dashboard/info",
                headers=self._auth_headers(),
                json={},
                timeout=10,
            )
            if r.status_code == 200:
                return r.json()
            logger.warning("Dashboard info başarısız: HTTP %s", r.status_code)
        except Exception as e:
            logger.error("Dashboard info hatası: %s", e)
        return None

    def get_agent_list(self) -> list[dict]:
        """Ajan listesini döner."""
        try:
            r = self.session.post(
                f"{self.base_url}/api/lider/agent-info/list",
                headers=self._auth_headers(),
                json={"agentStatus": "ALL", "pageNumber": 1, "pageSize": 20},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                agents = data.get("content")
                if agents is None and isinstance(data.get("agents"), dict):
                    agents = data["agents"].get("content", [])
                return agents if isinstance(agents, list) else []
        except Exception as e:
            logger.error("Agent list hatası: %s", e)
        return []

    def get_agent_info_list(self, page: int = 1, size: int = 100) -> dict:
        """Agent bilgi listesi — POST /api/lider/agent-info/list
        Not: liderapi AgentDTO'da Optional field NPE bug'ı var.
        Tüm query param'lar gönderilmeli."""
        params = {
            "pageNumber": page, "pageSize": size,
            "agentStatus": "ALL", "status": "", "dn": "",
            "hostname": "", "macAddress": "", "ipAddress": "",
            "brand": "", "model": "", "processor": "",
            "osVersion": "", "agentVersion": "", "diskType": "",
            "selectedOUDN": "", "groupName": "", "groupDN": "",
            "sessionReportType": "",
        }
        r = self.session.post(
            f"{self.base_url}/api/lider/agent-info/list",
            params=params,
            timeout=10,
        )
        r.raise_for_status()
        return r.json()

    def get_agent_count(self) -> int:
        """Kayıtlı ajan sayısı."""
        return len(self.get_agents())

    def wait_for_agents(self, min_count: int, timeout: int = 120) -> bool:
        """min_count ajan bağlanana kadar bekle."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                if self.get_agent_count() >= min_count:
                    return True
            except Exception:
                pass
            time.sleep(5)
        return False

    def send_task(self, agent_ids: list, task_type: str,
                  params: dict) -> Optional[str]:
        """Ajanlara görev gönder — POST /api/tasks"""
        payload = {
            "commandClsId": task_type,
            "dnList": agent_ids,
            "parameterMap": params,
        }
        r = self.session.post(
            self._api_url("tasks"), json=payload, timeout=15
        )
        r.raise_for_status()
        data = r.json()
        return data.get("taskId") or data.get("id")

    def get_task_results(self, task_id: str) -> dict:
        """Görev sonuçlarını al — GET /api/tasks/{id}/results"""
        r = self.session.get(
            self._api_url(f"tasks/{task_id}/results"), timeout=10
        )
        r.raise_for_status()
        return r.json()

    def get_server_info(self) -> dict:
        """Sunucu bilgisi — GET /api/lider-info (auth gerektirmez)."""
        r = requests.get(
            f"{self.base_url}/api/lider-info", timeout=5
        )
        r.raise_for_status()
        return r.json()

    # ── Health ────────────────────────────────────────────────

    def health_check(self) -> bool:
        """liderapi ayakta mı? 401 bile olsa uygulama çalışıyor."""
        try:
            r = requests.get(
                f"{self.base_url}/actuator/health", timeout=5
            )
            return r.status_code in (200, 401)
        except Exception:
            return False

    def signin_endpoint_available(self) -> bool:
        """POST /api/auth/signin endpoint'i mevcut mu? (405 kabul)."""
        try:
            r = requests.get(
                f"{self.base_url}{self.AUTH_ENDPOINT}", timeout=5
            )
            # GET → 405 veya 401 = endpoint var
            return r.status_code in (200, 401, 405)
        except Exception:
            return False
