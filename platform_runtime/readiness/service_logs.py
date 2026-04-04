"""Docker service log inspection utilities."""
from __future__ import annotations

import os
import subprocess
from typing import Any


def _project_name() -> str:
    return os.environ.get("PROJECT_NAME", "liderahenk-test")


def tail_service_logs(service_name: str, *, tail: int = 120) -> dict[str, Any]:
    container_name = f"{_project_name()}-{service_name}-1"
    result = subprocess.run(
        ["docker", "logs", f"--tail={tail}", container_name],
        capture_output=True,
        text=True,
    )
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return {
        "container": container_name,
        "available": result.returncode == 0,
        "tailLines": tail,
        "tail": combined,
        "error": None if result.returncode == 0 else combined[-500:],
    }


def search_service_logs(service_name: str, *, since: str = "20m") -> dict[str, Any]:
    container_name = f"{_project_name()}-{service_name}-1"
    result = subprocess.run(
        ["docker", "logs", f"--since={since}", container_name],
        capture_output=True,
        text=True,
    )
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    return {
        "container": container_name,
        "available": result.returncode == 0,
        "since": since,
        "logs": combined,
        "error": None if result.returncode == 0 else combined[-500:],
    }
