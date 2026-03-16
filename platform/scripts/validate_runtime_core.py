#!/usr/bin/env python3
from __future__ import annotations

import json
import os

from platform_runtime.runtime_readiness import collect_runtime_core_report, write_runtime_report


def main() -> int:
    profile = os.environ.get("PLATFORM_RUNTIME_PROFILE", "dev-fast")
    report = collect_runtime_core_report(profile=profile)
    write_runtime_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
