#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values


REQUIRED_FIELDS = (
    "LIDER_API_URL_EXTERNAL",
    "LIDER_UI_URL",
    "LIDER_USER",
    "LIDER_PASS",
    "LDAP_HOST",
    "LDAP_PORT",
    "LDAP_BASE_DN",
    "LDAP_ADMIN_USERNAME",
    "LDAP_ADMIN_PASSWORD",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "XMPP_DOMAIN",
    "GOLDEN_BASELINE_NAME",
    "BASELINE_SOURCE_LABEL",
)


def load_capture_env(env_file: Path) -> dict[str, str]:
    values = dotenv_values(env_file)
    return {key: value for key, value in values.items() if value is not None}


def missing_required_fields(values: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        if not str(values.get(field, "")).strip():
            missing.append(field)
    return missing


def _tcp_check(host: str, port: int, timeout_seconds: float = 3.0) -> dict[str, object]:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return {"ok": True, "host": host, "port": port}
    except OSError as exc:
        return {"ok": False, "host": host, "port": port, "error": str(exc)}


def build_connectivity_checks(values: dict[str, str]) -> list[dict[str, object]]:
    api = urlparse(values["LIDER_API_URL_EXTERNAL"])
    ui = urlparse(values["LIDER_UI_URL"])
    checks = [
        {
            "surface": "liderapi",
            **_tcp_check(api.hostname or "", api.port or (443 if api.scheme == "https" else 80)),
        },
        {
            "surface": "liderui",
            **_tcp_check(ui.hostname or "", ui.port or (443 if ui.scheme == "https" else 80)),
        },
        {
            "surface": "ldap",
            **_tcp_check(values["LDAP_HOST"], int(values["LDAP_PORT"])),
        },
        {
            "surface": "mariadb",
            **_tcp_check(values["MYSQL_HOST"], int(values["MYSQL_PORT"])),
        },
    ]
    return checks


def build_preflight_report(
    env_file: Path,
    *,
    check_connectivity: bool = True,
) -> dict[str, object]:
    values = load_capture_env(env_file)
    missing = missing_required_fields(values)
    checks = build_connectivity_checks(values) if check_connectivity and not missing else []
    failed_checks = [item for item in checks if not item.get("ok")]
    status = "pass"
    if missing or failed_checks:
        status = "fail"
    return {
        "envFile": str(env_file),
        "status": status,
        "missingFields": missing,
        "connectivityChecks": checks,
        "message": (
            "Stock baseline preflight passed."
            if status == "pass"
            else "Stock baseline preflight failed."
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate env/config and basic reachability before capturing a canonical stock golden baseline."
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        required=True,
        help="Path to the stock baseline env file.",
    )
    parser.add_argument(
        "--env-only",
        action="store_true",
        help="Validate required env fields only; skip TCP reachability checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_preflight_report(Path(args.env_file), check_connectivity=not args.env_only)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
