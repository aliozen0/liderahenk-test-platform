import pytest

from tests.e2e.pages.computer_management_page import ComputerManagementPage

pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_computer_information_inventory_matches_backend(authenticated_page, ready_backend):
    computer_page = ComputerManagementPage(authenticated_page)
    computer_page.load()

    ui_agents = computer_page.list_agents()
    active_labels = ready_backend.get_active_agent_labels()
    candidate_agent = next((label for label in ui_agents if label in active_labels), None)
    assert candidate_agent is not None, (
        "Computer information parity cannot be validated because no UI-visible Active agent was found."
    )
    selected_agent = computer_page.select_agent(candidate_agent)
    computer_page.wait_for_agent_info_card(expected_label=selected_agent)

    ui_summary = computer_page.get_agent_info_summary()
    backend_summary = ready_backend.get_agent_inventory_summary(selected_agent)

    assert ui_summary == backend_summary, (
        "Computer information inventory diverged from the official backend inventory surfaces. "
        f"ui={ui_summary}, backend={backend_summary}"
    )
