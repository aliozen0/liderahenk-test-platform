from playwright.sync_api import Page

class BasePage:
    def __init__(self, page: Page):
        self.page = page

    def navigate(self, url: str):
        self.page.goto(url)

    def click(self, selector: str):
        self.page.locator(selector).click()

    def fill_text(self, selector: str, text: str):
        self.page.locator(selector).fill(text)

    def wait_for_selector(self, selector: str, state="visible"):
        self.page.wait_for_selector(selector, state=state)

    def wait_for_url_contains(self, url_fragment: str):
        self.page.wait_for_url(f"**/*{url_fragment}*")

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).inner_text()
