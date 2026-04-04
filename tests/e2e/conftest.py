from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from tests.e2e.config.play_config import PlayConfig
from tests.e2e.pages.login_page import LoginPage
from tests.e2e.support.backend_facade import BackendFacade


def _slugify(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "test"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _request_failure_text(req) -> str:
    failure = getattr(req, "failure", None)
    if isinstance(failure, dict):
        return failure.get("errorText", "unknown")
    if isinstance(failure, str):
        return failure
    return "unknown"


def _test_failed(node: pytest.Item) -> bool:
    for phase in ("setup", "call"):
        report = getattr(node, f"rep_{phase}", None)
        if report and report.failed:
            return True
    return False


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest.fixture(scope="session")
def e2e_artifacts_root() -> Path:
    root = Path(PlayConfig.ARTIFACTS_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(scope="session")
def playwright_driver() -> Iterator[Playwright]:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_driver: Playwright) -> Iterator[Browser]:
    browser = playwright_driver.chromium.launch(
        headless=PlayConfig.HEADLESS,
        slow_mo=PlayConfig.SLOW_MO_MS,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    yield browser
    browser.close()


@pytest.fixture(scope="session")
def backend() -> BackendFacade:
    return BackendFacade()


@pytest.fixture(scope="session")
def ready_backend(backend: BackendFacade) -> BackendFacade:
    assert backend.wait_for_platform_readiness(
        min_count=1,
        timeout=PlayConfig.AGENT_READY_TIMEOUT,
    ), (
        f"E2E backend readiness failed within "
        f"{PlayConfig.AGENT_READY_TIMEOUT} seconds."
    )
    return backend


@pytest.fixture(scope="function")
def ui_page(
    request: pytest.FixtureRequest,
    browser: Browser,
    e2e_artifacts_root: Path,
) -> Iterator[Page]:
    artifact_dir = e2e_artifacts_root / _slugify(request.node.nodeid)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    console_messages: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    context = browser.new_context(
        ignore_https_errors=True,
        locale=PlayConfig.LOCALE,
        viewport={
            "width": PlayConfig.VIEWPORT_WIDTH,
            "height": PlayConfig.VIEWPORT_HEIGHT,
        },
        record_video_dir=str(artifact_dir),
        record_video_size={
            "width": PlayConfig.VIEWPORT_WIDTH,
            "height": PlayConfig.VIEWPORT_HEIGHT,
        },
    )
    context.set_default_timeout(PlayConfig.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(PlayConfig.NAVIGATION_TIMEOUT)
    context.tracing.start(screenshots=True, snapshots=True, sources=True)

    page = context.new_page()
    page.on("console", lambda message: console_messages.append(f"[{message.type}] {message.text}"))
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.on(
        "requestfailed",
        lambda req: failed_requests.append(f"{req.method} {req.url} -> {_request_failure_text(req)}"),
    )

    yield page

    failed = _test_failed(request.node)
    keep_artifacts = failed or PlayConfig.KEEP_PASSED_ARTIFACTS
    video = page.video

    metadata = {
        "nodeid": request.node.nodeid,
        "failed": failed,
        "url": page.url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        if keep_artifacts:
            page.screenshot(path=str(artifact_dir / "final-state.png"), full_page=True)
            _write_text(artifact_dir / "dom.html", page.content())
            _write_text(
                artifact_dir / "console.log",
                "\n".join(console_messages) if console_messages else "No console output captured.\n",
            )
            _write_text(
                artifact_dir / "page-errors.log",
                "\n".join(page_errors) if page_errors else "No page errors captured.\n",
            )
            _write_text(
                artifact_dir / "request-failures.log",
                "\n".join(failed_requests) if failed_requests else "No request failures captured.\n",
            )
            _write_text(
                artifact_dir / "metadata.json",
                json.dumps(metadata, ensure_ascii=False, indent=2),
            )
            try:
                context.tracing.stop(path=str(artifact_dir / "trace.zip"))
            except Exception:
                context.tracing.stop()
        else:
            context.tracing.stop()
    finally:
        context.close()

    if not video:
        return

    video_path = Path(video.path())
    if keep_artifacts:
        if video_path.exists():
            video_path.replace(artifact_dir / "video.webm")
        return

    if video_path.exists():
        video_path.unlink()


@pytest.fixture(scope="function")
def authenticated_page(ui_page: Page) -> Page:
    login_page = LoginPage(ui_page)
    login_page.login_expect_success()
    return ui_page
