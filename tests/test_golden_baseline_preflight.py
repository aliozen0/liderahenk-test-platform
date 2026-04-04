from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "platform" / "scripts" / "golden_baseline_preflight.py"
SPEC = importlib.util.spec_from_file_location("golden_baseline_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
build_preflight_report = MODULE.build_preflight_report


def _write_env(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def test_preflight_reports_missing_fields(tmp_path):
    env_file = _write_env(
        tmp_path / "stock.env",
        """
        LIDER_API_URL_EXTERNAL=http://api.example:8082
        LIDER_UI_URL=http://ui.example:3001
        """,
    )
    report = build_preflight_report(env_file, check_connectivity=False)
    assert report["status"] == "fail"
    assert "LIDER_USER" in report["missingFields"]
    assert report["connectivityChecks"] == []


def test_preflight_passes_when_required_fields_exist_and_connectivity_is_skipped(tmp_path):
    env_file = _write_env(
        tmp_path / "stock.env",
        """
        LIDER_API_URL_EXTERNAL=http://api.example:8082
        LIDER_UI_URL=http://ui.example:3001
        LIDER_USER=lider-admin
        LIDER_PASS=secret
        LDAP_HOST=ldap.example
        LDAP_PORT=1389
        LDAP_BASE_DN=dc=liderahenk,dc=org
        LDAP_ADMIN_USERNAME=admin
        LDAP_ADMIN_PASSWORD=secret
        MYSQL_HOST=db.example
        MYSQL_PORT=3306
        MYSQL_DATABASE=liderahenk
        MYSQL_USER=lider
        MYSQL_PASSWORD=secret
        XMPP_DOMAIN=liderahenk.org
        GOLDEN_BASELINE_NAME=stock-liderahenk
        BASELINE_SOURCE_LABEL=stock-install-2026-04-04
        """,
    )
    report = build_preflight_report(env_file, check_connectivity=False)
    assert report["status"] == "pass"
    assert report["missingFields"] == []
    assert report["connectivityChecks"] == []
