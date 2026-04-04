from __future__ import annotations

import json
import os
import socket
import sys
import time
from typing import Any
from urllib import parse
from urllib import error, request


AUTH_ENDPOINT = "/api/auth/signin"
PROTECTED_PROBE_ENDPOINT = "/api/dashboard/info"


class GateTimeoutError(RuntimeError):
    pass


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _replace_base_url_host(base_url: str, host: str) -> str:
    parsed = parse.urlparse(base_url)
    if not parsed.scheme:
        return base_url
    port = f":{parsed.port}" if parsed.port else ""
    return parse.urlunparse(
        parsed._replace(
            netloc=f"{host}{port}",
        )
    )


def _docker_get(path: str) -> list[dict[str, Any]]:
    sock_path = "/var/run/docker.sock"
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(5)
    client.connect(sock_path)
    try:
        request_text = (
            f"GET {path} HTTP/1.0\r\n"
            "Host: localhost\r\n"
            "\r\n"
        )
        client.sendall(request_text.encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        client.close()

    response = b"".join(chunks)
    if b"\r\n\r\n" not in response:
        raise RuntimeError("docker socket response did not contain headers")
    header_blob, body_blob = response.split(b"\r\n\r\n", 1)
    status_line = header_blob.splitlines()[0].decode("utf-8", errors="ignore")
    if "200" not in status_line:
        raise RuntimeError(f"docker socket request failed: {status_line}")
    payload = json.loads(body_blob.decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("docker socket returned a non-list payload")
    return payload


def _discover_compose_service_ip(service_name: str) -> str | None:
    sock_path = "/var/run/docker.sock"
    if not os.path.exists(sock_path):
        return None

    labels = [
        f"com.docker.compose.service={service_name}",
        "com.docker.compose.oneoff=False",
    ]
    project_name = os.environ.get("COMPOSE_PROJECT_NAME", "").strip()
    if project_name:
        labels.append(f"com.docker.compose.project={project_name}")

    filters = parse.quote(json.dumps({"label": labels}))
    containers = _docker_get(f"/containers/json?all=0&filters={filters}")
    preferred_network_suffix = os.environ.get(
        "LIDERAPI_GATE_PREFERRED_NETWORK_SUFFIX",
        "_liderahenk_agents",
    ).strip()

    for container in containers:
        networks = container.get("NetworkSettings", {}).get("Networks", {}) or {}
        preferred_ip = None
        fallback_ip = None
        for name, network in networks.items():
            ip_address = str(network.get("IPAddress") or "").strip()
            if not ip_address:
                continue
            fallback_ip = fallback_ip or ip_address
            if preferred_network_suffix and name.endswith(preferred_network_suffix):
                preferred_ip = ip_address
                break
        if preferred_ip:
            return preferred_ip
        if fallback_ip:
            return fallback_ip
    return None


def resolve_base_url(base_url: str) -> str:
    normalized = _normalize_base_url(base_url)
    parsed = parse.urlparse(normalized)
    hostname = parsed.hostname or ""
    if not hostname or hostname in {"localhost", "127.0.0.1"}:
        return normalized

    service_name = os.environ.get("LIDERAPI_GATE_SERVICE_NAME", hostname).strip() or hostname
    discovered_ip = _discover_compose_service_ip(service_name)
    if not discovered_ip:
        return normalized
    return _replace_base_url_host(normalized, discovered_ip)


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: int,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    req = request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                data = {"payload": data}
            return response.status, data
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {"rawBody": raw}
        if not isinstance(data, dict):
            data = {"payload": data}
        return exc.code, data


def authenticate(*, base_url: str, username: str, password: str, timeout: int) -> str:
    status_code, payload = _post_json(
        f"{_normalize_base_url(base_url)}{AUTH_ENDPOINT}",
        {"username": username, "password": password},
        timeout=timeout,
    )
    if status_code != 200:
        raise RuntimeError(f"signin returned HTTP {status_code}")

    token = payload.get("token")
    if not isinstance(token, str) or not token.strip():
        raise RuntimeError("signin did not return a usable token")
    return token


def probe_protected_endpoint(*, base_url: str, token: str, timeout: int) -> None:
    status_code, _payload = _post_json(
        f"{_normalize_base_url(base_url)}{PROTECTED_PROBE_ENDPOINT}",
        {},
        timeout=timeout,
        headers={"Authorization": f"Bearer {token}"},
    )
    if status_code != 200:
        raise RuntimeError(f"protected probe returned HTTP {status_code}")


def wait_for_liderapi_gate(
    *,
    base_url: str,
    username: str,
    password: str,
    timeout_seconds: int,
    interval_seconds: int,
    stable_success_count: int = 1,
) -> dict[str, Any]:
    if stable_success_count < 1:
        raise ValueError("stable_success_count must be at least 1")

    resolved_base_url = resolve_base_url(base_url)
    deadline = time.monotonic() + timeout_seconds
    consecutive_successes = 0
    attempt = 0
    last_error: str | None = None

    while time.monotonic() <= deadline:
        attempt += 1
        try:
            token = authenticate(
                base_url=resolved_base_url,
                username=username,
                password=password,
                timeout=max(1, interval_seconds),
            )
            probe_protected_endpoint(
                base_url=resolved_base_url,
                token=token,
                timeout=max(1, interval_seconds),
            )
            consecutive_successes += 1
            print(
                f"[liderapi-gate] attempt={attempt} auth+probe success "
                f"({consecutive_successes}/{stable_success_count})",
                flush=True,
            )
            if consecutive_successes >= stable_success_count:
                return {
                    "status": "ready",
                    "attempts": attempt,
                    "baseUrl": resolved_base_url,
                    "stableSuccessCount": stable_success_count,
                }
        except Exception as exc:
            last_error = str(exc)
            consecutive_successes = 0
            print(
                f"[liderapi-gate] attempt={attempt} waiting: {last_error}",
                flush=True,
            )
        time.sleep(interval_seconds)

    raise GateTimeoutError(
        "liderapi auth gate timed out after "
        f"{attempt} attempts at {_normalize_base_url(base_url)}; last error: {last_error or 'unknown'}"
    )


def _read_env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def main() -> int:
    base_url = os.environ.get("LIDER_API_URL", "http://liderapi:8080").strip() or "http://liderapi:8080"
    username = os.environ.get("LIDER_USER", "lider-admin").strip() or "lider-admin"
    password = os.environ.get("LIDER_PASS", "secret")
    timeout_seconds = _read_env_int("LIDERAPI_GATE_TIMEOUT_SECONDS", 180)
    interval_seconds = _read_env_int("LIDERAPI_GATE_INTERVAL_SECONDS", 5)
    stable_success_count = _read_env_int("LIDERAPI_GATE_STABLE_SUCCESS_COUNT", 2)

    try:
        resolved_base_url = resolve_base_url(base_url)
        if resolved_base_url != _normalize_base_url(base_url):
            print(
                "[liderapi-gate] resolved "
                f"{_normalize_base_url(base_url)} -> {resolved_base_url} via docker socket",
                flush=True,
            )
        result = wait_for_liderapi_gate(
            base_url=resolved_base_url,
            username=username,
            password=password,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            stable_success_count=stable_success_count,
        )
    except Exception as exc:
        print(f"[liderapi-gate] ERROR: {exc}", file=sys.stderr, flush=True)
        return 1

    print(f"[liderapi-gate] ready: {json.dumps(result, ensure_ascii=False)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
