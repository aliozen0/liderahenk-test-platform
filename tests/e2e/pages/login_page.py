from __future__ import annotations

from playwright.sync_api import Page

from tests.e2e.config.play_config import PlayConfig
from .base_page import BasePage
from .dashboard_page import DashboardPage


class LoginPage(BasePage):
    USERNAME_SELECTORS = (
        "input[placeholder='Kullanıcı Adı']",
        "input[placeholder='Username']",
        "input[type='text']",
    )
    PASSWORD_SELECTORS = (
        "input[placeholder='Parola']",
        "input[placeholder='Password']",
        "input[type='password']",
    )
    SUBMIT_SELECTORS = (
        "button[type='submit']",
        "button:has-text('Oturum Aç')",
        "button:has-text('Sign In')",
        "button:has-text('Login')",
    )
    FORM_READY_SELECTORS = (
        "button[type='submit']",
        "input[type='password']",
    )
    ERROR_SELECTORS = (
        ".p-toast-message-content",
        ".p-inline-message",
        ".p-message-text",
        "[role='alert']",
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def load(self):
        self.navigate_to_route("/login")
        self.wait_for_any(self.FORM_READY_SELECTORS)

    def login(self, username: str = PlayConfig.ADMIN_USER, password: str = PlayConfig.ADMIN_PASS):
        self.fill_any(self.USERNAME_SELECTORS, username)
        self.fill_any(self.PASSWORD_SELECTORS, password)
        self.click_any(self.SUBMIT_SELECTORS)

    def wait_for_success(self) -> DashboardPage:
        dashboard_page = DashboardPage(self.page)
        dashboard_page.wait_for_load()
        return dashboard_page

    def login_expect_success(
        self,
        username: str = PlayConfig.ADMIN_USER,
        password: str = PlayConfig.ADMIN_PASS,
    ) -> DashboardPage:
        self.load()
        self.login(username=username, password=password)
        return self.wait_for_success()

    def is_login_successful(self) -> bool:
        try:
            self.wait_for_url_contains("/dashboard")
            return True
        except Exception:
            return False

    def get_error_messages(self) -> list[str]:
        messages = []
        for selector in self.ERROR_SELECTORS:
            locator = self.page.locator(selector)
            for index in range(locator.count()):
                text = locator.nth(index).inner_text().strip()
                if text:
                    messages.append(text)
        return list(dict.fromkeys(messages))
