#!/usr/bin/env python3
"""
ejabberd Prometheus Metrics Exporter

ejabberd HTTP API'den istatistik çeker ve Prometheus formatında sunar.
Port 9780'de HTTP server olarak çalışır.
"""

from __future__ import annotations

import http.server
import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict


EJABBERD_API = os.environ.get("EJABBERD_API", "http://ejabberd:5280/api")
XMPP_DOMAIN = os.environ.get("XMPP_DOMAIN", "liderahenk.org")
PORT = int(os.environ.get("EXPORTER_PORT", "9780"))

API_STATS = defaultdict(
    lambda: {
        "success": 0,
        "error": 0,
        "last_duration": 0.0,
        "last_success": 0.0,
        "last_status": 0,
    }
)


def _coerce_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def api_call(endpoint, payload):
    """ejabberd HTTP API çağrısı."""
    url = f"{EJABBERD_API}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    stats = API_STATS[endpoint]
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            stats["success"] += 1
            stats["last_success"] = time.time()
            stats["last_status"] = getattr(resp, "status", 200)
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        stats["error"] += 1
        stats["last_status"] = exc.code
        return None
    except (urllib.error.URLError, Exception):
        stats["error"] += 1
        stats["last_status"] = 0
        return None
    finally:
        stats["last_duration"] = time.time() - started


def _append_metric(lines, help_text, metric_type, samples):
    lines.append(f"# HELP {help_text}")
    lines.append(f"# TYPE {metric_type}")
    lines.extend(samples)


def collect_metrics():
    """ejabberd metriklerini topla ve Prometheus formatında döndür."""
    scrape_started = time.time()
    lines = []
    lines.append("# HELP ejabberd_up ejabberd reachable via HTTP API")
    lines.append("# TYPE ejabberd_up gauge")

    users = api_call("registered_users", {"host": XMPP_DOMAIN})
    if users is not None:
        lines.append("ejabberd_up 1")
        user_count = len(users)
        lines.append("# HELP ejabberd_registered_users Number of registered users")
        lines.append("# TYPE ejabberd_registered_users gauge")
        lines.append(f'ejabberd_registered_users{{host="{XMPP_DOMAIN}"}} {user_count}')

        agent_count = sum(1 for user in users if str(user).startswith("ahenk"))
        lines.append("# HELP ejabberd_ahenk_agents Number of registered ahenk agents")
        lines.append("# TYPE ejabberd_ahenk_agents gauge")
        lines.append(f'ejabberd_ahenk_agents{{host="{XMPP_DOMAIN}"}} {agent_count}')
    else:
        lines.append("ejabberd_up 0")
        user_count = 0
        agent_count = 0

    connected = api_call("connected_users_number", {})
    connected_count = _coerce_number(connected, 0)
    if connected is not None:
        lines.append("# HELP ejabberd_connected_users Number of currently connected users")
        lines.append("# TYPE ejabberd_connected_users gauge")
        lines.append(f"ejabberd_connected_users {connected_count}")

    if user_count:
        lines.append("# HELP ejabberd_connected_ratio Ratio of connected users to registered users")
        lines.append("# TYPE ejabberd_connected_ratio gauge")
        lines.append(f"ejabberd_connected_ratio {connected_count / float(user_count)}")

    vhosts = api_call("registered_vhosts", {})
    if vhosts is not None:
        lines.append("# HELP ejabberd_vhosts Number of registered virtual hosts")
        lines.append("# TYPE ejabberd_vhosts gauge")
        lines.append(f"ejabberd_vhosts {len(vhosts)}")

    rooms = api_call("muc_online_rooms", {"service": f"conference.{XMPP_DOMAIN}"})
    if rooms is not None:
        lines.append("# HELP ejabberd_muc_online_rooms Number of online MUC rooms")
        lines.append("# TYPE ejabberd_muc_online_rooms gauge")
        lines.append(f"ejabberd_muc_online_rooms {len(rooms)}")

    stats_uptime = api_call("stats", {"name": "uptimeseconds"})
    if stats_uptime is not None:
        lines.append("# HELP ejabberd_uptime_seconds ejabberd uptime in seconds")
        lines.append("# TYPE ejabberd_uptime_seconds gauge")
        lines.append(f"ejabberd_uptime_seconds {_coerce_number(stats_uptime)}")

    processes = api_call("stats", {"name": "processes"})
    if processes is not None:
        lines.append("# HELP ejabberd_processes Number of Erlang processes")
        lines.append("# TYPE ejabberd_processes gauge")
        lines.append(f"ejabberd_processes {_coerce_number(processes)}")

    lines.append("# HELP ejabberd_api_request_duration_seconds Last API call duration by endpoint")
    lines.append("# TYPE ejabberd_api_request_duration_seconds gauge")
    for endpoint, stats in sorted(API_STATS.items()):
        lines.append(
            f'ejabberd_api_request_duration_seconds{{endpoint="{endpoint}"}} {stats["last_duration"]}'
        )

    lines.append("# HELP ejabberd_api_requests_total Total ejabberd API requests by endpoint and result")
    lines.append("# TYPE ejabberd_api_requests_total counter")
    for endpoint, stats in sorted(API_STATS.items()):
        lines.append(
            f'ejabberd_api_requests_total{{endpoint="{endpoint}",result="success"}} {stats["success"]}'
        )
        lines.append(
            f'ejabberd_api_requests_total{{endpoint="{endpoint}",result="error"}} {stats["error"]}'
        )

    lines.append(
        "# HELP ejabberd_api_last_success_timestamp_seconds Unix timestamp of the last successful ejabberd API call"
    )
    lines.append("# TYPE ejabberd_api_last_success_timestamp_seconds gauge")
    for endpoint, stats in sorted(API_STATS.items()):
        lines.append(
            f'ejabberd_api_last_success_timestamp_seconds{{endpoint="{endpoint}"}} {stats["last_success"]}'
        )

    lines.append("# HELP ejabberd_api_last_http_status Last observed HTTP status per ejabberd API endpoint")
    lines.append("# TYPE ejabberd_api_last_http_status gauge")
    for endpoint, stats in sorted(API_STATS.items()):
        lines.append(
            f'ejabberd_api_last_http_status{{endpoint="{endpoint}"}} {stats["last_status"]}'
        )

    lines.append("# HELP ejabberd_exporter_scrape_duration_seconds Exporter scrape duration")
    lines.append("# TYPE ejabberd_exporter_scrape_duration_seconds gauge")
    lines.append(f"ejabberd_exporter_scrape_duration_seconds {time.time() - scrape_started}")

    return "\n".join(lines) + "\n"


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            metrics = collect_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics.encode("utf-8"))
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    print(f"ejabberd-exporter baslatiliyor - port {PORT}")
    print(f"  API: {EJABBERD_API}")
    print(f"  Domain: {XMPP_DOMAIN}")
    server = http.server.HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
