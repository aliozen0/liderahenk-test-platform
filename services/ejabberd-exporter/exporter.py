#!/usr/bin/env python3
"""
ejabberd Prometheus Metrics Exporter
ejabberd HTTP API'den istatistik çeker ve Prometheus formatında sunar.
Port 9780'de HTTP server olarak çalışır.
"""
import http.server
import json
import urllib.request
import urllib.error
import time
import os

EJABBERD_API = os.environ.get("EJABBERD_API", "http://ejabberd:5280/api")
XMPP_DOMAIN = os.environ.get("XMPP_DOMAIN", "liderahenk.org")
PORT = int(os.environ.get("EXPORTER_PORT", "9780"))


def api_call(endpoint, payload):
    """ejabberd HTTP API çağrısı."""
    url = f"{EJABBERD_API}/{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, Exception):
        return None


def collect_metrics():
    """ejabberd metriklerini topla ve Prometheus formatında döndür."""
    lines = []
    lines.append("# HELP ejabberd_up ejabberd reachable via HTTP API")
    lines.append("# TYPE ejabberd_up gauge")

    # Kayıtlı kullanıcı sayısı
    users = api_call("registered_users", {"host": XMPP_DOMAIN})
    if users is not None:
        lines.append("ejabberd_up 1")
        user_count = len(users)
        lines.append("# HELP ejabberd_registered_users Number of registered users")
        lines.append("# TYPE ejabberd_registered_users gauge")
        lines.append(f"ejabberd_registered_users{{host=\"{XMPP_DOMAIN}\"}} {user_count}")

        # Ahenk ajanları
        agent_count = sum(1 for u in users if u.startswith("ahenk"))
        lines.append("# HELP ejabberd_ahenk_agents Number of registered ahenk agents")
        lines.append("# TYPE ejabberd_ahenk_agents gauge")
        lines.append(f"ejabberd_ahenk_agents{{host=\"{XMPP_DOMAIN}\"}} {agent_count}")
    else:
        lines.append("ejabberd_up 0")
        return "\n".join(lines) + "\n"

    # Bağlı kullanıcı sayısı
    connected = api_call("connected_users_number", {})
    if connected is not None:
        lines.append("# HELP ejabberd_connected_users Number of currently connected users")
        lines.append("# TYPE ejabberd_connected_users gauge")
        lines.append(f"ejabberd_connected_users {connected}")

    # Kayıtlı vhost'lar
    vhosts = api_call("registered_vhosts", {})
    if vhosts is not None:
        lines.append("# HELP ejabberd_vhosts Number of registered virtual hosts")
        lines.append("# TYPE ejabberd_vhosts gauge")
        lines.append(f"ejabberd_vhosts {len(vhosts)}")

    # Online rooms
    rooms = api_call("muc_online_rooms", {"service": f"conference.{XMPP_DOMAIN}"})
    if rooms is not None:
        lines.append("# HELP ejabberd_muc_online_rooms Number of online MUC rooms")
        lines.append("# TYPE ejabberd_muc_online_rooms gauge")
        lines.append(f"ejabberd_muc_online_rooms {len(rooms)}")

    # Uptime (saniye)
    stats = api_call("stats", {"name": "uptimeseconds"})
    if stats is not None:
        lines.append("# HELP ejabberd_uptime_seconds ejabberd uptime in seconds")
        lines.append("# TYPE ejabberd_uptime_seconds gauge")
        lines.append(f"ejabberd_uptime_seconds {stats}")

    # İşlem sayısı
    processes = api_call("stats", {"name": "processes"})
    if processes is not None:
        lines.append("# HELP ejabberd_processes Number of Erlang processes")
        lines.append("# TYPE ejabberd_processes gauge")
        lines.append(f"ejabberd_processes {processes}")

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
        # Suppress access logs
        pass


if __name__ == "__main__":
    print(f"🚀 ejabberd-exporter başlatılıyor — port {PORT}")
    print(f"   API: {EJABBERD_API}")
    print(f"   Domain: {XMPP_DOMAIN}")
    server = http.server.HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
