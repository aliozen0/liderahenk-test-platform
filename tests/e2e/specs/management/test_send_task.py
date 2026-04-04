import pytest

from tests.e2e.pages.computer_management_page import ComputerManagementPage

pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_script_execution_flow_is_reachable_from_ui_and_executable_from_backend(
    authenticated_page,
    ready_backend,
):
    comp_page = ComputerManagementPage(authenticated_page)
    comp_page.load()

    ui_agents = comp_page.list_agents()
    active_labels = ready_backend.get_active_agent_labels()
    candidate_agent = next((label for label in ui_agents if label in active_labels), None)
    statuses = ready_backend.get_agent_status_by_label()
    assert candidate_agent is not None, (
        "Task dispatch cannot be validated because the backend reports no UI-visible Active agent. "
        f"Current statuses: {statuses}"
    )

    selected_agent = comp_page.select_agent(candidate_agent)
    backend_agent_entry = ready_backend.get_tree_agent_entry(selected_agent)
    backend_labels = set(ready_backend.get_agent_labels())

    assert selected_agent in backend_labels, (
        "The selected UI agent is missing from backend registration data."
    )

    comp_page.open_script_plugin()
    assert comp_page.script_catalog_visible(), (
        "Script management catalog did not become visible in the UI."
    )

    params = {
        "SCRIPT_FILE_ID": "inline",
        "SCRIPT_TYPE": "bash",
        "SCRIPT_CONTENTS": "#!/bin/bash\nprintf 'liderahenk-e2e-test\\n'",
        "SCRIPT_PARAMS": "",
    }
    agent_dn = ready_backend.get_agent_dn(backend_agent_entry)

    task_result = ready_backend.execute_task_and_collect_result(
        agent_dn=agent_dn,
        task_name="EXECUTE_SCRIPT",
        params=params,
        timeout=20,
        entry=backend_agent_entry,
    )

    assert not any(
        "İstemci bulunamadı" in message for message in task_result.get("messages", [])
    ), (
        "Task dispatch is rejected by liderapi for the selected agent. "
        f"agent_dn={agent_dn}, messages={task_result.get('messages', [])}"
    )

    assert task_result["accepted"] is True, (
        f"Task dispatch request was not accepted for {agent_dn}: {task_result}"
    )
    assert task_result["historyDetected"] is True, (
        f"Task dispatch was accepted but not recorded in command history for {agent_dn}: {task_result}"
    )
