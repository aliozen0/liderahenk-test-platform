from __future__ import annotations

from adapters.platform_bundle import _resolve_host_urls


def test_resolve_host_urls_rewrites_internal_urls_for_host_context(monkeypatch):
    monkeypatch.delenv("PLATFORM_EXECUTION_CONTEXT", raising=False)
    monkeypatch.setenv("LIDER_API_URL", "http://liderapi:8080")
    monkeypatch.setenv("EJABBERD_API_URL", "http://ejabberd:5280/api")

    api_url, ejabberd_url = _resolve_host_urls()

    assert api_url == "http://localhost:8082"
    assert ejabberd_url == "http://localhost:15280/api"


def test_resolve_host_urls_keeps_internal_urls_for_container_context(monkeypatch):
    monkeypatch.setenv("PLATFORM_EXECUTION_CONTEXT", "container")
    monkeypatch.setenv("LIDER_API_URL", "http://liderapi:8080")
    monkeypatch.setenv("EJABBERD_API_URL", "http://ejabberd:5280/api")

    api_url, ejabberd_url = _resolve_host_urls()

    assert api_url == "http://liderapi:8080"
    assert ejabberd_url == "http://ejabberd:5280/api"
