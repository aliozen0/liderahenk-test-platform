#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from platform_runtime.golden_baseline import DEFAULT_BASELINE_DIR, validate_golden_baseline


def main() -> int:
    baseline_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BASELINE_DIR
    report = validate_golden_baseline(baseline_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
