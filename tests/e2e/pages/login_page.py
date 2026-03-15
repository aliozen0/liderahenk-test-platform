from playwright.sync_api import Page
from .base_page import BasePage
from tests.e2e.config.play_config import PlayConfig

class LoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = PlayConfig.BASE_URL
        
        # Locators (Lider UI)
        self.username_input = "input[placeholder='Kullanıcı Adı']"
        self.password_input = "input[placeholder='Parola']"
        self.login_button = "button[type='submit']"
        
        # Olası hata mesajı lokasyonu
        self.error_message = ".p-toast-message-content" # PrimeVue toast hata mesaj lokasyonu

    def load(self):
        self.navigate(self.url)
        self.wait_for_selector(self.username_input)

    def login(self, username: str = PlayConfig.ADMIN_USER, password: str = PlayConfig.ADMIN_PASS):
        self.fill_text(self.username_input, username)
        self.fill_text(self.password_input, password)
        self.click(self.login_button)

    def is_login_successful(self) -> bool:
        # Başarılı girişten sonra genellikle dashboard veya overview sayfasına yönlendirilir
        try:
            self.wait_for_url_contains("/dashboard")
            return True
        except:
            return False
