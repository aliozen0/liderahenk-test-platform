from playwright.sync_api import Page
from .base_page import BasePage

class ComputerManagementPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        
        # UI Elementleri (.computer-management vue root)
        self.container = ".computer-management"
        self.total_label = "label:has-text('Toplam:')"
        
        # Ajan tablosu / Ajan tree
        self.tree_container = ".p-tree"
        
        # Sağ taraftaki Plugin Sekmeleri (Örn: system, package, limit vs.)
        self.system_plugin_btn = "button:has-text('Sistem')"
        self.script_plugin_btn = "button:has-text('Beti̇k')"
        
        # Görev gönderme eylemleri için genel buton (Sistem Yönetimi vb.)
        # Echo görevi `Sistem` modülü altındadır.
        self.task_button = "button.p-button"

    def navigate_to_computers(self):
        """Menüden 'Bilgisayarlar' sekmesine tıklandığı varsayılır, direkt URL'den gidiyoruz."""
        self.wait_for_load()
            
    def wait_for_load(self):
        self.wait_for_selector(self.container)

    def select_first_agent(self):
        """Tree/list component üzerinden ilk ajanı seçer"""
        # Element ağacı yüklendikten sonra ".p-treenode-label" tıklanır
        self.wait_for_selector(self.tree_container)
        self.page.locator(".p-treenode-label").nth(1).click()  # Lider kök node'undan sonraki ilk ajan
        
    def open_script_plugin(self):
        """Betik gönderim aracını açar"""
        self.wait_for_selector(self.script_plugin_btn)
        self.click(self.script_plugin_btn)
