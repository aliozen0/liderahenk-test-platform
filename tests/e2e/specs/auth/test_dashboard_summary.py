import pytest

from tests.e2e.pages.dashboard_page import DashboardPage

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def test_dashboard_summary_cards_match_backend(authenticated_page, ready_backend):
    dashboard_page = DashboardPage(authenticated_page)
    dashboard_page.wait_for_load()

    backend_metrics = ready_backend.get_dashboard_summary()
    ui_metrics = dashboard_page.wait_for_overview_metrics(backend_metrics)

    assert ui_metrics == backend_metrics, (
        "Dashboard summary cards diverged from the official dashboard backend payload. "
        f"ui={ui_metrics}, backend={backend_metrics}"
    )
