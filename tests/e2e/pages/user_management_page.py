from __future__ import annotations

import re

from playwright.sync_api import Page

from .base_page import BasePage


class UserManagementPage(BasePage):
    ROOT_SELECTORS = (
        "button:has-text('LDAP Kullanıcı Yönetimi')",
        "button:has-text('LDAP Kullanıcı Grup Yönetimi')",
        "button:has-text('Gelişmiş Arama')",
    )
    TREE_SELECTOR = ".el-tree[role='tree']"
    TREE_NODE_SELECTOR = ".el-tree-node[role='treeitem']"
    TREE_LABEL_SELECTOR = ".el-tree-node .custom-tree-node"
    CONTEXT_MENU_SELECTORS = (
        ".el-overlay.mycontextmenu",
        "ul[role='menu']",
        ".p-contextmenu",
        ".p-menu.p-component",
    )
    USER_CREATE_DIALOG_SELECTORS = (
        "text=Kullanıcı Ekle",
        "text=Kullanıcı ID",
        "text=Yeni parola",
    )
    GROUP_MEMBERS_DIALOG_SELECTORS = (
        "text=Grup Üyeleri",
        "text=Grup Bilgileri",
        "text=Mevcut Kullanıcılar",
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def load(self):
        self.navigate_to_route("/user")
        self.wait_for_load()

    def wait_for_load(self):
        self.wait_for_url_contains("/user")
        self.wait_for_any(self.ROOT_SELECTORS)
        self.tree.wait_for(state="visible")

    def is_user_management_visible(self) -> bool:
        try:
            self.wait_for_load()
            return True
        except Exception:
            return False

    @property
    def tree(self):
        return self.page.locator(self.TREE_SELECTOR).first

    def open_user_management(self):
        self.page.get_by_role("button", name="LDAP Kullanıcı Yönetimi").click()
        self.wait_for_load()

    def open_group_management(self):
        self.page.get_by_role("button", name="LDAP Kullanıcı Grup Yönetimi").click()
        self.wait_for_group_management()

    def wait_for_group_management(self):
        self.wait_for_url_contains("/user")
        self.page.get_by_role("button", name="LDAP Kullanıcı Grup Yönetimi").wait_for()
        self.tree.wait_for(state="visible")

    def is_group_management_visible(self) -> bool:
        try:
            self.wait_for_group_management()
            return True
        except Exception:
            return False

    def _tree_items(self):
        return self.page.locator(self.TREE_NODE_SELECTOR)

    def _tree_item(self, label: str):
        exact_label = re.compile(rf"^\s*{re.escape(label)}\s*$")
        labels = self.page.locator(f"{self.TREE_SELECTOR} .custom-tree-node").filter(has_text=exact_label)
        for index in range(labels.count()):
            label_node = labels.nth(index)
            if not label_node.is_visible():
                continue
            return label_node.locator("xpath=ancestor::div[contains(@class,'el-tree-node')][1]")
        raise AssertionError(f"Tree item {label!r} is not visible.")

    def _tree_item_by_key(self, key: str):
        item = self.page.locator(f"{self.TREE_NODE_SELECTOR}[data-key='{key}']").first
        if item.count() == 0:
            raise AssertionError(f"Tree item with key {key!r} is not visible.")
        return item

    def _tree_label(self, label: str):
        return self._tree_item(label).locator(".custom-tree-node").first

    def _tree_label_by_key(self, key: str):
        return self._tree_item_by_key(key).locator(".custom-tree-node").first

    def _first_tree_item(self):
        item = self._tree_items().first
        if item.count() == 0:
            raise AssertionError("No tree root item is visible.")
        return item

    def _visible_context_menu(self):
        for selector in self.CONTEXT_MENU_SELECTORS:
            menu = self.page.locator(selector).first
            try:
                if menu.count() > 0 and menu.is_visible():
                    return menu
            except Exception:
                continue
        raise AssertionError("No visible context menu was found.")

    def expand_tree_item(self, label: str):
        item = self._tree_item(label)
        if item.get_attribute("aria-expanded") != "true":
            self._tree_label(label).click()
            expand_icon = item.locator(".el-tree-node__expand-icon").first
            expand_icon.scroll_into_view_if_needed()
            expand_icon.click(force=True)
            for _ in range(20):
                if item.get_attribute("aria-expanded") == "true":
                    return
                self.page.wait_for_timeout(250)
            self._tree_label(label).press("ArrowRight")
            for _ in range(20):
                if item.get_attribute("aria-expanded") == "true":
                    return
                self.page.wait_for_timeout(250)
            raise AssertionError(f"Tree item {label!r} did not expand.")

    def expand_tree_item_by_key(self, key: str):
        item = self._tree_item_by_key(key)
        if item.get_attribute("aria-expanded") == "true":
            return
        self._tree_label_by_key(key).click()
        expand_icon = item.locator(".el-tree-node__expand-icon").first
        expand_icon.scroll_into_view_if_needed()
        expand_icon.click(force=True)
        for _ in range(20):
            if item.get_attribute("aria-expanded") == "true":
                return
            self.page.wait_for_timeout(250)
        self._tree_label_by_key(key).press("ArrowRight")
        for _ in range(20):
            if item.get_attribute("aria-expanded") == "true":
                return
            self.page.wait_for_timeout(250)
        raise AssertionError(f"Tree item with key {key!r} did not expand.")

    def select_tree_item(self, label: str):
        self._tree_label(label).click()

    def open_tree_context_menu(self, label: str):
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(150)
        self._tree_label(label).scroll_into_view_if_needed()
        self._tree_label(label).click(button="right", force=True)
        self.wait_for_any(self.CONTEXT_MENU_SELECTORS)

    def open_tree_context_menu_by_key(self, key: str):
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(150)
        self._tree_label_by_key(key).scroll_into_view_if_needed()
        self._tree_label_by_key(key).click(button="right", force=True)
        self.wait_for_any(self.CONTEXT_MENU_SELECTORS)

    def click_context_menu_action(self, action_label: str):
        candidate_selectors = (
            ".p-menuitem-text",
            "[role='menuitem']",
            ".p-menuitem-link",
        )
        for selector in candidate_selectors:
            locator = self.page.locator(selector).filter(has_text=action_label)
            for index in range(locator.count() - 1, -1, -1):
                candidate = locator.nth(index)
                if candidate.is_visible():
                    candidate.click()
                    return
        raise AssertionError(f"Context menu action {action_label!r} could not be clicked.")

    def assert_context_menu_actions(self, label: str, expected_actions: tuple[str, ...]):
        self.open_tree_context_menu(label)
        for action in expected_actions:
            visible = False
            for selector in (".p-menuitem-text", "[role='menuitem']", ".p-menuitem-link"):
                locator = self.page.locator(selector).filter(has_text=action)
                visible = any(locator.nth(index).is_visible() for index in range(locator.count()))
                if visible:
                    break
            assert visible, f"Context menu action {action!r} was not visible for tree item {label!r}."
        self.page.keyboard.press("Escape")

    def assert_context_menu_actions_by_key(self, key: str, expected_actions: tuple[str, ...]):
        self.open_tree_context_menu_by_key(key)
        for action in expected_actions:
            visible = False
            for selector in (".p-menuitem-text", "[role='menuitem']", ".p-menuitem-link"):
                locator = self.page.locator(selector).filter(has_text=action)
                visible = any(locator.nth(index).is_visible() for index in range(locator.count()))
                if visible:
                    break
            assert visible, f"Context menu action {action!r} was not visible for tree item {key!r}."
        self.page.keyboard.press("Escape")

    def open_user_create_dialog_from_root(self):
        self._first_tree_item().locator(".custom-tree-node").first.click(button="right")
        self.wait_for_any(self.CONTEXT_MENU_SELECTORS)
        self.click_context_menu_action("Kullanıcı Ekle")
        self.wait_for_user_create_dialog()

    def wait_for_user_create_dialog(self):
        self.page.get_by_role("dialog").wait_for()

    @property
    def user_create_dialog(self):
        return self.page.get_by_role("dialog").filter(has_text="Kullanıcı ID").first

    @property
    def existing_group_add_user_dialog(self):
        return self.page.get_by_role("dialog").filter(has_text="Mevcut Kullanıcılar").first

    def assert_user_create_dialog_visible(self):
        dialog = self.user_create_dialog
        dialog.wait_for()
        assert dialog.is_visible(), "User creation dialog is not visible."
        for label in (
            "Kullanıcı Ekle",
            "Kullanıcı ID",
            "Kullanıcı Adı",
            "Kullanıcı Soyadı",
            "Mail Adresi",
            "Telefon Numarası",
            "Adres",
            "Yeni parola",
            "Parolayı onayla",
        ):
            assert dialog.get_by_text(label).first.is_visible(), (
                f"User creation dialog did not expose {label!r}."
            )
        assert dialog.get_by_role("button", name="İptal").is_visible(), (
            "User creation dialog did not expose a cancel button."
        )
        assert dialog.get_by_role("button", name="Ekle").is_visible(), (
            "User creation dialog did not expose a submit button."
        )

    def create_user_via_dialog(
        self,
        *,
        uid: str,
        common_name: str,
        surname: str,
        mail: str,
        password: str,
        telephone_number: str = "(555) 123-4567",
        address: str = "LiderAhenk UI acceptance flow",
    ) -> dict[str, str | int]:
        dialog = self.user_create_dialog
        dialog.wait_for()
        inputs = dialog.locator("input")
        inputs.nth(0).fill(uid)
        inputs.nth(1).fill(common_name)
        inputs.nth(2).fill(surname)
        inputs.nth(3).fill(mail)
        inputs.nth(4).fill(telephone_number)
        dialog.locator("textarea").first.fill(address)
        dialog.locator("input[type='password']").nth(0).fill(password)
        dialog.locator("input[type='password']").nth(1).fill(password)
        with self.page.expect_response(
            lambda response: response.request.method == "POST" and response.url.endswith("/api/lider/user/add-user")
        ) as response_info:
            dialog.get_by_role("button", name="Ekle").click()
        response = response_info.value
        dialog.wait_for(state="hidden")
        return {"url": response.url, "statusCode": response.status}

    def close_user_create_dialog(self):
        self.user_create_dialog.get_by_role("button", name="İptal").click()
        self.page.wait_for_timeout(300)

    def open_group_members_modal(self, group_label: str):
        self.assert_group_detail_actions_visible(group_label)
        self.page.get_by_title("Grup Üyeleri").click()
        self.wait_for_group_members_dialog()

    def wait_for_group_members_dialog(self):
        self.page.get_by_role("dialog").wait_for()

    def open_existing_group_add_user_dialog(self, group_label: str):
        self.open_tree_context_menu(group_label)
        self.click_context_menu_action("Kullanıcı Ekle")
        self.wait_for_group_members_dialog()

    def open_existing_group_add_user_dialog_by_key(self, group_key: str):
        self.open_tree_context_menu_by_key(group_key)
        menu = self._visible_context_menu()
        assert menu.locator(".p-menuitem-text").filter(has_text="Kullanıcı Ekle").first.is_visible(), (
            f"Group context menu did not expose an add-user action for {group_key!r}."
        )
        self.click_context_menu_action("Kullanıcı Ekle")
        self.wait_for_group_members_dialog()

    def add_existing_user_to_group(self, *, group_label: str, user_uid: str) -> dict[str, str | int]:
        self.open_existing_group_add_user_dialog(group_label)
        dialog = self.existing_group_add_user_dialog
        dialog.wait_for()
        root_item = self._dialog_user_root(dialog)
        if root_item.get_attribute("aria-expanded") != "true":
            root_item.locator(".el-tree-node__expand-icon").first.click()
            self.page.wait_for_timeout(500)
        user_item = dialog.locator(self.TREE_NODE_SELECTOR).filter(has_text=user_uid).first
        user_item.wait_for(state="visible")
        user_item.locator(".el-checkbox").first.click()
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith("/api/lider/user-groups/group/existing/add-user")
            )
        ) as response_info:
            dialog.get_by_role("button", name="Ekle").click()
        response = response_info.value
        dialog.wait_for(state="hidden")
        return {"url": response.url, "statusCode": response.status}

    def add_existing_user_to_group_by_key(self, *, group_key: str, user_uid: str) -> dict[str, str | int]:
        self.open_existing_group_add_user_dialog_by_key(group_key)
        dialog = self.existing_group_add_user_dialog
        dialog.wait_for()
        root_item = self._dialog_user_root(dialog)
        if root_item.get_attribute("aria-expanded") != "true":
            root_item.locator(".el-tree-node__expand-icon").first.click()
            self.page.wait_for_timeout(500)
        user_item = dialog.locator(self.TREE_NODE_SELECTOR).filter(has_text=user_uid).first
        user_item.wait_for(state="visible")
        user_item.locator(".el-checkbox").first.click()
        with self.page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.endswith("/api/lider/user-groups/group/existing/add-user")
            )
        ) as response_info:
            dialog.get_by_role("button", name="Ekle").click()
        response = response_info.value
        dialog.wait_for(state="hidden")
        return {"url": response.url, "statusCode": response.status}

    def _dialog_user_root(self, dialog):
        user_root_key = "ou=users,dc=liderahenk,dc=org"
        root_item = dialog.locator(f"{self.TREE_NODE_SELECTOR}[data-key='{user_root_key}']").first
        for _ in range(20):
            if root_item.count() > 0:
                return root_item
            fallback = dialog.locator(self.TREE_NODE_SELECTOR).filter(has_text="users").first
            if fallback.count() > 0:
                return fallback
            self.page.wait_for_timeout(250)
        raise AssertionError("Existing-user dialog did not render the users tree root.")

    def assert_group_members_dialog_visible(self):
        dialog = self.page.get_by_role("dialog").first
        dialog.wait_for()
        assert dialog.is_visible(), "Group members dialog is not visible."
        for label in (
            "Grup Üyeleri",
            "Grup Bilgileri",
            "Mevcut Kullanıcılar",
        ):
            assert dialog.get_by_text(label).first.is_visible(), (
                f"Group members dialog did not expose {label!r}."
            )
        assert dialog.get_by_role("button", name="Kapat").is_visible(), (
            "Group members dialog did not expose a close button."
        )

    def close_group_members_dialog(self):
        self.page.get_by_role("dialog").get_by_role("button", name="Kapat").click()
        self.page.wait_for_timeout(300)

    def assert_group_detail_actions_visible(self, group_label: str):
        self.open_tree_context_menu(group_label)
        menu = self._visible_context_menu()
        assert menu.locator(".p-menuitem-text").filter(has_text="Kayıt Detayı").first.is_visible(), (
            f"Group context menu did not expose a record-detail action for {group_label!r}."
        )
        self.click_context_menu_action("Kayıt Detayı")
        self.page.get_by_role("button", name="Politika Uygula").wait_for()
        self.page.get_by_title("Grup Üyeleri").wait_for()
        assert self.page.get_by_role("button", name="Politika Uygula").is_visible(), (
            f"Policy application button was not visible for group {group_label!r}."
        )
        assert self.page.get_by_title("Grup Üyeleri").is_visible(), (
            f"Group members button was not visible for group {group_label!r}."
        )

    def assert_group_detail_actions_visible_by_key(self, group_key: str):
        self.open_tree_context_menu_by_key(group_key)
        menu = self._visible_context_menu()
        assert menu.locator(".p-menuitem-text").filter(has_text="Kayıt Detayı").first.is_visible(), (
            f"Group context menu did not expose a record-detail action for {group_key!r}."
        )
        self.click_context_menu_action("Kayıt Detayı")
        self.page.get_by_role("button", name="Politika Uygula").wait_for()
        self.page.get_by_title("Grup Üyeleri").wait_for()
        assert self.page.get_by_role("button", name="Politika Uygula").is_visible(), (
            f"Policy application button was not visible for group {group_key!r}."
        )
        assert self.page.get_by_title("Grup Üyeleri").is_visible(), (
            f"Group members button was not visible for group {group_key!r}."
        )

    def open_policy_application_action(self, group_label: str):
        self.assert_group_detail_actions_visible(group_label)
        self.page.get_by_role("button", name="Politika Uygula").click()
