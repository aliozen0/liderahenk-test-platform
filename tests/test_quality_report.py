from __future__ import annotations

import json
from pathlib import Path

import scripts.generate_quality_report as quality_report


def test_build_markdown_includes_release_checks():
    markdown = quality_report.build_markdown(
        [("liderapi health", True)],
        [("synthetic probe metrics", True)],
        [("registration verdict pass", False)],
        [("runtime core pass", True)],
    )
    assert "## Runtime Checks" in markdown
    assert "runtime core pass" in markdown
    assert "## Release Checks" in markdown
    assert "registration verdict pass" in markdown


def test_load_platform_artifact_reads_json(tmp_path, monkeypatch):
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    artifact = platform_dir / "registration-verdict.json"
    artifact.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    monkeypatch.setattr(quality_report, "PLATFORM_ARTIFACTS_DIR", platform_dir)
    payload = quality_report.load_platform_artifact("registration-verdict.json")
    assert payload == {"status": "pass"}


def test_check_release_signals_includes_registration_evidence(tmp_path, monkeypatch):
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    (platform_dir / "run-manifest.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (platform_dir / "registration-verdict.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (platform_dir / "baseline-diff.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (platform_dir / "registration-evidence-report.json").write_text(json.dumps({"valid": True}), encoding="utf-8")
    monkeypatch.setattr(quality_report, "PLATFORM_ARTIFACTS_DIR", platform_dir)
    checks = quality_report.check_release_signals()
    assert ("registration evidence report present", True) in checks
    assert ("registration evidence valid", True) in checks


def test_check_runtime_signals_respects_profile(tmp_path, monkeypatch):
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    (platform_dir / "runtime-core-report.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    monkeypatch.setattr(quality_report, "PLATFORM_ARTIFACTS_DIR", platform_dir)
    monkeypatch.setenv("PLATFORM_RUNTIME_PROFILE", "dev-fast")
    checks = quality_report.check_runtime_signals()
    assert ("runtime core report present", True) in checks
    assert ("runtime core pass", True) in checks
    assert not any(name == "runtime operational report present" for name, _ in checks)


def test_check_runtime_signals_requires_operational_report_for_fidelity(tmp_path, monkeypatch):
    platform_dir = tmp_path / "platform"
    platform_dir.mkdir()
    (platform_dir / "runtime-core-report.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    (platform_dir / "runtime-operational-report.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    monkeypatch.setattr(quality_report, "PLATFORM_ARTIFACTS_DIR", platform_dir)
    monkeypatch.setenv("PLATFORM_RUNTIME_PROFILE", "dev-fidelity")
    checks = quality_report.check_runtime_signals()
    assert ("runtime operational report present", True) in checks
    assert ("runtime operational pass", True) in checks
