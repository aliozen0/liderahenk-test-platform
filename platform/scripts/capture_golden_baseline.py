#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from platform_runtime.golden_baseline import (
    DEFAULT_BASELINE_DIR,
    capture_golden_baseline,
    parse_capture_args,
)


def main() -> int:
    args = parse_capture_args()
    baseline_root = Path(args.baseline_root) if args.baseline_root else DEFAULT_BASELINE_DIR
    env_file = Path(args.env_file) if args.env_file else None
    report = capture_golden_baseline(
        baseline_root,
        source_label=args.source_label,
        env_file=env_file,
        force=bool(args.force),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
