import pytest

from tests.e2e.pages.computer_management_page import ComputerManagementPage

pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_task_history_reflects_recent_script_dispatch(authenticated_page, ready_backend):
    computer_page = ComputerManagementPage(authenticated_page)
    computer_page.load()

    ui_agents = computer_page.list_agents()
    active_labels = ready_backend.get_active_agent_labels()
    candidate_agent = next((label for label in ui_agents if label in active_labels), None)
    assert candidate_agent is not None, (
        "Task history cannot be validated because no UI-visible Active agent was found."
    )

    selected_agent = computer_page.select_agent(candidate_agent)
    backend_agent_entry = ready_backend.get_tree_agent_entry(selected_agent)
    agent_dn = ready_backend.get_agent_dn(backend_agent_entry)

    params = {
        "SCRIPT_FILE_ID": "inline",
        "SCRIPT_TYPE": "bash",
        "SCRIPT_CONTENTS": "#!/bin/bash\nprintf 'liderahenk-task-history-test\\n'",
        "SCRIPT_PARAMS": "",
    }
    task_result = ready_backend.execute_task_and_collect_result(
        agent_dn=agent_dn,
        task_name="EXECUTE_SCRIPT",
        params=params,
        timeout=20,
        entry=backend_agent_entry,
    )

    assert task_result["accepted"] is True, (
        f"Task dispatch request was not accepted for {agent_dn}: {task_result}"
    )
    assert task_result["historyDetected"] is True, (
        f"Task dispatch was accepted but not recorded in backend command history for {agent_dn}: {task_result}"
    )

    expected_row = ready_backend.get_latest_command_history_summary(agent_dn)

    computer_page.open_history_plugin()
    ui_row = computer_page.wait_for_task_history_row(expected_row)

    assert ui_row == {**expected_row, "index": ui_row["index"]}, (
        "Task history UI diverged from the official command history backend surface. "
        f"ui={ui_row}, backend={expected_row}"
    )
