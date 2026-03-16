from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REGISTRATION_EVIDENCE_CONTRACT_PATH = Path("platform/contracts/registration-evidence.yaml")
DEFAULT_PLATFORM_ARTIFACTS_DIR = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_contract() -> dict[str, Any]:
    with REGISTRATION_EVIDENCE_CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _load_json(path: Path, *, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}: invalid json ({exc})")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label}: expected object payload")
        return None
    return payload


def _load_events(path: Path, *, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        errors.append("registration-events.jsonl: no events captured")
        return events
    for index, line in enumerate(lines, start=1):
        try:
            payload = json.loads(line)
        except Exception as exc:
            errors.append(f"registration-events.jsonl:{index}: invalid json ({exc})")
            continue
        if not isinstance(payload, dict):
            errors.append(f"registration-events.jsonl:{index}: expected object payload")
            continue
        events.append(payload)
    return events


def _require_fields(
    payload: dict[str, Any] | None,
    required_fields: list[str],
    *,
    label: str,
    errors: list[str],
) -> None:
    if payload is None:
        return
    for field_name in required_fields:
        if field_name not in payload:
            errors.append(f"{label}: missing field {field_name}")


def _validate_per_agent_states(
    per_agent: list[dict[str, Any]],
    *,
    states: list[str],
    errors: list[str],
) -> None:
    allowed_states = set(states)
    for index, entry in enumerate(per_agent, start=1):
        label = f"registration-verdict.json: perAgent[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: expected object payload")
            continue
        if "agentId" not in entry:
            errors.append(f"{label}: missing field agentId")
        state_map = entry.get("states")
        if not isinstance(state_map, dict):
            errors.append(f"{label}: states must be an object")
            continue
        missing_states = [name for name in states if name not in state_map]
        if missing_states:
            errors.append(f"{label}: missing states {missing_states}")
        unexpected_states = sorted(set(state_map.keys()) - allowed_states)
        if unexpected_states:
            errors.append(f"{label}: unexpected states {unexpected_states}")
        for state_name, state_value in state_map.items():
            if not isinstance(state_value, bool):
                errors.append(f"{label}: state {state_name} must be boolean")
        highest_state = entry.get("highestState")
        if highest_state != "missing" and highest_state not in allowed_states:
            errors.append(f"{label}: highestState must be one of {states} or 'missing'")
        if highest_state in allowed_states and state_map.get(highest_state) is not True:
            errors.append(f"{label}: highestState {highest_state} is not marked true")


def validate_registration_evidence(root: Path | None = None) -> dict[str, Any]:
    artifacts_root = root or DEFAULT_PLATFORM_ARTIFACTS_DIR
    contract = _read_contract()
    errors: list[str] = []
    required_artifacts = contract["required_artifacts"]

    for relative_path in required_artifacts:
        if not (artifacts_root / relative_path).exists():
            errors.append(f"missing evidence artifact: {relative_path}")

    run_manifest = _load_json(artifacts_root / "run-manifest.json", label="run-manifest.json", errors=errors)
    verdict = _load_json(artifacts_root / "registration-verdict.json", label="registration-verdict.json", errors=errors)
    failure_summary = _load_json(artifacts_root / "failure-summary.json", label="failure-summary.json", errors=errors)
    events = _load_events(artifacts_root / "registration-events.jsonl", errors=errors)

    _require_fields(
        run_manifest,
        contract["run_manifest_required_fields"],
        label="run-manifest.json",
        errors=errors,
    )
    _require_fields(
        verdict,
        contract["registration_verdict_required_fields"],
        label="registration-verdict.json",
        errors=errors,
    )
    _require_fields(
        failure_summary,
        contract["failure_summary_required_fields"],
        label="failure-summary.json",
        errors=errors,
    )

    if run_manifest is not None:
        backoff = run_manifest.get("backoff")
        if not isinstance(backoff, dict):
            errors.append("run-manifest.json: backoff must be an object")
        else:
            min_seconds = backoff.get("minSeconds")
            max_seconds = backoff.get("maxSeconds")
            if not isinstance(min_seconds, int) or min_seconds < 0:
                errors.append("run-manifest.json: backoff.minSeconds must be a non-negative integer")
            if not isinstance(max_seconds, int) or max_seconds < 0:
                errors.append("run-manifest.json: backoff.maxSeconds must be a non-negative integer")
            if isinstance(min_seconds, int) and isinstance(max_seconds, int) and min_seconds > max_seconds:
                errors.append("run-manifest.json: backoff.minSeconds cannot exceed backoff.maxSeconds")

    if verdict is not None:
        if verdict.get("status") not in {"pass", "fail"}:
            errors.append("registration-verdict.json: status must be pass or fail")
        if not isinstance(verdict.get("checks"), dict):
            errors.append("registration-verdict.json: checks must be an object")
        else:
            for check_name, value in verdict["checks"].items():
                if not isinstance(value, bool):
                    errors.append(f"registration-verdict.json: check {check_name} must be boolean")
        if not isinstance(verdict.get("failedChecks"), list):
            errors.append("registration-verdict.json: failedChecks must be an array")
        if not isinstance(verdict.get("taxonomy"), list):
            errors.append("registration-verdict.json: taxonomy must be an array")
        if not isinstance(verdict.get("surfaces"), dict):
            errors.append("registration-verdict.json: surfaces must be an object")
        if not isinstance(verdict.get("perAgent"), list):
            errors.append("registration-verdict.json: perAgent must be an array")
        else:
            _validate_per_agent_states(
                verdict["perAgent"],
                states=contract["registration_states"],
                errors=errors,
            )
            if (
                verdict.get("status") == "pass"
                and isinstance(verdict.get("expectedAgents"), int)
                and verdict["expectedAgents"] > 0
                and len(verdict["perAgent"]) != verdict["expectedAgents"]
            ):
                errors.append("registration-verdict.json: perAgent count does not match expectedAgents for pass verdict")
        if verdict.get("status") == "pass":
            if isinstance(verdict.get("checks"), dict) and not all(verdict["checks"].values()):
                errors.append("registration-verdict.json: pass verdict contains failed checks")
            if isinstance(verdict.get("failedChecks"), list) and verdict["failedChecks"]:
                errors.append("registration-verdict.json: pass verdict must not contain failedChecks")
            if isinstance(verdict.get("taxonomy"), list) and verdict["taxonomy"]:
                errors.append("registration-verdict.json: pass verdict must not contain taxonomy entries")

    run_id = None
    if run_manifest is not None:
        run_id = run_manifest.get("runId")
    if verdict is not None:
        verdict_run_id = verdict.get("runId")
        if run_id is None:
            run_id = verdict_run_id
        elif verdict_run_id != run_id:
            errors.append("registration-verdict.json: runId does not match run-manifest.json")
        if run_manifest is not None:
            if verdict.get("expectedAgents") != run_manifest.get("expectedAgents"):
                errors.append("registration-verdict.json: expectedAgents does not match run-manifest.json")
            if verdict.get("runtimeProfile") != run_manifest.get("runtimeProfile"):
                errors.append("registration-verdict.json: runtimeProfile does not match run-manifest.json")
            if run_manifest.get("lastStatus") is not None and run_manifest.get("lastStatus") != verdict.get("status"):
                errors.append("run-manifest.json: lastStatus does not match registration-verdict.json")
            if run_manifest.get("lastVerdictAt") is not None and run_manifest.get("lastVerdictAt") != verdict.get("capturedAt"):
                errors.append("run-manifest.json: lastVerdictAt does not match registration-verdict.json")

    if failure_summary is not None and verdict is not None:
        if failure_summary.get("runId") != verdict.get("runId"):
            errors.append("failure-summary.json: runId does not match registration-verdict.json")
        if failure_summary.get("status") != verdict.get("status"):
            errors.append("failure-summary.json: status does not match registration-verdict.json")
        if failure_summary.get("failedChecks") != verdict.get("failedChecks"):
            errors.append("failure-summary.json: failedChecks does not match registration-verdict.json")
        if failure_summary.get("taxonomy") != verdict.get("taxonomy"):
            errors.append("failure-summary.json: taxonomy does not match registration-verdict.json")

    allowed_phases = set(contract["event_phases"])
    last_attempt = None
    last_event_status = None
    for index, event in enumerate(events, start=1):
        label = f"registration-events.jsonl:{index}"
        for field_name in contract["registration_event_required_fields"]:
            if field_name not in event:
                errors.append(f"{label}: missing field {field_name}")
        if run_id is not None and event.get("runId") != run_id:
            errors.append(f"{label}: runId does not match bundle runId")
        if event.get("phase") not in allowed_phases:
            errors.append(f"{label}: phase must be one of {sorted(allowed_phases)}")
        if event.get("status") not in {"pass", "fail"}:
            errors.append(f"{label}: status must be pass or fail")
        if not isinstance(event.get("attempt"), int) or event["attempt"] <= 0:
            errors.append(f"{label}: attempt must be a positive integer")
        if not isinstance(event.get("failedChecks"), list):
            errors.append(f"{label}: failedChecks must be an array")
        if not isinstance(event.get("taxonomy"), list):
            errors.append(f"{label}: taxonomy must be an array")
        last_attempt = event.get("attempt")
        last_event_status = event.get("status")

    if run_manifest is not None and run_manifest.get("attemptCount") is not None and last_attempt is not None:
        if run_manifest.get("attemptCount") != last_attempt:
            errors.append("run-manifest.json: attemptCount does not match last event attempt")
    if verdict is not None and last_event_status is not None and verdict.get("status") != last_event_status:
        errors.append("registration-verdict.json: status does not match last event status")

    report = {
        "schemaVersion": 1,
        "artifactsRoot": str(artifacts_root),
        "valid": not errors,
        "checkedAt": _utc_now(),
        "runId": run_id,
        "summary": {
            "requiredArtifacts": len(required_artifacts),
            "eventCount": len(events),
            "status": verdict.get("status") if verdict else None,
        },
        "errors": errors,
    }
    return report


def write_registration_evidence_report(
    report: dict[str, Any],
    *,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    artifacts_dir = output_dir or DEFAULT_PLATFORM_ARTIFACTS_DIR
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifacts_dir / "registration-evidence-report.json"
    markdown_path = artifacts_dir / "registration-evidence-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Registration Evidence Validation",
        "",
        f"- Status: `{'pass' if report['valid'] else 'fail'}`",
        f"- Checked at: `{report['checkedAt']}`",
        f"- Run ID: `{report.get('runId')}`",
        f"- Event count: `{report['summary']['eventCount']}`",
        "",
    ]
    if report["errors"]:
        lines.append("## Errors")
        lines.append("")
        for item in report["errors"]:
            lines.append(f"- {item}")
    else:
        lines.append("- Evidence bundle is complete and internally consistent.")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path
