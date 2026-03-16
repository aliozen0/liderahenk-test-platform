#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from platform_runtime.golden_baseline import (
    DEFAULT_BASELINE_DIR,
    compare_with_golden_baseline,
    write_baseline_diff,
)


def main() -> int:
    baseline_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BASELINE_DIR
    verdict_path = Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform")) / "registration-verdict.json"
    payload = compare_with_golden_baseline(
        baseline_root=baseline_root,
        verdict_path=verdict_path,
    )
    write_baseline_diff(payload, output_dir=Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform")))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
