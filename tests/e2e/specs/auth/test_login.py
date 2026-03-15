import pytest

from tests.e2e.pages.login_page import LoginPage

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


def test_successful_login(ui_page):
    login_page = LoginPage(ui_page)
    dashboard_page = login_page.login_expect_success()

    assert login_page.is_login_successful(), (
        "Login did not redirect to the dashboard route."
    )
    assert dashboard_page.summary_visible(), (
        "Dashboard summary widgets did not become visible after login."
    )
    assert not login_page.get_error_messages(), (
        "Unexpected login error toast was rendered during a successful login."
    )
