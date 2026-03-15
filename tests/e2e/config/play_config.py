import os

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class PlayConfig:
    BASE_URL = os.getenv("LIDER_UI_URL", "http://localhost:3001").rstrip("/")

    API_URL = (
        os.getenv("LIDER_API_URL_E2E")
        or os.getenv("LIDER_API_URL_EXTERNAL")
        or os.getenv("LIDER_API_URL", "http://localhost:8082")
    )
    XMPP_URL = os.getenv("XMPP_API_URL", "http://localhost:15280/api")

    ADMIN_USER = os.getenv("LIDER_USER", "lider-admin")
    ADMIN_PASS = os.getenv("LIDER_PASS", "secret")

    DEFAULT_TIMEOUT = _env_int("PLAYWRIGHT_TIMEOUT_MS", 30000)
    NAVIGATION_TIMEOUT = _env_int("PLAYWRIGHT_NAVIGATION_TIMEOUT_MS", 60000)
    AGENT_READY_TIMEOUT = _env_int("E2E_AGENT_READY_TIMEOUT_SECONDS", 120)

    HEADLESS = _env_bool("PLAYWRIGHT_HEADLESS", True)
    SLOW_MO_MS = _env_int("PLAYWRIGHT_SLOW_MO_MS", 0)
    KEEP_PASSED_ARTIFACTS = _env_bool("PLAYWRIGHT_KEEP_PASSED_ARTIFACTS", False)

    VIEWPORT_WIDTH = _env_int("PLAYWRIGHT_VIEWPORT_WIDTH", 1440)
    VIEWPORT_HEIGHT = _env_int("PLAYWRIGHT_VIEWPORT_HEIGHT", 900)
    LOCALE = os.getenv("PLAYWRIGHT_LOCALE", "tr-TR")
    ARTIFACTS_DIR = os.getenv("PLAYWRIGHT_ARTIFACTS_DIR", "artifacts/e2e")
