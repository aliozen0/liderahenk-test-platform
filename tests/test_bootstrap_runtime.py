from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path("platform/scripts/bootstrap_runtime.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("bootstrap_runtime_test_module", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compose_up_recreates_seed_services_before_up(monkeypatch):
    module = _load_module()
    calls: list[list[str]] = []

    def fake_run(cmd, *, env):
        calls.append(list(cmd))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_compose_base_cmd", lambda profile, project_name: ["docker", "compose"])

    module._compose_up(
        profile="dev-fidelity",
        project_name="liderahenk-test",
        services=["provisioner", "registration-orchestrator"],
        env={"ANY": "1"},
        build=False,
        scale_agents=None,
        no_deps=True,
        recreate_before_up=["provisioner"],
    )

    assert calls == [
        ["docker", "compose", "rm", "-sf", "provisioner"],
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "provisioner",
            "registration-orchestrator",
        ],
    ]


def test_compose_up_skips_rm_when_no_seed_services_requested(monkeypatch):
    module = _load_module()
    calls: list[list[str]] = []

    def fake_run(cmd, *, env):
        calls.append(list(cmd))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(module, "_run", fake_run)
    monkeypatch.setattr(module, "_compose_base_cmd", lambda profile, project_name: ["docker", "compose"])

    module._compose_up(
        profile="dev-fidelity",
        project_name="liderahenk-test",
        services=["liderapi", "lider-ui"],
        env={"ANY": "1"},
        build=False,
        scale_agents=None,
        no_deps=True,
        recreate_before_up=[],
    )

    assert calls == [
        [
            "docker",
            "compose",
            "up",
            "-d",
            "--no-build",
            "--no-deps",
            "liderapi",
            "lider-ui",
        ]
    ]


def test_declared_host_port_bindings_include_observability_ports_from_compose_stack():
    module = _load_module()

    bindings = module._declared_host_port_bindings("dev-fidelity")

    assert {
        (binding["service"], binding["host"], binding["port"])
        for binding in bindings
    } >= {
        ("liderapi", "127.0.0.1", 8082),
        ("lider-ui", "127.0.0.1", 3001),
        ("ejabberd", "127.0.0.1", 15280),
        ("grafana-alloy", "127.0.0.1", 12345),
    }


def test_lider_ui_waits_for_liderapi_health_before_starting():
    module = _load_module()
    compose_config = module._read_yaml(Path("compose/compose.lider.yml"))

    assert compose_config["services"]["lider-ui"]["depends_on"] == {
        "liderapi": {"condition": "service_healthy"}
    }


def test_host_port_conflicts_ignore_ports_already_owned_by_current_project(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_declared_host_port_bindings",
        lambda profile: [{"service": "liderapi", "host": "127.0.0.1", "port": 8082, "source": "compose"}],
    )
    monkeypatch.setattr(module, "_project_owned_host_ports", lambda profile, project_name, env: {8082})
    monkeypatch.setattr(module, "_host_port_available", lambda host, port: False)

    conflicts = module._host_port_conflicts("dev-fidelity", "liderahenk-test", {"ANY": "1"})

    assert conflicts == []


def test_bootstrap_runtime_fails_before_first_phase_when_host_port_is_busy(monkeypatch, capsys):
    module = _load_module()
    compose_calls = []

    monkeypatch.setattr(
        module,
        "_read_yaml",
        lambda path: {
            "runtime_profiles": {
                "dev-fidelity": {
                    "bootstrap_phases": [
                        {"name": "core", "services": ["ldap"], "wait_for": {"ldap": "healthy"}},
                    ]
                }
            },
            "bootstrap_defaults": {"poll_interval_seconds": 1, "phase_timeout_seconds": 1},
        },
    )
    monkeypatch.setattr(
        module,
        "_runtime_env",
        lambda profile, expected_agents, project_name: (
            {"PROJECT_NAME": project_name},
            {
                "name": profile,
                "operators": {"count": 1},
                "directory_users": {"count": 1},
                "user_groups": {"count": 1},
                "endpoint_groups": {"count": 1},
                "policy_pack": "baseline-standard",
                "session_pack": "login-basic",
            },
        ),
    )
    monkeypatch.setattr(
        module,
        "_host_port_conflicts",
        lambda profile, project_name, env: [
            {
                "service": "liderapi",
                "host": "127.0.0.1",
                "port": 8082,
                "source": "compose/compose.lider.yml",
            }
        ],
    )
    monkeypatch.setattr(module, "_compose_up", lambda **kwargs: compose_calls.append(kwargs))

    result = module.bootstrap_runtime(
        profile="dev-fidelity",
        expected_agents=10,
        project_name="liderahenk-test",
        build=False,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert compose_calls == []
    assert "host port preflight failed" in captured.err
    assert "127.0.0.1:8082" in captured.err
