import pytest

from tests.e2e.pages.computer_management_page import ComputerManagementPage

pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_registered_agents_are_visible_in_computer_management(authenticated_page, ready_backend):
    computer_page = ComputerManagementPage(authenticated_page)
    computer_page.load()

    assert ready_backend.is_agent_connected_xmpp(), (
        "No Ahenk agent is connected to XMPP."
    )

    backend_summary = ready_backend.get_computer_summary_counts()
    summary_counts = computer_page.wait_for_summary_counts(backend_summary)
    ui_agents = computer_page.list_agents()
    backend_count = backend_summary["total"]
    backend_labels = set(ready_backend.get_agent_labels())

    assert backend_count > 0, "BackendFacade did not find any registered agent."
    assert summary_counts == backend_summary, (
        "Computer management summary counters diverged from the official backend summary surface. "
        f"ui={summary_counts}, backend={backend_summary}"
    )
    assert len(ui_agents) == backend_count, (
        "UI tree does not list the same number of agents as the backend."
    )
    assert set(ui_agents).issubset(backend_labels), (
        "UI tree contains agent labels that do not match backend registration data."
    )

    selected_agent = computer_page.select_first_agent()
    focused_backend_summary = ready_backend.get_agent_focus_summary(selected_agent)
    focused_summary = computer_page.wait_for_summary_counts(focused_backend_summary)

    assert selected_agent in backend_labels, (
        "Selected UI agent is not present in backend registration data."
    )
    assert focused_summary == focused_backend_summary, (
        "Selecting a single agent did not focus the summary counters to the selected backend state. "
        f"ui={focused_summary}, backend={focused_backend_summary}"
    )
