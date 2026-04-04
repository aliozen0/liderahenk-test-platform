from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class PolicyManagementPage(BasePage):
    ROOT_SELECTORS = (
        "button:has-text('Politikalar')",
        "button:has-text('Profiller')",
        "text=Politika Yönetimi",
    )
    POLICY_TAB_SELECTORS = (
        "button:has-text('Politikalar')",
        "[role='tab']:has-text('Politikalar')",
    )
    PROFILE_TAB_SELECTORS = (
        "button:has-text('Profiller')",
        "[role='tab']:has-text('Profiller')",
    )
    POLICY_DIALOG_SELECTORS = (
        "text=Politika Ekle",
        "text=Politika Adı",
        "text=Açıklama",
    )
    POLICY_LIST_SELECTORS = (
        "text=Politika Yönetimi",
        "text=Politika Listesi",
    )
    PROFILE_LIST_SELECTORS = (
        "text=Profil Yönetimi",
        "text=Betik Profili",
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def load(self):
        self.navigate_to_route("/policy")
        self.wait_for_load()

    def wait_for_load(self):
        self.wait_for_url_contains("/policy")
        self.wait_for_any(self.ROOT_SELECTORS)
        self.page.get_by_role("tab", name="Politikalar").wait_for()
        self.page.get_by_role("tab", name="Profiller").wait_for()

    def is_policy_management_visible(self) -> bool:
        try:
            self.wait_for_load()
            return True
        except Exception:
            return False

    def assert_tabs_visible(self):
        assert self.is_visible_any(self.POLICY_TAB_SELECTORS), (
            "Policy management page did not expose the Policies tab."
        )
        assert self.is_visible_any(self.PROFILE_TAB_SELECTORS), (
            "Policy management page did not expose the Profiles tab."
        )

    def open_policies_tab(self):
        self.page.get_by_role("tab", name="Politikalar").click()
        self.wait_for_policies_tab()

    def wait_for_policies_tab(self):
        self.wait_for_any(self.POLICY_LIST_SELECTORS)

    def open_profiles_tab(self):
        self.page.get_by_role("tab", name="Profiller").click()
        self.wait_for_profiles_tab()

    def wait_for_profiles_tab(self):
        self.wait_for_any(self.PROFILE_LIST_SELECTORS)

    def open_add_policy_dialog(self):
        self.open_policies_tab()
        self.page.get_by_role("button", name="Ekle").first.click()
        self.wait_for_policy_dialog()

    def wait_for_policy_dialog(self):
        self.page.get_by_role("dialog").wait_for()

    def assert_policy_dialog_visible(self):
        dialog = self.page.get_by_role("dialog").first
        dialog.wait_for()
        assert dialog.is_visible(), "Policy creation dialog is not visible."
        for label in (
            "Politika Ekle",
            "Politika Adı",
            "Açıklama",
        ):
            assert dialog.get_by_text(label).first.is_visible(), (
                f"Policy creation dialog did not expose {label!r}."
            )
        assert dialog.get_by_role("button", name="İptal").is_visible(), (
            "Policy creation dialog did not expose a cancel button."
        )
        assert dialog.get_by_role("button", name="Ekle").is_visible(), (
            "Policy creation dialog did not expose a submit button."
        )

    def close_policy_dialog(self):
        self.page.get_by_role("dialog").get_by_role("button", name="İptal").click()
        self.page.wait_for_timeout(300)

    def assert_profile_list_visible(self):
        self.open_profiles_tab()
        for selector in self.PROFILE_LIST_SELECTORS:
            assert self.page.locator(selector).first.is_visible(), (
                f"Profile list selector was not visible: {selector}"
            )
