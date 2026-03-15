from __future__ import annotations

import re

from playwright.sync_api import Page

from .base_page import BasePage


class ComputerManagementPage(BasePage):
    ROOT_SELECTORS = (
        "div.p-grid.computer-management",
        ".computer-management .el-tree",
    )
    TREE_SELECTOR = ".computer-management .el-tree"
    TREE_LABEL_SELECTOR = ".computer-management .el-tree .custom-tree-node"
    TREE_EXPAND_ICON_SELECTOR = ".computer-management .el-tree .el-tree-node__expand-icon"
    TREE_NODE_SELECTOR = ".computer-management .el-tree .el-tree-node"
    PLUGIN_SELECTORS = {
        "system": (
            "button:has-text('Sistem')",
            "button:has-text('System')",
        ),
        "package": (
            "button:has-text('Paket')",
            "button:has-text('Package')",
        ),
        "script": (
            "button:has-text('Betik')",
            "button:has-text('Script')",
        ),
        "security": (
            "button:has-text('Güvenlik')",
            "button:has-text('Security')",
        ),
        "history": (
            "button:has-text('Geçmiş')",
            "button:has-text('History')",
        ),
    }
    SCRIPT_VIEW_SELECTORS = (
        "text=Betik Çalıştır",
        "text=Script Execute",
        "button:has-text('Çalıştır')",
        "button:has-text('Run')",
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def load(self):
        self.navigate_to_route("/computer", wait_until="networkidle")
        self.wait_for_load()

    def wait_for_load(self):
        self.wait_for_url_contains("/computer")
        self.wait_for_any(self.ROOT_SELECTORS)
        self.agent_tree.wait_for(state="visible")

    @property
    def agent_tree(self):
        return self.page.locator(self.TREE_SELECTOR).first

    @property
    def agent_tree_labels(self):
        return self.page.locator(self.TREE_LABEL_SELECTOR)

    def _clean_text(self, text: str) -> str:
        return " ".join(text.replace("\xa0", " ").split())

    def _read_counter(self, labels: tuple[str, ...]) -> int:
        for label in labels:
            label_locator = self.page.locator(f"label:has-text('{label}')").first
            if label_locator.count() == 0:
                continue
            value_locator = label_locator.locator("xpath=following-sibling::a[1]").first
            raw_value = value_locator.inner_text().strip()
            digits = "".join(char for char in raw_value if char.isdigit())
            if digits:
                return int(digits)

        body_text = self.body_text()
        for label in labels:
            match = re.search(rf"{re.escape(label)}\s*:\s*(\d+)", body_text)
            if match:
                return int(match.group(1))
        raise AssertionError(f"Could not read summary counter for labels: {labels}")

    def get_summary_counts(self) -> dict[str, int]:
        return {
            "total": self._read_counter(("Toplam", "Total")),
            "online": self._read_counter(("Çevrimiçi", "Online")),
            "offline": self._read_counter(("Çevrimdışı", "Offline")),
        }

    def expand_root_node(self):
        self.wait_for_load()
        root_node = self.page.locator(self.TREE_NODE_SELECTOR).first
        if root_node.count() == 0:
            raise AssertionError("Agent tree root node is not visible.")

        if root_node.get_attribute("aria-expanded") != "true":
            self.page.locator(self.TREE_EXPAND_ICON_SELECTOR).first.click()
            for _ in range(10):
                if self.agent_tree_labels.count() > 1:
                    return
                self.page.wait_for_timeout(500)

    def list_agents(self) -> list[str]:
        self.expand_root_node()
        labels = [
            self._clean_text(text)
            for text in self.agent_tree_labels.all_inner_texts()
        ]
        return [
            label for label in labels
            if label and label.lower() != "ahenkler"
        ]

    def select_first_agent(self) -> str:
        self.expand_root_node()
        if self.agent_tree_labels.count() < 2:
            raise AssertionError("No agent entry is visible in the computer tree.")

        first_agent = self._clean_text(self.agent_tree_labels.nth(1).inner_text())
        self.agent_tree_labels.nth(1).click()

        for _ in range(10):
            if self.get_summary_counts()["total"] == 1:
                break
            self.page.wait_for_timeout(500)
        return first_agent

    def open_plugin_tab(self, plugin_name: str):
        selectors = self.PLUGIN_SELECTORS[plugin_name]
        self.click_any(selectors)

    def open_script_plugin(self):
        self.open_plugin_tab("script")

    def script_catalog_visible(self) -> bool:
        try:
            self.wait_for_any(self.SCRIPT_VIEW_SELECTORS, timeout=10000)
            return True
        except AssertionError:
            return False
