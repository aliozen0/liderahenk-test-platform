from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from platform_runtime.golden_baseline import validate_golden_baseline


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDAT\x08\x99c```\x00\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _build_complete_baseline(tmp_path: Path) -> Path:
    (tmp_path / "api-captures").mkdir()
    (tmp_path / "ui-evidence").mkdir()

    _write_json(
        tmp_path / "ldap-tree.json",
        {
            "schemaVersion": 1,
            "capturedAt": "2026-01-01T00:00:00+00:00",
            "entries": [],
        },
    )
    _write_json(
        tmp_path / "config.json",
        {
            "schemaVersion": 1,
            "capturedAt": "2026-01-01T00:00:00+00:00",
            "source": "stock-liderahenk-install",
            "fields": {
                "ldapRootDn": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "dc=liderahenk,dc=org"},
                "agentLdapBaseDn": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "ou=Ahenkler,dc=liderahenk,dc=org"},
                "userLdapBaseDn": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "ou=users,dc=liderahenk,dc=org"},
                "userGroupLdapBaseDn": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "ou=Groups,dc=liderahenk,dc=org"},
                "ahenkGroupLdapBaseDn": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "ou=Agent,ou=Groups,dc=liderahenk,dc=org"},
                "xmppServiceName": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "liderahenk.org"},
                "xmppResource": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1", "value": "LiderAPI"},
                "ldapPassword": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1"},
                "xmppPassword": {"present": True, "source": "c_config.liderConfigParams", "sha256": "1"},
            },
        },
    )
    for path in (
        "api-captures/dashboard.json",
        "api-captures/agent-list.json",
        "api-captures/computer-tree.json",
    ):
        _write_json(
            tmp_path / path,
            {
                "schemaVersion": 1,
                "capturedAt": "2026-01-01T00:00:00+00:00",
                "payload": {},
            },
        )
    for path in ("ui-evidence/dashboard.png", "ui-evidence/computer-management.png"):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(PNG_1X1)

    tracked_files = (
        "ldap-tree.json",
        "config.json",
        "api-captures/dashboard.json",
        "api-captures/agent-list.json",
        "api-captures/computer-tree.json",
        "ui-evidence/dashboard.png",
        "ui-evidence/computer-management.png",
    )
    manifest = {
        "schemaVersion": 1,
        "baselineName": "stock-liderahenk",
        "status": "capture-complete",
        "source": {"kind": "stock-liderahenk-install", "label": "test-stock"},
        "capturedAt": "2026-01-01T00:00:00+00:00",
        "captureContext": {
            "capturedByHost": "test-host",
            "envFile": None,
            "sourceLabel": "test-stock",
            "captureUiEvidence": True,
            "apiUrl": "http://stock-api:8082",
            "uiUrl": "http://stock-ui:3001",
            "ldap": {"host": "stock-ldap", "port": 1389, "baseDn": "dc=liderahenk,dc=org"},
            "mysql": {"host": "stock-mariadb", "port": 3306, "database": "liderahenk", "user": "lider"},
            "xmpp": {"domain": "liderahenk.org"},
        },
        "files": {},
    }
    _write_json(tmp_path / "manifest.json", manifest)
    manifest["files"] = {
        relative_path: {
            "path": relative_path,
            "size": (tmp_path / relative_path).stat().st_size,
            "sha256": _hash_file(tmp_path / relative_path),
        }
        for relative_path in tracked_files
    }
    _write_json(tmp_path / "manifest.json", manifest)
    return tmp_path


def test_validator_rejects_missing_required_files(tmp_path):
    report = validate_golden_baseline(tmp_path)
    assert report["valid"] is False
    assert any("missing required file" in item for item in report["errors"])


def test_validator_accepts_complete_baseline(tmp_path):
    _build_complete_baseline(tmp_path)
    report = validate_golden_baseline(tmp_path)
    assert report["valid"] is True, report["errors"]


def test_validator_rejects_manifest_hash_mismatch(tmp_path):
    _build_complete_baseline(tmp_path)
    (tmp_path / "ldap-tree.json").write_text(
        json.dumps({"schemaVersion": 1, "capturedAt": "2026-01-02T00:00:00+00:00", "entries": []}, indent=2),
        encoding="utf-8",
    )
    report = validate_golden_baseline(tmp_path)
    assert report["valid"] is False
    assert "manifest hash mismatch: ldap-tree.json" in report["errors"]


def test_validator_handles_invalid_manifest_json(tmp_path):
    (tmp_path / "api-captures").mkdir()
    (tmp_path / "ui-evidence").mkdir()
    (tmp_path / "manifest.json").write_text("{invalid", encoding="utf-8")
    report = validate_golden_baseline(tmp_path)
    assert report["valid"] is False
    assert any("manifest.json: invalid json" in item for item in report["errors"])
