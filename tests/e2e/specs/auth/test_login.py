from tests.e2e.pages.login_page import LoginPage
from tests.e2e.pages.dashboard_page import DashboardPage

def test_successful_login(ui_page):
    """
    Test Senaryosu: Geçerli kimlik bilgileriyle Lider UI'a başarılı giriş yapmak ve dashboard'u görmek.
    """
    login_page = LoginPage(ui_page)
    dashboard_page = DashboardPage(ui_page)
    
    # 1. Login sayfasına git
    login_page.load()
    
    # 2. Geçerli kullanıcı adı ve şifreyle giriş yap
    login_page.login()
    
    # 3. Yönlendirmenin URL olarak onaylanmasını kontrol et
    assert login_page.is_login_successful() == True, "Giriş başarısız oldu veya yönlendirme gerçekleşmedi."
    
    # 4. Dashboard üzerindeki elementlerin görülmesini bekle
    assert dashboard_page.is_dashboard_visible() == True, "Dashboard öğeleri yüklenemedi."
