#!/usr/bin/env python3
"""Generate a consolidated acceptance summary artifact.

Collects unit tests, runtime core checks, and runtime operational checks
into a single JSON + Markdown report with green/yellow/red surface
indicators.

Usage:
    python3 platform/scripts/generate_acceptance_summary.py \
        --profile dev-fidelity --agents 10
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from platform_runtime.readiness import (
    collect_runtime_core_report,
    collect_runtime_operational_report,
    write_runtime_report,
)

ARTIFACTS_DIR = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_unit_tests() -> dict[str, Any]:
    """Run the unit test gate and capture results."""
    test_files = [
        "tests/test_topology_profile_loader.py",
        "tests/test_scenario_pack_loader.py",
        "tests/test_scenario_runtime_runner.py",
        "tests/test_directory_topology_seed.py",
        "tests/test_ui_api_mutation_contract.py",
        "tests/test_runtime_support_summary.py",
        "tests/test_liderapi_ldap_bind_policy.py",
        "tests/test_bootstrap_runtime.py",
        "tests/test_ahenk_liderapi_gate.py",
        "tests/test_compose_network_topology.py",
        "tests/test_registration_evidence.py",
    ]
    cmd = [
        "python3", "-m", "pytest", *test_files,
        "-v", "--timeout=120", "--tb=short", "-q",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())
    started = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()), env=env)
    duration = round(time.monotonic() - started, 2)

    # Parse pytest output for counts
    output_lines = result.stdout.strip().splitlines()
    summary_line = output_lines[-1] if output_lines else ""

    return {
        "status": "pass" if result.returncode == 0 else "fail",
        "returnCode": result.returncode,
        "durationSeconds": duration,
        "summaryLine": summary_line,
        "stdoutTail": "\n".join(output_lines[-5:]),
    }


def _status_color(status: str) -> str:
    if status == "pass":
        return "🟢"
    elif status == "fail":
        return "🔴"
    return "🟡"


def _support_surface(
    *,
    active_scenarios: list[str],
    supported_steps: list[str],
    unsupported_steps: list[str],
    catalog_supported_steps: list[str],
    catalog_unsupported_steps: list[str],
) -> dict[str, str]:
    if active_scenarios:
        status = "pass" if not unsupported_steps else "fail"
        detail = (
            f"{len(supported_steps)} active supported, "
            f"{len(unsupported_steps)} active unsupported"
        )
        return {"status": status, "detail": detail}

    status = "partial"
    detail = (
        "no active scenarios; "
        f"catalog {len(catalog_supported_steps)} supported, "
        f"{len(catalog_unsupported_steps)} unsupported"
    )
    return {"status": status, "detail": detail}


def generate_acceptance_summary(profile: str, agents: int) -> dict[str, Any]:
    """Generate consolidated acceptance summary."""
    started_at = _utc_now()

    # 1. Unit tests
    print("  [1/3] Running unit test gate...", flush=True)
    unit_result = _run_unit_tests()

    # 2. Runtime core
    print("  [2/3] Collecting runtime core report...", flush=True)
    core_report = collect_runtime_core_report(profile)

    # 3. Runtime operational
    print("  [3/3] Collecting runtime operational report...", flush=True)
    operational_report = collect_runtime_operational_report(profile)

    # Build surfaces
    surfaces = []
    surfaces.append({
        "name": "Unit Tests",
        "status": unit_result["status"],
        "detail": unit_result["summaryLine"],
    })
    surfaces.append({
        "name": "Runtime Core",
        "status": core_report["status"],
        "detail": f"{core_report['summary']['passedChecks']}/{core_report['summary']['totalChecks']} checks passed",
    })
    surfaces.append({
        "name": "Runtime Operational",
        "status": operational_report["status"],
        "detail": f"{operational_report['summary']['passedChecks']}/{operational_report['summary']['totalChecks']} checks passed",
    })

    # Session support summary
    session_support = operational_report.get("support", {}).get("sessionSupport", {})
    active_scenarios = operational_report.get("scenarios", {}).get("activeScenarios", [])
    supported_steps = session_support.get("supportedDeclaredSteps", [])
    unsupported_steps = session_support.get("unsupportedDeclaredSteps", [])
    catalog_supported_steps = session_support.get("catalogSupportedDeclaredSteps", supported_steps)
    catalog_unsupported_steps = session_support.get("catalogUnsupportedDeclaredSteps", unsupported_steps)
    active_scenarios = session_support.get("activeScenarios", [])
    session_surface = _support_surface(
        active_scenarios=active_scenarios,
        supported_steps=supported_steps,
        unsupported_steps=unsupported_steps,
        catalog_supported_steps=catalog_supported_steps,
        catalog_unsupported_steps=catalog_unsupported_steps,
    )
    surfaces.append({
        "name": "Session Support",
        "status": session_surface["status"],
        "detail": session_surface["detail"],
    })

    # Mutation support summary
    mutation_support = operational_report.get("support", {}).get("mutationSupport", {})
    supported_mutation = mutation_support.get("supportedDeclaredSteps", [])
    unsupported_mutation = mutation_support.get("unsupportedDeclaredSteps", [])
    catalog_supported_mutation = mutation_support.get("catalogSupportedDeclaredSteps", supported_mutation)
    catalog_unsupported_mutation = mutation_support.get("catalogUnsupportedDeclaredSteps", unsupported_mutation)
    mutation_surface = _support_surface(
        active_scenarios=active_scenarios,
        supported_steps=supported_mutation,
        unsupported_steps=unsupported_mutation,
        catalog_supported_steps=catalog_supported_mutation,
        catalog_unsupported_steps=catalog_unsupported_mutation,
    )
    surfaces.append({
        "name": "Mutation Support",
        "status": mutation_surface["status"],
        "detail": mutation_surface["detail"],
    })

    overall = "pass"
    for s in surfaces:
        if s["status"] == "fail":
            overall = "fail"
            break
        if s["status"] == "partial":
            overall = "partial"

    return {
        "schemaVersion": 1,
        "reportType": "acceptance-summary",
        "status": overall,
        "profile": profile,
        "expectedAgents": agents,
        "generatedAt": started_at,
        "completedAt": _utc_now(),
        "surfaces": surfaces,
        "unitTests": unit_result,
        "runtimeCore": {
            "status": core_report["status"],
            "summary": core_report["summary"],
        },
        "runtimeOperational": {
            "status": operational_report["status"],
            "summary": operational_report["summary"],
        },
        "activeScenarios": active_scenarios,
        "sessionSupport": session_support,
        "mutationSupport": mutation_support,
    }


def write_acceptance_summary(report: dict[str, Any]) -> tuple[Path, Path]:
    """Write acceptance summary as JSON + Markdown."""
    fallback_dir = Path(
        os.environ.get("PLATFORM_RUNTIME_FALLBACK_ARTIFACTS_DIR", "artifacts/platform-local")
    )

    lines = [
        "# Acceptance Summary",
        "",
        f"- Profile: `{report['profile']}`",
        f"- Expected agents: `{report['expectedAgents']}`",
        f"- Overall: **{report['status'].upper()}**",
        f"- Generated: `{report['generatedAt']}`",
        "",
        "## Surfaces",
        "",
        "| Surface | Status | Detail |",
        "|---------|--------|--------|",
    ]
    for s in report["surfaces"]:
        color = _status_color(s["status"])
        lines.append(f"| {s['name']} | {color} {s['status'].upper()} | {s['detail']} |")

    lines.extend([
        "",
        "## Active Scenario Packs",
        "",
    ])
    active_scenarios = report.get("activeScenarios", [])
    if not active_scenarios:
        lines.append("- `none` (no active scenario packs)")
    for scenario in active_scenarios:
        lines.append(f"- `{scenario}`")

    lines.extend([
        "",
        "## Active Session Steps",
        "",
    ])
    session_catalog = report.get("sessionSupport", {}).get("declaredStepCatalog", {})
    if not session_catalog:
        lines.append("- `none` (no active scenario packs)")
    for step_name, step_data in sorted(session_catalog.items()):
        status = "🟢 supported" if step_data.get("supported") else "🔴 unsupported"
        mode = step_data.get("mode", "")
        lines.append(f"- `{step_name}` → {status}" + (f" ({mode})" if mode else ""))

    lines.extend([
        "",
        "## Session Step Catalog",
        "",
    ])
    session_catalog = report.get("sessionSupport", {}).get("catalogDeclaredStepCatalog", {})
    for step_name, step_data in sorted(session_catalog.items()):
        status = "🟢 supported" if step_data.get("supported") else "🟡 unsupported"
        mode = step_data.get("mode", "")
        lines.append(f"- `{step_name}` → {status}" + (f" ({mode})" if mode else ""))

    lines.extend([
        "",
        "## Active Mutation Steps",
        "",
    ])
    mutation_catalog = report.get("mutationSupport", {}).get("declaredStepCatalog", {})
    if not mutation_catalog:
        lines.append("- `none` (no active scenario packs)")
    for step_name, step_data in sorted(mutation_catalog.items()):
        status = "🟢 supported" if step_data.get("supported") else "🟡 unsupported"
        lines.append(f"- `{step_name}` → {status}")

    lines.extend([
        "",
        "## Mutation Step Catalog",
        "",
    ])
    mutation_catalog = report.get("mutationSupport", {}).get("catalogDeclaredStepCatalog", {})
    for step_name, step_data in sorted(mutation_catalog.items()):
        status = "🟢 supported" if step_data.get("supported") else "🟡 unsupported"
        lines.append(f"- `{step_name}` → {status}")

    lines.extend([
        "",
        "---",
        f"*Generated by platform acceptance summary at {report['completedAt']}*",
    ])
    markdown_content = "\n".join(lines) + "\n"

    def _write_to(directory: Path) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "acceptance-summary.json"
        md_path = directory / "acceptance-summary.md"
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        md_path.write_text(markdown_content, encoding="utf-8")
        return json_path, md_path

    try:
        return _write_to(ARTIFACTS_DIR)
    except PermissionError:
        return _write_to(fallback_dir)


def main():
    parser = argparse.ArgumentParser(description="Generate acceptance summary")
    parser.add_argument("--profile", default=os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fidelity"))
    parser.add_argument("--agents", type=int, default=int(os.environ.get("AHENK_COUNT", "10")))
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="Exit non-zero unless the acceptance summary status is PASS.",
    )
    args = parser.parse_args()

    print(f"Generating acceptance summary (profile={args.profile}, agents={args.agents})...")
    report = generate_acceptance_summary(args.profile, args.agents)
    json_path, md_path = write_acceptance_summary(report)
    print(f"\nAcceptance Summary: {report['status'].upper()}")
    for s in report["surfaces"]:
        color = _status_color(s["status"])
        print(f"  {color} {s['name']}: {s['status'].upper()} — {s['detail']}")
    print(f"\nArtifacts:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    if args.require_pass and report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
