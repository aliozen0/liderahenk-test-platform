#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from platform_runtime.golden_baseline import DEFAULT_BASELINE_DIR, validate_golden_baseline


def _summarize_errors(errors: list[str]) -> dict[str, int]:
    summary = {"missing": 0, "manifest": 0, "config": 0, "other": 0}
    for error in errors:
        if error.startswith("missing required file:"):
            summary["missing"] += 1
        elif error.startswith("manifest ") or error.startswith("manifest.json:"):
            summary["manifest"] += 1
        elif error.startswith("config "):
            summary["config"] += 1
        else:
            summary["other"] += 1
    return summary


def main() -> int:
    baseline_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BASELINE_DIR
    report = validate_golden_baseline(baseline_root)
    error_summary = _summarize_errors(report.get("errors", []))
    payload = {
        "baselineRoot": report["baselineRoot"],
        "status": report.get("status", "fail"),
        "manifestStatus": report.get("manifestStatus"),
        "valid": report["valid"],
        "errorSummary": error_summary,
        "message": (
            "Canonical baseline pending capture."
            if report.get("status") == "pending-capture"
            else "Canonical baseline ready."
            if report["valid"]
            else "Canonical baseline invalid."
        ),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
