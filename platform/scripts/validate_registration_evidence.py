#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from platform_runtime.registration_evidence import (
    DEFAULT_PLATFORM_ARTIFACTS_DIR,
    validate_registration_evidence,
    write_registration_evidence_report,
)


def main() -> int:
    artifacts_root = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PLATFORM_ARTIFACTS_DIR
    report = validate_registration_evidence(artifacts_root)
    write_registration_evidence_report(report, output_dir=artifacts_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
