from __future__ import annotations

from typing import Sequence

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.e2e.config.play_config import PlayConfig


class BasePage:
    def __init__(self, page: Page):
        self.page = page

    def navigate(self, url: str, *, wait_until: str = "domcontentloaded"):
        self.page.goto(url, wait_until=wait_until)

    def navigate_to_route(self, route: str, *, wait_until: str = "domcontentloaded"):
        normalized_route = route if route.startswith("/") else f"/{route}"
        self.navigate(f"{PlayConfig.BASE_URL}/#{normalized_route}", wait_until=wait_until)

    def click(self, selector: str):
        self.page.locator(selector).first.click()

    def fill_text(self, selector: str, text: str):
        self.page.locator(selector).first.fill(text)

    def wait_for_selector(self, selector: str, state: str = "visible", timeout: int = None):
        self.page.locator(selector).first.wait_for(state=state, timeout=timeout)

    def wait_for_url_contains(self, url_fragment: str):
        self.page.wait_for_url(f"**/*{url_fragment}*")

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).first.inner_text().strip()

    def wait_for_any(self, selectors: Sequence[str], *, state: str = "visible", timeout: int = None) -> str:
        last_error = None
        for selector in selectors:
            try:
                self.wait_for_selector(selector, state=state, timeout=timeout)
                return selector
            except PlaywrightTimeoutError as exc:
                last_error = exc
        raise AssertionError(f"None of the selectors became {state}: {selectors}") from last_error

    def click_any(self, selectors: Sequence[str], *, timeout: int = None) -> str:
        selector = self.wait_for_any(selectors, timeout=timeout)
        self.click(selector)
        return selector

    def fill_any(self, selectors: Sequence[str], value: str, *, timeout: int = None) -> str:
        selector = self.wait_for_any(selectors, timeout=timeout)
        self.fill_text(selector, value)
        return selector

    def text_any(self, selectors: Sequence[str], *, timeout: int = None) -> str:
        selector = self.wait_for_any(selectors, state="attached", timeout=timeout)
        return self.get_text(selector)

    def is_visible_any(self, selectors: Sequence[str]) -> bool:
        for selector in selectors:
            locator = self.page.locator(selector).first
            try:
                if locator.count() > 0 and locator.is_visible():
                    return True
            except PlaywrightTimeoutError:
                continue
        return False

    def body_text(self) -> str:
        return self.page.locator("body").inner_text()
