from playwright.sync_api import Page

from .base_page import BasePage


class DashboardPage(BasePage):
    LOAD_SELECTORS = (
        ".dashboard",
        ".p-chart",
        "text=Faaliyetlerim",
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def load(self):
        self.navigate_to_route("/dashboard")

    def wait_for_load(self):
        self.wait_for_url_contains("/dashboard")
        self.wait_for_any(self.LOAD_SELECTORS)

    def is_dashboard_visible(self) -> bool:
        try:
            self.wait_for_load()
            return True
        except Exception:
            return False

    def summary_visible(self) -> bool:
        return self.is_visible_any(self.LOAD_SELECTORS)
