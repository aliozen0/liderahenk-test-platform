import pytest
import time
from tests.e2e.pages.login_page import LoginPage
from tests.e2e.pages.dashboard_page import DashboardPage
from tests.e2e.pages.computer_management_page import ComputerManagementPage
from tests.e2e.support.backend_facade import BackendFacade

@pytest.fixture(scope="module")
def backend():
    return BackendFacade()

def test_send_echo_task_and_verify(ui_page, backend):
    """
    Test Senaryosu: 
    1. Sisteme kayıtlı ajan olduğunu (BackendFacade ile) teyit et.
    2. Yönetici paneline giriş yap.
    3. BackendFacade ile Echo komunu (EXECUTE_SCRIPT) at ve arka plan result database'ini dinle.
    """
    login_page = LoginPage(ui_page)
    dashboard_page = DashboardPage(ui_page)
    comp_page = ComputerManagementPage(ui_page)
    
    # 1. Ortamı hazırla (En az 1 ajan olmalı)
    assert backend.wait_for_agent_registration(min_count=1, timeout=60) == True, "Test için ajan bulunamadı (Timeout)!"
    agent_dn = backend.api_adapter.get_agent_list()[0].get('distinguishedName')
    
    # 2. Login
    login_page.load()
    login_page.login()
    assert dashboard_page.is_dashboard_visible(), "Dashboard'a ulaşılamadı"
    
    # --- Backend Hibrit Doğrulama ---
    # Not: UI sayfasında (ComputerManagementPage) Playwright ile her adımın DOM'a tıklanması, 
    # LiderUI'ın karmaşık extjs/primevue DOM yapısı ve animasyon süreleri
    # sebebiyle bu testin Facade deseninde (Hibrit) koşması daha güvenilirdir.
    
    params = {
        "SCRIPT_TYPE": 0,
        "SCRIPT_CONTENTS": "echo 'liderahenk-e2e-test'",
        "SCRIPT_PARAMS": ""
    }
    
    # 3. Lider API üzerinden görev ateşlemesi
    is_task_dispatched = backend.execute_and_verify_task(
        agent_dn=agent_dn,
        task_name="EXECUTE_SCRIPT",
        params=params,
        timeout=15
    )
    
    assert is_task_dispatched is True, f"Görev ({agent_dn}) makinesine gönderilemedi veya işlem Lider API veritabanına yansımadı."
