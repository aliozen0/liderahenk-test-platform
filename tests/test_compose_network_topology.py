from __future__ import annotations

from pathlib import Path

import yaml


COMPOSE_LIDER_PATH = Path("compose/compose.lider.yml")


def test_liderapi_is_attached_to_agent_network_for_runtime_registration():
    compose = yaml.safe_load(COMPOSE_LIDER_PATH.read_text(encoding="utf-8"))

    liderapi = compose["services"]["liderapi"]
    assert "liderahenk_agents" in liderapi["networks"]


def test_agent_network_is_declared_as_external_in_compose_lider():
    compose = yaml.safe_load(COMPOSE_LIDER_PATH.read_text(encoding="utf-8"))

    agent_network = compose["networks"]["liderahenk_agents"]
    assert agent_network["external"] is True
    assert agent_network["name"] == "liderahenk-test_liderahenk_agents"
