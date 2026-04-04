"""Shared check helpers used throughout the readiness subsystem."""
from __future__ import annotations

from typing import Any


def build_check(
    *,
    check_id: str,
    category: str,
    description: str,
    passed: bool,
    actual: Any = None,
    expected: Any = None,
    details: Any = None,
) -> dict[str, Any]:
    payload = {
        "id": check_id,
        "category": category,
        "description": description,
        "status": "pass" if passed else "fail",
    }
    if actual is not None:
        payload["actual"] = actual
    if expected is not None:
        payload["expected"] = expected
    if details is not None:
        payload["details"] = details
    return payload


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for item in checks if item["status"] == "pass")
    failed = len(checks) - passed
    return {
        "totalChecks": len(checks),
        "passedChecks": passed,
        "failedChecks": failed,
    }
