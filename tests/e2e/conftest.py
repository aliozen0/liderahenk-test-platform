import pytest
from playwright.sync_api import sync_playwright
from .config.play_config import PlayConfig

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """
    Tarayıcı varsayılan ayarlarını yapılandırır.
    """
    return {
        **browser_context_args,
        "ignore_https_errors": True,
        "viewport": {
            "width": 1280,
            "height": 720,
        }
    }

@pytest.fixture(scope="function")
def ui_page():
    """
    Playwright base fixture.
    Her test için yeni bir context/page açar.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=PlayConfig.HEADLESS,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1280, "height": 720}
        )
        
        # Bekleme sürelerini config üzerinden setle
        context.set_default_timeout(PlayConfig.DEFAULT_TIMEOUT)
        context.set_default_navigation_timeout(PlayConfig.NAVIGATION_TIMEOUT)
        
        page = context.new_page()
        yield page
        
        context.close()
        browser.close()
