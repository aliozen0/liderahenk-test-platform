import os
from dotenv import load_dotenv

load_dotenv()

class PlayConfig:
    # Lider UI Base URL
    BASE_URL = os.getenv("LIDER_UI_URL", "http://localhost:3001")
    
    # Backend Services
    API_URL = os.getenv("LIDER_API_URL", "http://localhost:8082")
    XMPP_URL = os.getenv("XMPP_API_URL", "http://localhost:15280/api")
    
    # Credentials
    ADMIN_USER = os.getenv("LIDER_USER", "lider")
    ADMIN_PASS = os.getenv("LIDER_PASS", "lider")
    
    # Timeouts
    DEFAULT_TIMEOUT = 30000  # 30 seconds
    NAVIGATION_TIMEOUT = 60000 # 60 seconds
    
    # Headless Mode
    HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
