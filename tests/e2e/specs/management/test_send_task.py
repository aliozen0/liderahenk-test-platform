import pytest

from tests.e2e.pages.computer_management_page import ComputerManagementPage

pytestmark = [pytest.mark.e2e, pytest.mark.management, pytest.mark.hybrid]


def test_script_execution_flow_is_reachable_from_ui_and_executable_from_backend(
    authenticated_page,
    ready_backend,
):
    comp_page = ComputerManagementPage(authenticated_page)
    comp_page.load()

    selected_agent = comp_page.select_first_agent()
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

    is_task_dispatched = ready_backend.execute_and_verify_task(
        agent_dn=agent_dn,
        task_name="EXECUTE_SCRIPT",
        params=params,
        timeout=20,
        entry=backend_agent_entry,
    )

    assert is_task_dispatched is True, (
        f"Task dispatch was not recorded for {agent_dn}."
    )
