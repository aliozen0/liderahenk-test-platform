#!/usr/bin/env python3
"""
Read-only synthetic probe exporter for LiderAhenk.

This exporter only exercises login and visibility flows so it can run
continuously in shared developer environments without mutating state.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from ldap3 import ALL, Connection, Server
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry
from prometheus_client import Counter, Gauge, Histogram, generate_latest


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("platform-exporter")

EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9790"))
PROBE_INTERVAL_SECONDS = int(os.environ.get("PROBE_INTERVAL_SECONDS", "15"))

LIDER_API_URL = os.environ.get("LIDER_API_URL", "http://liderapi:8080").rstrip("/")
LIDER_USER = os.environ.get("LIDER_USER", "lider-admin")
LIDER_PASS = os.environ.get("LIDER_PASS", "secret")

EJABBERD_API = os.environ.get("EJABBERD_API", "http://ejabberd:5280/api").rstrip("/")
XMPP_DOMAIN = os.environ.get("XMPP_DOMAIN", "liderahenk.org")

LDAP_HOST = os.environ.get("LDAP_HOST", "ldap")
LDAP_PORT = int(os.environ.get("LDAP_PORT", "1389"))
LDAP_BASE_DN = os.environ.get("LDAP_BASE_DN", "dc=liderahenk,dc=org")
LDAP_AGENT_BASE_DN = os.environ.get(
    "LDAP_AGENT_BASE_DN",
    f"ou=Ahenkler,{LDAP_BASE_DN}",
)
LDAP_ADMIN_USERNAME = os.environ.get("LDAP_ADMIN_USERNAME", "admin")
LDAP_ADMIN_PASSWORD = os.environ.get("LDAP_ADMIN_PASSWORD", "DEGISTIR")
LDAP_BIND_DN = os.environ.get(
    "LDAP_BIND_DN",
    f"cn={LDAP_ADMIN_USERNAME},{LDAP_BASE_DN}",
)

HTTP_TIMEOUT = 10

REGISTRY = CollectorRegistry()

PROBE_RESULTS_TOTAL = Counter(
    "lider_probe_results_total",
    "Synthetic probe execution results.",
    ["probe", "result"],
    registry=REGISTRY,
)
PROBE_SUCCESS = Gauge(
    "lider_probe_success",
    "Latest success value for each probe.",
    ["probe"],
    registry=REGISTRY,
)
PROBE_HTTP_STATUS = Gauge(
    "lider_probe_http_status",
    "Latest HTTP status observed by each probe.",
    ["probe"],
    registry=REGISTRY,
)
PROBE_LAST_DURATION = Gauge(
    "lider_probe_last_duration_seconds",
    "Latest probe duration in seconds.",
    ["probe"],
    registry=REGISTRY,
)
PROBE_LAST_SUCCESS_TS = Gauge(
    "lider_probe_last_success_timestamp_seconds",
    "Unix timestamp of the latest successful probe.",
    ["probe"],
    registry=REGISTRY,
)
PROBE_DURATION = Histogram(
    "lider_probe_duration_seconds",
    "Latency of each synthetic probe.",
    ["probe"],
    registry=REGISTRY,
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20),
)
PROBE_AGENT_COUNT = Gauge(
    "lider_probe_agent_count",
    "Observed agent count by source.",
    ["source"],
    registry=REGISTRY,
)
PROBE_AGENT_COUNT_DELTA = Gauge(
    "lider_probe_agent_count_delta",
    "Absolute delta between two agent count sources.",
    ["left", "right"],
    registry=REGISTRY,
)
PROBE_DASHBOARD_TOTAL_COMPUTERS = Gauge(
    "lider_probe_dashboard_total_computers",
    "Total computers value reported by dashboard info.",
    registry=REGISTRY,
)
PROBE_COMPUTER_TREE_NODES = Gauge(
    "lider_probe_computer_tree_nodes",
    "Number of nodes returned by the computer tree.",
    registry=REGISTRY,
)
PROBE_PLATFORM_UP = Gauge(
    "lider_probe_platform_up",
    "Overall status for read-only platform evidence probes.",
    registry=REGISTRY,
)

STATE_LOCK = threading.Lock()
STATE = {
    "healthy": False,
    "last_run": 0.0,
    "last_error": "",
}


def _safe_json(response: requests.Response):
    try:
        return response.json()
    except ValueError:
        return None


def _record_probe(probe: str, success: bool, duration: float, http_status: int | None):
    result = "success" if success else "failure"
    PROBE_RESULTS_TOTAL.labels(probe=probe, result=result).inc()
    PROBE_SUCCESS.labels(probe=probe).set(1 if success else 0)
    PROBE_LAST_DURATION.labels(probe=probe).set(duration)
    if http_status is not None:
        PROBE_HTTP_STATUS.labels(probe=probe).set(http_status)
    PROBE_DURATION.labels(probe=probe).observe(duration)
    if success:
        PROBE_LAST_SUCCESS_TS.labels(probe=probe).set_to_current_time()


def _post(session: requests.Session, path: str, json_body=None, data=None):
    return session.post(
        f"{LIDER_API_URL}{path}",
        json=json_body,
        data=data,
        timeout=HTTP_TIMEOUT,
    )


def _probe_login(session: requests.Session):
    started = time.time()
    response = None
    try:
        response = session.post(
            f"{LIDER_API_URL}/api/auth/signin",
            json={"username": LIDER_USER, "password": LIDER_PASS},
            timeout=HTTP_TIMEOUT,
        )
        payload = _safe_json(response) or {}
        token = payload.get("token")
        success = response.status_code == 200 and bool(token)
        if success:
            session.headers.update({"Authorization": f"Bearer {token}"})
        return success, response.status_code, payload
    except requests.RequestException as exc:
        LOGGER.warning("jwt_login probe failed: %s", exc)
        return False, None, {}
    finally:
        _record_probe(
            "jwt_login",
            response is not None and response.status_code == 200 and "Authorization" in session.headers,
            time.time() - started,
            response.status_code if response is not None else None,
        )


def _probe_dashboard_info(session: requests.Session):
    started = time.time()
    response = None
    success = False
    payload = {}
    try:
        response = _post(session, "/api/dashboard/info", json_body={})
        payload = _safe_json(response) or {}
        success = response.status_code == 200 and isinstance(payload, dict)
        if success:
            total_computers = (
                payload.get("totalComputers")
                or payload.get("computerCount")
                or payload.get("totalAgent")
                or 0
            )
            try:
                PROBE_DASHBOARD_TOTAL_COMPUTERS.set(float(total_computers))
            except (TypeError, ValueError):
                PROBE_DASHBOARD_TOTAL_COMPUTERS.set(0)
        return success, response.status_code, payload
    except requests.RequestException as exc:
        LOGGER.warning("dashboard_info probe failed: %s", exc)
        return False, None, {}
    finally:
        _record_probe(
            "dashboard_info",
            success,
            time.time() - started,
            response.status_code if response is not None else None,
        )


def _probe_agent_list(session: requests.Session):
    started = time.time()
    response = None
    success = False
    agent_count = 0
    try:
        response = _post(
            session,
            "/api/lider/agent-info/list",
            json_body={
                "pageNumber": 1,
                "pageSize": 500,
                "agentStatus": "ALL",
                "status": "",
                "dn": "",
                "hostname": "",
                "macAddress": "",
                "ipAddress": "",
                "brand": "",
                "model": "",
                "processor": "",
                "osVersion": "",
                "agentVersion": "",
                "diskType": "",
                "selectedOUDN": "",
                "groupName": "",
                "groupDN": "",
                "sessionReportType": "",
            },
        )
        payload = _safe_json(response) or {}
        content = payload.get("content")
        if isinstance(content, list):
            agent_count = len(content)
            success = response.status_code == 200
        elif isinstance(payload.get("agents"), dict):
            agent_count = len(payload["agents"].get("content", []))
            success = response.status_code == 200
        PROBE_AGENT_COUNT.labels(source="liderapi").set(agent_count)
        return success, response.status_code, agent_count
    except requests.RequestException as exc:
        LOGGER.warning("agent_list probe failed: %s", exc)
        return False, None, agent_count
    finally:
        _record_probe(
            "agent_list",
            success,
            time.time() - started,
            response.status_code if response is not None else None,
        )


def _count_tree_nodes(nodes):
    if not isinstance(nodes, list):
        return 0
    total = 0
    stack = list(nodes)
    while stack:
        node = stack.pop()
        total += 1
        children = node.get("childEntries", []) if isinstance(node, dict) else []
        if isinstance(children, list):
            stack.extend(children)
    return total


def _probe_computer_tree(session: requests.Session):
    started = time.time()
    response = None
    success = False
    node_count = 0
    try:
        response = _post(session, "/api/lider/computer/computers", json_body={})
        payload = _safe_json(response)
        nodes = payload if isinstance(payload, list) else (payload or {}).get("entries", [])
        success = response.status_code == 200 and isinstance(nodes, list)
        node_count = _count_tree_nodes(nodes)
        PROBE_COMPUTER_TREE_NODES.set(node_count)
        return success, response.status_code, node_count
    except requests.RequestException as exc:
        LOGGER.warning("computer_tree probe failed: %s", exc)
        return False, None, node_count
    finally:
        _record_probe(
            "computer_tree",
            success,
            time.time() - started,
            response.status_code if response is not None else None,
        )


def _probe_ejabberd_registered_users():
    started = time.time()
    response = None
    success = False
    count = 0
    try:
        response = requests.post(
            f"{EJABBERD_API}/registered_users",
            json={"host": XMPP_DOMAIN},
            timeout=HTTP_TIMEOUT,
        )
        payload = _safe_json(response) or []
        success = response.status_code == 200 and isinstance(payload, list)
        count = sum(1 for user in payload if str(user).startswith("ahenk")) if isinstance(payload, list) else 0
        PROBE_AGENT_COUNT.labels(source="xmpp").set(count)
        return success, response.status_code, count
    except requests.RequestException as exc:
        LOGGER.warning("xmpp_registered_users probe failed: %s", exc)
        return False, None, count
    finally:
        _record_probe(
            "xmpp_registered_users",
            success,
            time.time() - started,
            response.status_code if response is not None else None,
        )


def _probe_ldap_agent_count():
    started = time.time()
    success = False
    count = 0
    try:
        server = Server(LDAP_HOST, port=LDAP_PORT, get_info=ALL)
        with Connection(
            server,
            user=LDAP_BIND_DN,
            password=LDAP_ADMIN_PASSWORD,
            auto_bind=True,
            receive_timeout=HTTP_TIMEOUT,
        ) as conn:
            success = conn.search(
                search_base=LDAP_AGENT_BASE_DN,
                search_filter="(objectClass=device)",
                attributes=["cn"],
            )
            count = len(conn.entries)
        PROBE_AGENT_COUNT.labels(source="ldap").set(count)
        return success, 200 if success else 0, count
    except Exception as exc:  # pragma: no cover - network/runtime failures
        LOGGER.warning("ldap_agent_count probe failed: %s", exc)
        return False, None, count
    finally:
        _record_probe(
            "ldap_agent_count",
            success,
            time.time() - started,
            200 if success else None,
        )


def _update_deltas(agent_counts):
    pairs = [("liderapi", "ldap"), ("liderapi", "xmpp"), ("ldap", "xmpp")]
    for left, right in pairs:
        delta = abs(int(agent_counts.get(left, 0)) - int(agent_counts.get(right, 0)))
        PROBE_AGENT_COUNT_DELTA.labels(left=left, right=right).set(delta)


def probe_forever():
    while True:
        session = requests.Session()
        overall_success = True
        last_error = ""
        agent_counts = {}
        try:
            login_ok, _, _ = _probe_login(session)
            overall_success = overall_success and login_ok

            dashboard_ok, _, _ = _probe_dashboard_info(session)
            overall_success = overall_success and dashboard_ok

            agent_list_ok, _, liderapi_count = _probe_agent_list(session)
            overall_success = overall_success and agent_list_ok
            agent_counts["liderapi"] = liderapi_count

            tree_ok, _, _ = _probe_computer_tree(session)
            overall_success = overall_success and tree_ok

            xmpp_ok, _, xmpp_count = _probe_ejabberd_registered_users()
            overall_success = overall_success and xmpp_ok
            agent_counts["xmpp"] = xmpp_count

            ldap_ok, _, ldap_count = _probe_ldap_agent_count()
            overall_success = overall_success and ldap_ok
            agent_counts["ldap"] = ldap_count

            _update_deltas(agent_counts)
            PROBE_PLATFORM_UP.set(1 if overall_success else 0)
        except Exception as exc:  # pragma: no cover - defensive
            overall_success = False
            last_error = str(exc)
            LOGGER.exception("Unexpected probe failure")
            PROBE_PLATFORM_UP.set(0)
        finally:
            with STATE_LOCK:
                STATE["healthy"] = overall_success
                STATE["last_run"] = time.time()
                STATE["last_error"] = last_error

        time.sleep(PROBE_INTERVAL_SECONDS)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            payload = generate_latest(REGISTRY)
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path == "/health":
            with STATE_LOCK:
                healthy = STATE["healthy"]
                body = json.dumps(STATE).encode("utf-8")
            self.send_response(200 if healthy else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):  # noqa: A003
        return


def main():
    worker = threading.Thread(target=probe_forever, daemon=True)
    worker.start()

    server = ThreadingHTTPServer(("0.0.0.0", EXPORTER_PORT), Handler)
    LOGGER.info("platform-exporter listening on port %s", EXPORTER_PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
