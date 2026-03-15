import pytest
from tests.e2e.pages.login_page import LoginPage
from tests.e2e.pages.dashboard_page import DashboardPage
from tests.e2e.support.backend_facade import BackendFacade

@pytest.fixture(scope="module")
def backend():
    return BackendFacade()

def test_agent_visibility(ui_page, backend):
    """
    Test Senaryosu: 
    1. Lider UI'a giriş yap.
    2. BackendFacade üzerinden sisteme kayıtlı en az 1 ajan olduğunu doğrula.
    3. UI'ın bu ajanları listeleyebilecek duruma geldiğini (login sonrası) varsay.
    """
    login_page = LoginPage(ui_page)
    dashboard_page = DashboardPage(ui_page)
    
    # 1. Login ol
    login_page.load()
    login_page.login()
    assert dashboard_page.is_dashboard_visible() == True, "Dashboard'a ulaşılamadı"
    
    # 2. XMPP Bağlantısını ve API üzerindeki ajan sayısını doğrula
    assert backend.is_agent_connected_xmpp() == True, "Hiçbir ajan XMPP'ye bağlı değil!"
    
    # 60 saniyeye kadar ajanların kaydolmasını bekle (Konteynerlerin ayağa kalkma süresi olabilir)
    assert backend.wait_for_agent_registration(min_count=1, timeout=60) == True, "Lider'e kayıtlı ahenk bulunamadı (Timeout)!"
    
    registered_agents = backend.get_registered_agent_count()
    assert registered_agents > 0, "Lider'e kayıtlı ahenk bulunamadı!"
    
    # 3. Not: UI'dan listeye tıklama ve DOM element sayma işlemleri (XPath/CSS selector)
    # LiderUI DOM'u detaylı bilindiğinde eklenebilir. Şimdilik BackendFacade Hibrit testi yapılıyor.
