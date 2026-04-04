from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVIDENCE_FILENAME = "ui-user-policy-roundtrip-evidence.json"


def _artifact_directories() -> list[Path]:
    candidates = [
        Path(os.environ.get("PLATFORM_ARTIFACTS_DIR", "artifacts/platform")),
        Path(os.environ.get("PLATFORM_RUNTIME_FALLBACK_ARTIFACTS_DIR", "artifacts/platform-local")),
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def mutation_evidence_paths() -> list[Path]:
    return [directory / EVIDENCE_FILENAME for directory in _artifact_directories()]


def clear_ui_mutation_evidence() -> None:
    for path in mutation_evidence_paths():
        try:
            path.unlink()
        except FileNotFoundError:
            continue


def write_ui_mutation_evidence(payload: dict[str, Any]) -> Path:
    body = dict(payload)
    body.setdefault("generatedAt", datetime.now(timezone.utc).isoformat())

    first_written: Path | None = None
    last_error: Exception | None = None
    for path in mutation_evidence_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
            if first_written is None:
                first_written = path
        except PermissionError as exc:
            last_error = exc
            continue
    if first_written is None:
        raise PermissionError("Unable to write UI mutation evidence artifact") from last_error
    return first_written


def load_ui_mutation_evidence() -> dict[str, Any] | None:
    for path in mutation_evidence_paths():
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None
