import pytest

from tests.e2e.pages.computer_management_page import ComputerManagementPage

pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_registered_agents_are_visible_in_computer_management(authenticated_page, ready_backend):
    computer_page = ComputerManagementPage(authenticated_page)
    computer_page.load()

    assert ready_backend.is_agent_connected_xmpp(), (
        "No Ahenk agent is connected to XMPP."
    )

    summary_counts = computer_page.get_summary_counts()
    ui_agents = computer_page.list_agents()
    backend_count = ready_backend.get_registered_agent_count()
    backend_labels = set(ready_backend.get_agent_labels())

    assert backend_count > 0, "BackendFacade did not find any registered agent."
    assert summary_counts["total"] == backend_count, (
        "Computer management summary and backend agent count diverged."
    )
    assert len(ui_agents) == backend_count, (
        "UI tree does not list the same number of agents as the backend."
    )
    assert set(ui_agents).issubset(backend_labels), (
        "UI tree contains agent labels that do not match backend registration data."
    )

    selected_agent = computer_page.select_first_agent()
    focused_summary = computer_page.get_summary_counts()

    assert selected_agent in backend_labels, (
        "Selected UI agent is not present in backend registration data."
    )
    assert focused_summary["total"] == 1, (
        "Selecting a single agent did not focus the summary counters."
    )
