from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import platform_runtime.runtime_readiness as runtime_readiness


def _load_bootstrap_runtime_module():
    module_path = Path(__file__).resolve().parents[1] / "platform" / "scripts" / "bootstrap_runtime.py"
    spec = importlib.util.spec_from_file_location("bootstrap_runtime", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_runtime_compose_base_cmd_omits_env_file(monkeypatch):
    bootstrap_runtime = _load_bootstrap_runtime_module()
    monkeypatch.setattr(
        bootstrap_runtime,
        "_compose_stack",
        lambda profile: ["compose/compose.core.yml", "compose/compose.lider.yml"],
    )

    cmd = bootstrap_runtime._compose_base_cmd("dev-fast", "liderahenk-test")

    assert cmd == [
        "docker",
        "compose",
        "-f",
        "compose/compose.core.yml",
        "-f",
        "compose/compose.lider.yml",
        "-p",
        "liderahenk-test",
    ]
    assert "--env-file" not in cmd


def test_runtime_readiness_compose_ps_omits_env_file(monkeypatch):
    monkeypatch.setattr(runtime_readiness, "_compose_stack", lambda profile: ["compose/compose.core.yml"])
    monkeypatch.setattr(runtime_readiness, "_project_name", lambda: "liderahenk-test")

    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(runtime_readiness.subprocess, "run", fake_run)

    containers = runtime_readiness._compose_ps("dev-fast")

    assert containers == []
    assert captured["cmd"] == [
        "docker",
        "compose",
        "-f",
        "compose/compose.core.yml",
        "-p",
        "liderahenk-test",
        "ps",
        "--all",
        "--format",
        "json",
    ]
    assert "--env-file" not in captured["cmd"]
