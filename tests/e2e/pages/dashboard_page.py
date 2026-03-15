from playwright.sync_api import Page
from .base_page import BasePage

class DashboardPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        
        # Dashboard UI Elementleri
        self.dashboard_container = ".dashboard"  # Dashboard.vue root elementi
        
    def wait_for_load(self):
        """Dashboard'un yüklendiğini teyit eder."""
        self.wait_for_url_contains("/dashboard")
        self.wait_for_selector(self.dashboard_container)

    def is_dashboard_visible(self) -> bool:
        try:
            self.wait_for_load()
            return True
        except:
            return False
