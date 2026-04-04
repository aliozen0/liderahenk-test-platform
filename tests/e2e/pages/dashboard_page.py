from __future__ import annotations

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

    def _clean_text(self, text: str) -> str:
        return " ".join(text.replace("\xa0", " ").split())

    def _read_overview_card_value(self, labels: tuple[str, ...]) -> int:
        cards = self.page.locator(".dashboard .card.overview-box")
        for index in range(cards.count()):
            card = cards.nth(index)
            label = self._clean_text(card.locator("h6").first.inner_text())
            if label not in labels:
                continue
            raw_value = self._clean_text(card.locator("h1").first.inner_text())
            digits = "".join(char for char in raw_value if char.isdigit())
            if digits:
                return int(digits)
            raise AssertionError(f"Dashboard card {label!r} did not expose a numeric value.")
        raise AssertionError(f"Dashboard overview card could not be resolved for labels: {labels}")

    def get_overview_metrics(self) -> dict[str, int]:
        self.wait_for_load()
        return {
            "totalComputers": self._read_overview_card_value(
                ("Toplam İstemci Sayısı", "Total Computer Number")
            ),
            "totalUsers": self._read_overview_card_value(
                ("Toplam Kullanıcı Sayısı", "Total User Number")
            ),
            "totalSentTasks": self._read_overview_card_value(
                ("Toplam Gönderilen Görev Sayısı", "Total Sent Task Number")
            ),
            "totalAssignedPolicies": self._read_overview_card_value(
                ("Toplam Atanan Politika Sayısı", "Total Assigned Policy Number")
            ),
        }

    def wait_for_overview_metrics(
        self,
        expected: dict[str, int],
        *,
        attempts: int = 20,
        delay_ms: int = 500,
    ) -> dict[str, int]:
        last_seen: dict[str, int] = {}
        for _ in range(attempts):
            last_seen = self.get_overview_metrics()
            if last_seen == expected:
                return last_seen
            self.page.wait_for_timeout(delay_ms)
        raise AssertionError(
            "Dashboard overview metrics did not converge to the expected backend snapshot. "
            f"expected={expected}, last_seen={last_seen}"
        )
