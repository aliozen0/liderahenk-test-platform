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
    AGENT_INFO_CARD_SELECTOR = ".computer-management .plugin-card"
    TASK_HISTORY_CARD_HEADER_SELECTORS = (
        "text=Görev Geçmişi",
        "text=Task History",
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def load(self):
        # The management view keeps background requests open on the live stack,
        # so `networkidle` is too strict for deterministic E2E navigation.
        self.navigate_to_route("/computer", wait_until="domcontentloaded")
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

    def wait_for_summary_counts(
        self,
        expected: dict[str, int],
        *,
        attempts: int = 20,
        delay_ms: int = 500,
    ) -> dict[str, int]:
        last_seen: dict[str, int] = {}
        for _ in range(attempts):
            last_seen = self.get_summary_counts()
            if last_seen == expected:
                return last_seen
            self.page.wait_for_timeout(delay_ms)
        raise AssertionError(
            "Computer management summary counters did not converge to the expected backend snapshot. "
            f"expected={expected}, last_seen={last_seen}"
        )

    def expand_root_node(self):
        self.wait_for_load()
        self.wait_for_selector(self.TREE_NODE_SELECTOR, state="attached", timeout=10000)
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

    def select_agent(self, agent_label: str) -> str:
        self.expand_root_node()
        target = self._clean_text(agent_label)
        for index in range(self.agent_tree_labels.count()):
            label = self._clean_text(self.agent_tree_labels.nth(index).inner_text())
            if label != target:
                continue
            self.agent_tree_labels.nth(index).click()
            for _ in range(10):
                if self.get_summary_counts()["total"] == 1:
                    break
                self.page.wait_for_timeout(500)
            return label
        raise AssertionError(f"Agent entry {agent_label!r} is not visible in the computer tree.")

    def open_plugin_tab(self, plugin_name: str):
        selectors = self.PLUGIN_SELECTORS[plugin_name]
        self.click_any(selectors)

    def open_script_plugin(self):
        self.open_plugin_tab("script")

    def open_history_plugin(self):
        self.open_plugin_tab("history")

    def script_catalog_visible(self) -> bool:
        try:
            self.wait_for_any(self.SCRIPT_VIEW_SELECTORS, timeout=10000)
            return True
        except AssertionError:
            return False

    @property
    def task_history_card(self):
        return self.page.locator(".plugin-card").filter(has_text="Görev Geçmişi").first

    def wait_for_task_history_card(self, timeout_ms: int = 10000):
        self.wait_for_any(self.TASK_HISTORY_CARD_HEADER_SELECTORS, timeout=timeout_ms)
        self.task_history_card.wait_for(state="visible", timeout=timeout_ms)

    def refresh_task_history(self):
        self.wait_for_task_history_card()
        refresh_button = self.task_history_card.locator("button[title='Görev Geçmişini Listele']").first
        if refresh_button.count() == 0:
            raise AssertionError("Task history refresh button is not visible in the UI.")
        refresh_button.click()

    def get_task_history_rows(self) -> list[dict[str, str]]:
        self.wait_for_task_history_card()
        rows = self.task_history_card.locator("tbody tr")
        parsed: list[dict[str, str]] = []
        for index in range(rows.count()):
            row = rows.nth(index)
            row_class = row.get_attribute("class") or ""
            if "emptymessage" in row_class:
                continue
            cells = [
                self._clean_text(cell)
                for cell in row.locator("td").all_inner_texts()
            ]
            if len(cells) < 6:
                continue
            parsed.append(
                {
                    "index": cells[0],
                    "taskName": cells[1],
                    "result": cells[2],
                    "sender": cells[3],
                    "createDate": cells[4],
                    "executionDate": cells[5],
                }
            )
        return parsed

    def wait_for_task_history_row(
        self,
        expected: dict[str, str],
        *,
        attempts: int = 20,
        delay_ms: int = 500,
    ) -> dict[str, str]:
        last_rows: list[dict[str, str]] = []
        for _ in range(attempts):
            self.refresh_task_history()
            self.page.wait_for_timeout(delay_ms)
            last_rows = self.get_task_history_rows()
            if last_rows:
                candidate = last_rows[0]
                if all(candidate.get(key) == value for key, value in expected.items()):
                    return candidate
        raise AssertionError(
            "Task history UI did not converge to the expected backend snapshot. "
            f"expected={expected}, last_rows={last_rows}"
        )

    @property
    def agent_info_card(self):
        return self.page.locator(self.AGENT_INFO_CARD_SELECTOR).first

    def wait_for_agent_info_card(self, expected_label: str | None = None, timeout_ms: int = 10000):
        self.agent_info_card.wait_for(state="visible", timeout=timeout_ms)
        if expected_label:
            target = self._clean_text(expected_label)
            started = self.page.evaluate("Date.now()")
            while True:
                text = self._clean_text(self.agent_info_card.inner_text())
                if target in text:
                    return
                current = self.page.evaluate("Date.now()")
                if int(current) - int(started) >= timeout_ms:
                    raise AssertionError(
                        f"Agent info card did not converge to the selected agent label: {expected_label!r}"
                    )
                self.page.wait_for_timeout(300)

    def get_agent_info_summary(self) -> dict[str, str]:
        self.wait_for_agent_info_card()
        row_cells = self.agent_info_card.locator(".p-grid > .p-col-4, .p-grid > .p-col-8")
        values = [
            self._clean_text(row_cells.nth(index).inner_text())
            for index in range(row_cells.count())
        ]
        pairs: dict[str, str] = {}
        for index in range(0, len(values), 2):
            if index + 1 >= len(values):
                break
            label = values[index]
            value = values[index + 1]
            if label:
                pairs[label] = value
        return {
            "status": pairs.get("Durum", ""),
            "computerName": pairs.get("Bilgisayar Adı", ""),
            "directory": pairs.get("Bulunduğu Dizin", ""),
            "userDomain": pairs.get("Kullanıcı Domain", ""),
            "ipAddress": pairs.get("IP Adresi", ""),
            "macAddress": pairs.get("MAC Adresi", ""),
            "createDate": pairs.get("Oluşturma Tarihi", ""),
        }
