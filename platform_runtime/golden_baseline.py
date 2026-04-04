from __future__ import annotations

import argparse
import json
import os
import socket
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from adapters import build_platform_bundle
from platform_runtime.registration import RegistrationCollector, flatten_tree_agent_ids, normalize_agent_id
from platform_runtime.runtime_db import RuntimeDbAdapter


BASELINE_CONTRACT_PATH = Path("platform/contracts/baseline-registry.yaml")
DEFAULT_BASELINE_DIR = Path("platform/baselines/golden-install")
STOCK_CAPTURE_CONFIRMATION_FLAG = "--confirm-stock-source"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_contract() -> dict[str, Any]:
    with BASELINE_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _required_relative_paths(contract: dict[str, Any]) -> list[str]:
    required = [
        contract["required_files"]["manifest"],
        contract["required_files"]["ldap_tree"],
        contract["required_files"]["config"],
    ]
    required.extend(contract["required_files"]["api_captures"])
    required.extend(contract["required_files"]["ui_evidence"])
    return required


def _tracked_manifest_paths(contract: dict[str, Any]) -> list[str]:
    # The manifest cannot reliably fingerprint itself without recursion.
    return _required_relative_paths(contract)[1:]


def _hash_text(value: Any) -> str:
    if value is None:
        value = ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return sha256(text.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def apply_capture_environment(env_file: Path | None = None) -> dict[str, str]:
    if env_file is None:
        return {}
    if not env_file.exists():
        raise FileNotFoundError(f"capture env file not found: {env_file}")
    loaded = {}
    values = dotenv_values(env_file)
    for key, value in values.items():
        if value is None:
            continue
        os.environ[key] = value
        loaded[key] = value
    return loaded


def _capture_runtime_config(runtime_db: RuntimeDbAdapter, contract: dict[str, Any]) -> dict[str, Any]:
    payload = runtime_db.get_config_json()
    fields: dict[str, Any] = {}
    secret_fields = set(contract.get("secret_runtime_fields", []))
    for field_name in contract.get("critical_runtime_fields", []):
        value = payload.get(field_name)
        entry = {
            "present": value is not None,
            "source": "c_config.liderConfigParams",
            "sha256": _hash_text(value),
        }
        if field_name not in secret_fields and value is not None:
            entry["value"] = value
        fields[field_name] = entry
    return {
        "schemaVersion": 1,
        "capturedAt": _utc_now(),
        "source": contract["source_kind"],
        "fields": fields,
    }


def _normalize_ldap_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for entry in entries:
        attrs = entry.get("attrs", {})
        normalized_attrs = {}
        for key, value in attrs.items():
            if isinstance(value, (list, tuple)):
                normalized_attrs[key] = [str(item) for item in value]
            else:
                normalized_attrs[key] = str(value)
        normalized.append(
            {
                "dn": entry.get("dn"),
                "attrs": normalized_attrs,
            }
        )
    return sorted(normalized, key=lambda item: item["dn"])


def _collect_live_baseline_payload(bundle, runtime_db: RuntimeDbAdapter, contract: dict[str, Any]) -> dict[str, Any]:
    dashboard = bundle.inventory.get_dashboard_info() or {}
    agent_list = bundle.inventory.get_agent_list()
    computer_tree = bundle.inventory.get_computer_tree()
    ldap_tree = bundle.directory.search_entries(
        os.environ.get("LDAP_BASE_DN", "dc=liderahenk,dc=org"),
        "(objectClass=*)",
    )
    return {
        "ldap-tree.json": {
            "schemaVersion": 1,
            "capturedAt": _utc_now(),
            "entries": _normalize_ldap_entries(ldap_tree),
        },
        "config.json": _capture_runtime_config(runtime_db, contract),
        "api-captures/dashboard.json": {
            "schemaVersion": 1,
            "capturedAt": _utc_now(),
            "payload": dashboard,
        },
        "api-captures/agent-list.json": {
            "schemaVersion": 1,
            "capturedAt": _utc_now(),
            "payload": agent_list,
            "agentIds": sorted(
                dict.fromkeys(
                    normalized
                    for agent in agent_list
                    for normalized in [
                        normalize_agent_id(agent.get("jid")),
                        normalize_agent_id(agent.get("uid")),
                        normalize_agent_id(agent.get("hostname")),
                        normalize_agent_id(agent.get("distinguishedName")),
                    ]
                    if normalized
                )
            ),
        },
        "api-captures/computer-tree.json": {
            "schemaVersion": 1,
            "capturedAt": _utc_now(),
            "payload": computer_tree,
            "agentIds": flatten_tree_agent_ids(computer_tree),
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _collect_file_metadata(root: Path, relative_paths: list[str]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for relative_path in relative_paths:
        target = root / relative_path
        metadata[relative_path] = {
            "path": relative_path,
            "size": target.stat().st_size,
            "sha256": _hash_file(target),
        }
    return metadata


def _build_capture_context(
    *,
    env_file: Path | None,
    source_label: str,
    capture_ui: bool,
) -> dict[str, Any]:
    return {
        "capturedByHost": socket.gethostname(),
        "envFile": str(env_file) if env_file else None,
        "sourceLabel": source_label,
        "captureUiEvidence": capture_ui,
        "apiUrl": os.environ.get("LIDER_API_URL_EXTERNAL", os.environ.get("LIDER_API_URL", "http://localhost:8082")),
        "uiUrl": os.environ.get("LIDER_UI_URL", "http://localhost:3001"),
        "ldap": {
            "host": os.environ.get("LDAP_HOST", "localhost"),
            "port": int(os.environ.get("LDAP_PORT", "1389")),
            "baseDn": os.environ.get("LDAP_BASE_DN", "dc=liderahenk,dc=org"),
        },
        "mysql": {
            "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "port": int(os.environ.get("MYSQL_PORT", "3306")),
            "database": os.environ.get("MYSQL_DATABASE", "liderahenk"),
            "user": os.environ.get("MYSQL_USER", "lider"),
        },
        "xmpp": {
            "domain": os.environ.get("XMPP_DOMAIN", "liderahenk.org"),
        },
    }


def _capture_ui_evidence(root: Path) -> None:
    from playwright.sync_api import sync_playwright

    from tests.e2e.pages.computer_management_page import ComputerManagementPage
    from tests.e2e.pages.login_page import LoginPage

    ui_dir = root / "ui-evidence"
    ui_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1440, "height": 900},
        )
        page = context.new_page()
        login_page = LoginPage(page)
        dashboard_page = login_page.login_expect_success()
        dashboard_page.wait_for_load()
        page.screenshot(path=str(ui_dir / "dashboard.png"), full_page=True)
        computer_page = ComputerManagementPage(page)
        computer_page.load()
        page.screenshot(path=str(ui_dir / "computer-management.png"), full_page=True)
        context.close()
        browser.close()


def capture_golden_baseline(
    root: Path | None = None,
    *,
    source_label: str | None = None,
    env_file: Path | None = None,
    force: bool = False,
    confirm_stock_source: bool = False,
) -> dict[str, Any]:
    if not confirm_stock_source:
        raise RuntimeError(
            "Refusing to capture canonical golden baseline without explicit stock-source confirmation. "
            f"Re-run with {STOCK_CAPTURE_CONFIRMATION_FLAG} only against a verified stock LiderAhenk installation."
        )
    apply_capture_environment(env_file)
    contract = _read_contract()
    baseline_root = root or DEFAULT_BASELINE_DIR
    baseline_root.mkdir(parents=True, exist_ok=True)
    manifest_path = baseline_root / contract["required_files"]["manifest"]
    if manifest_path.exists() and not force:
        try:
            existing_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            existing_manifest = {}
        if existing_manifest.get("status") == "capture-complete":
            raise RuntimeError(
                f"Refusing to overwrite capture-complete baseline at {baseline_root}. "
                "Use --force after verifying the target is a real stock installation."
            )
    bundle = build_platform_bundle()
    runtime_db = RuntimeDbAdapter.from_env()
    payloads = _collect_live_baseline_payload(bundle, runtime_db, contract)
    for relative_path, payload in payloads.items():
        _write_json(baseline_root / relative_path, payload)
    _capture_ui_evidence(baseline_root)
    source = source_label or os.environ.get("BASELINE_SOURCE_LABEL", "stock-liderahenk-install")
    capture_context = _build_capture_context(
        env_file=env_file,
        source_label=source,
        capture_ui=True,
    )
    file_metadata = _collect_file_metadata(baseline_root, _tracked_manifest_paths(contract))
    manifest = _build_manifest(
        contract,
        baseline_name=os.environ.get(contract["baseline_name_env"], "stock-liderahenk"),
        source_label=source,
        capture_context=capture_context,
        files=file_metadata,
    )
    _write_json(baseline_root / contract["required_files"]["manifest"], manifest)
    return validate_golden_baseline(baseline_root)


def validate_golden_baseline(root: Path | None = None) -> dict[str, Any]:
    contract = _read_contract()
    baseline_root = root or DEFAULT_BASELINE_DIR
    errors: list[str] = []
    missing_files: list[str] = []
    manifest_status = None
    for relative_path in _required_relative_paths(contract):
        target = baseline_root / relative_path
        if not target.exists():
            missing_files.append(relative_path)
            continue
        if target.suffix == ".json":
            try:
                json.loads(target.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"{relative_path}: invalid json ({exc})")
        elif target.suffix == ".png" and target.stat().st_size <= 0:
            errors.append(f"{relative_path}: empty png evidence")
    if missing_files:
        errors.extend([f"missing required file: {item}" for item in missing_files])

    manifest_path = baseline_root / contract["required_files"]["manifest"]
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"{contract['required_files']['manifest']}: invalid json ({exc})")
            manifest = None
        if isinstance(manifest, dict):
            for field_name in contract["manifest_required_fields"]:
                if field_name not in manifest:
                    errors.append(f"manifest missing field: {field_name}")
            manifest_status = manifest.get("status")
            if manifest_status == "capture-pending":
                errors.append("canonical golden baseline not captured yet (manifest status: capture-pending)")
            elif manifest_status != "capture-complete":
                errors.append("manifest status must be capture-complete")
            capture_context = manifest.get("captureContext")
            if not isinstance(capture_context, dict):
                errors.append("manifest captureContext must be an object")
            files_metadata = manifest.get("files", {})
            if not isinstance(files_metadata, dict):
                errors.append("manifest files must be an object")
                files_metadata = {}
            for relative_path in _tracked_manifest_paths(contract):
                metadata = files_metadata.get(relative_path)
                if not isinstance(metadata, dict):
                    errors.append(f"manifest file metadata missing: {relative_path}")
                    continue
                if metadata.get("path") != relative_path:
                    errors.append(f"manifest path mismatch: {relative_path}")
                target = baseline_root / relative_path
                if not target.exists():
                    continue
                actual_sha = _hash_file(target)
                actual_size = target.stat().st_size
                if metadata.get("sha256") != actual_sha:
                    errors.append(f"manifest hash mismatch: {relative_path}")
                if metadata.get("size") != actual_size:
                    errors.append(f"manifest size mismatch: {relative_path}")

    config_path = baseline_root / contract["required_files"]["config"]
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        fields = config.get("fields", {})
        for field_name in contract["critical_runtime_fields"]:
            payload = fields.get(field_name)
            if not isinstance(payload, dict):
                errors.append(f"config field missing: {field_name}")
                continue
            for required_key in ("present", "source", "sha256"):
                if required_key not in payload:
                    errors.append(f"config field {field_name} missing key: {required_key}")
        for secret_field in contract.get("secret_runtime_fields", []):
            payload = fields.get(secret_field, {})
            if "value" in payload:
                errors.append(f"secret field exposed in plaintext: {secret_field}")

    status = "pass"
    if errors:
        status = "pending-capture" if manifest_status == "capture-pending" else "fail"
    report = {
        "schemaVersion": 1,
        "baselineRoot": str(baseline_root),
        "status": status,
        "manifestStatus": manifest_status,
        "valid": not errors,
        "errors": errors,
        "checkedAt": _utc_now(),
    }
    return report


def load_golden_baseline(root: Path | None = None) -> dict[str, Any]:
    baseline_root = root or DEFAULT_BASELINE_DIR
    payload = {}
    for relative_path in _required_relative_paths(_read_contract()):
        target = baseline_root / relative_path
        if target.suffix == ".json" and target.exists():
            payload[relative_path] = json.loads(target.read_text(encoding="utf-8"))
        else:
            payload[relative_path] = str(target)
    return payload


def _list_diff_details(baseline_values: list[Any], current_values: list[Any]) -> dict[str, Any]:
    baseline_unique = list(dict.fromkeys(baseline_values))
    current_unique = list(dict.fromkeys(current_values))
    baseline_set = set(baseline_unique)
    current_set = set(current_unique)
    return {
        "baselineCount": len(baseline_unique),
        "currentCount": len(current_unique),
        "missingFromCurrent": sorted(baseline_set - current_set),
        "extraInCurrent": sorted(current_set - baseline_set),
    }


def _append_diff(
    diffs: list[dict[str, Any]],
    *,
    code: str,
    severity: str,
    surface: str,
    message: str,
    baseline_value: Any,
    current_value: Any,
    details: dict[str, Any] | None = None,
) -> None:
    if baseline_value == current_value:
        return
    payload = {
        "code": code,
        "severity": severity,
        "surface": surface,
        "message": message,
        "baseline": baseline_value,
        "current": current_value,
    }
    if details:
        payload["details"] = details
    diffs.append(payload)


def _summarize_diffs(diffs: list[dict[str, Any]], *, severity_order: list[str], blocking_severity: str) -> dict[str, Any]:
    counts = {severity: 0 for severity in severity_order}
    for item in diffs:
        severity = item.get("severity")
        if severity not in counts:
            counts[severity] = 0
        counts[severity] += 1
    highest_severity = None
    for severity in severity_order:
        if counts.get(severity, 0) > 0:
            highest_severity = severity
            break
    blocking_diff_count = counts.get(blocking_severity, 0)
    return {
        "totalDiffs": len(diffs),
        "counts": counts,
        "blockingSeverity": blocking_severity,
        "blockingDiffCount": blocking_diff_count,
        "highestSeverity": highest_severity,
        "hasWarnings": counts.get("warn", 0) > 0,
        "hasInfo": counts.get("info", 0) > 0,
    }


def _build_baseline_diff_payload(
    *,
    baseline_root: Path,
    baseline: dict[str, Any],
    live: dict[str, Any],
    live_verdict: dict[str, Any],
    contract: dict[str, Any],
    verdict_source: str,
) -> dict[str, Any]:
    policy = contract.get("diff_policy", {})
    severity_order = policy.get("severity_order", ["error", "warn", "info"])
    blocking_severity = policy.get("blocking_severity", "error")
    diffs: list[dict[str, Any]] = []

    if verdict_source != "artifact":
        if verdict_source == "artifact-invalid":
            message = "Registration verdict artifact was invalid; baseline diff used a live evaluation fallback."
        elif verdict_source == "artifact-missing":
            message = "Registration verdict artifact was missing; baseline diff used a live evaluation fallback."
        else:
            message = "Registration verdict artifact was unavailable; baseline diff used a live evaluation fallback."
        diffs.append(
            {
                "code": "registration_verdict_artifact_missing",
                "severity": "warn",
                "surface": "registration",
                "message": message,
                "baseline": "artifact",
                "current": verdict_source,
            }
        )

    baseline_ldap_dns = [entry["dn"] for entry in baseline["ldap-tree.json"].get("entries", [])]
    live_ldap_dns = [entry["dn"] for entry in live["ldap-tree.json"].get("entries", [])]
    _append_diff(
        diffs,
        code="ldap_entry_dns",
        severity="error",
        surface="ldap",
        message="LDAP distinguished names differ from the golden baseline.",
        baseline_value=baseline_ldap_dns,
        current_value=live_ldap_dns,
        details=_list_diff_details(baseline_ldap_dns, live_ldap_dns),
    )

    for field_name, baseline_field in baseline["config.json"].get("fields", {}).items():
        current_field = live["config.json"]["fields"].get(field_name)
        _append_diff(
            diffs,
            code=f"config_field:{field_name}",
            severity="error",
            surface="config",
            message=f"Runtime config field {field_name} differs from the golden baseline.",
            baseline_value=baseline_field,
            current_value=current_field,
        )

    _append_diff(
        diffs,
        code="dashboard_total",
        severity="error",
        surface="dashboard",
        message="Dashboard total computer count differs from the golden baseline.",
        baseline_value=baseline["api-captures/dashboard.json"]["payload"].get("totalComputerNumber"),
        current_value=live["api-captures/dashboard.json"]["payload"].get("totalComputerNumber"),
    )
    _append_diff(
        diffs,
        code="dashboard_online",
        severity="error",
        surface="dashboard",
        message="Dashboard online computer count differs from the golden baseline.",
        baseline_value=baseline["api-captures/dashboard.json"]["payload"].get("totalOnlineComputerNumber"),
        current_value=live["api-captures/dashboard.json"]["payload"].get("totalOnlineComputerNumber"),
    )
    baseline_agent_ids = baseline["api-captures/agent-list.json"].get("agentIds", [])
    live_agent_ids = live["api-captures/agent-list.json"].get("agentIds", [])
    _append_diff(
        diffs,
        code="agent_list_identities",
        severity="error",
        surface="agent-list",
        message="Agent inventory identities differ from the golden baseline.",
        baseline_value=baseline_agent_ids,
        current_value=live_agent_ids,
        details=_list_diff_details(baseline_agent_ids, live_agent_ids),
    )
    baseline_tree_ids = baseline["api-captures/computer-tree.json"].get("agentIds", [])
    live_tree_ids = live["api-captures/computer-tree.json"].get("agentIds", [])
    _append_diff(
        diffs,
        code="computer_tree_identities",
        severity="error",
        surface="computer-tree",
        message="Computer tree identities differ from the golden baseline.",
        baseline_value=baseline_tree_ids,
        current_value=live_tree_ids,
        details=_list_diff_details(baseline_tree_ids, live_tree_ids),
    )
    _append_diff(
        diffs,
        code="registration_verdict_status",
        severity="error",
        surface="registration",
        message="Registration verdict is not pass for the current run.",
        baseline_value="pass",
        current_value=live_verdict.get("status"),
    )

    summary = _summarize_diffs(diffs, severity_order=severity_order, blocking_severity=blocking_severity)
    status = "fail" if summary["blockingDiffCount"] > 0 else "pass"
    manifest = baseline.get("manifest.json", {})
    return {
        "schemaVersion": 1,
        "status": status,
        "baselineRoot": str(baseline_root),
        "capturedAt": _utc_now(),
        "policy": {
            "blockingSeverity": blocking_severity,
            "severityOrder": severity_order,
        },
        "baseline": {
            "name": manifest.get("baselineName"),
            "capturedAt": manifest.get("capturedAt"),
            "source": manifest.get("source"),
        },
        "comparison": {
            "verdictSource": verdict_source,
            "runtimeProfile": live_verdict.get("runtimeProfile"),
            "expectedAgents": live_verdict.get("expectedAgents"),
        },
        "summary": summary,
        "diffs": diffs,
        "verdict": live_verdict,
    }


def compare_with_golden_baseline(
    *,
    baseline_root: Path | None = None,
    verdict_path: Path | None = None,
) -> dict[str, Any]:
    root = baseline_root or DEFAULT_BASELINE_DIR
    baseline = load_golden_baseline(root)
    contract = _read_contract()
    bundle = build_platform_bundle()
    runtime_db = RuntimeDbAdapter.from_env()
    live = _collect_live_baseline_payload(bundle, runtime_db, contract)
    collector = RegistrationCollector.from_env()
    snapshot = collector.collect_snapshot()
    live_verdict = collector.evaluate_snapshot(snapshot)
    verdict_source = "live-evaluated"
    if verdict_path:
        if verdict_path.exists():
            try:
                live_verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
                verdict_source = "artifact"
            except Exception:
                verdict_source = "artifact-invalid"
        else:
            verdict_source = "artifact-missing"
    return _build_baseline_diff_payload(
        baseline_root=root,
        baseline=baseline,
        live=live,
        live_verdict=live_verdict,
        contract=contract,
        verdict_source=verdict_source,
    )


def write_baseline_diff(
    diff_payload: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    artifacts_dir = output_dir or Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / "baseline-diff.json"
    markdown_path = artifacts_dir / "baseline-diff.md"
    json_path.write_text(json.dumps(diff_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Baseline Diff",
        "",
        f"- Status: `{diff_payload['status']}`",
        f"- Captured at: `{diff_payload['capturedAt']}`",
        f"- Blocking severity: `{diff_payload['policy']['blockingSeverity']}`",
        f"- Verdict source: `{diff_payload['comparison']['verdictSource']}`",
        f"- Total diffs: `{diff_payload['summary']['totalDiffs']}`",
        f"- Errors: `{diff_payload['summary']['counts'].get('error', 0)}`",
        f"- Warnings: `{diff_payload['summary']['counts'].get('warn', 0)}`",
        f"- Info: `{diff_payload['summary']['counts'].get('info', 0)}`",
        "",
    ]
    baseline_meta = diff_payload.get("baseline", {})
    if baseline_meta:
        lines.extend(
            [
                "## Baseline",
                "",
                f"- Name: `{baseline_meta.get('name')}`",
                f"- Captured at: `{baseline_meta.get('capturedAt')}`",
                f"- Source: `{json.dumps(baseline_meta.get('source'), ensure_ascii=False)}`",
                "",
            ]
        )
    if not diff_payload["diffs"]:
        lines.append("- No differences detected.")
    else:
        for severity in diff_payload["policy"]["severityOrder"]:
            severity_items = [item for item in diff_payload["diffs"] if item["severity"] == severity]
            if not severity_items:
                continue
            lines.extend([f"## {severity.title()} Diffs", ""])
            for item in severity_items:
                lines.append(
                    f"- `{item['code']}` [{item['surface']}]: {item['message']} "
                    f"(baseline={json.dumps(item['baseline'], ensure_ascii=False)}, "
                    f"current={json.dumps(item['current'], ensure_ascii=False)})"
                )
                if item.get("details"):
                    lines.append(f"- details: `{json.dumps(item['details'], ensure_ascii=False, sort_keys=True)}`")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def _build_manifest(
    contract: dict[str, Any],
    baseline_name: str,
    source_label: str,
    *,
    capture_context: dict[str, Any],
    files: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "baselineName": baseline_name,
        "status": "capture-complete",
        "source": {
            "kind": contract["source_kind"],
            "label": source_label,
        },
        "capturedAt": _utc_now(),
        "captureContext": capture_context,
        "files": files,
    }


def parse_capture_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture canonical golden baseline artifacts from a stock LiderAhenk installation.")
    parser.add_argument(
        "baseline_root",
        nargs="?",
        default=str(DEFAULT_BASELINE_DIR),
        help="Target baseline directory. Defaults to platform/baselines/golden-install",
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        default=None,
        help="Path to a stock installation env file used only for capture.",
    )
    parser.add_argument(
        "--source-label",
        dest="source_label",
        default=None,
        help="Human-readable source label written into manifest metadata.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an existing capture-complete baseline directory.",
    )
    parser.add_argument(
        "--confirm-stock-source",
        dest="confirm_stock_source",
        action="store_true",
        help="Acknowledge that the capture source is a verified stock LiderAhenk installation, not the patched dev runtime.",
    )
    return parser.parse_args(argv)
