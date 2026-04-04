from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = (
    REPO_ROOT
    / "services"
    / "liderapi"
    / "extensions"
    / "src"
    / "main"
    / "java"
    / "tr"
    / "org"
    / "lider"
    / "platform"
    / "ldap"
    / "DefaultLdapBindPolicy.java"
)

# Active truth: Queue patches (not legacy patches/ directory)
QUEUE_PATCH_020 = REPO_ROOT / "services" / "liderapi" / "wiring" / "patches" / "queue" / "020-ldap-service-v1-surface.patch"
QUEUE_PATCH_021 = REPO_ROOT / "services" / "liderapi" / "wiring" / "patches" / "queue" / "021-ldap-service-provider-extraction.patch"
COMPOSE_LIDER_PATH = REPO_ROOT / "compose" / "compose.lider.yml"


# --- DefaultLdapBindPolicy (extension) tests ---

def test_default_ldap_bind_policy_uses_env_based_bind_mode_resolution():
    """Extension reads LIDER_LDAP_BIND_MODE and LIDER_FORCE_LDAP_ADMIN_BIND from env."""
    source = DEFAULT_POLICY_PATH.read_text(encoding="utf-8")

    assert '"LIDER_LDAP_BIND_MODE"' in source
    assert '"LIDER_FORCE_LDAP_ADMIN_BIND"' in source
    # Must NOT reference the old v1-broad feature profile approach
    assert '"LIDER_FEATURE_PROFILE"' not in source


def test_default_ldap_bind_policy_has_no_static_methods():
    """Extension must not expose static methods — upstream uses DI via LdapBindPolicy interface."""
    source = DEFAULT_POLICY_PATH.read_text(encoding="utf-8")

    assert "public static" not in source, (
        "DefaultLdapBindPolicy must not have static methods. "
        "Upstream depends on LdapBindPolicy interface via @Autowired DI, not static calls."
    )


def test_default_ldap_bind_policy_implements_strategy_interface():
    """Extension implements LdapBindPolicy (Strategy Pattern)."""
    source = DEFAULT_POLICY_PATH.read_text(encoding="utf-8")

    assert "implements LdapBindPolicy" in source
    assert "@Component" in source
    assert "@Override" in source
    assert "LdapBindCredentials resolve(" in source


def test_default_ldap_bind_policy_documents_solid_alignment():
    """Extension has architecture documentation for maintainability."""
    source = DEFAULT_POLICY_PATH.read_text(encoding="utf-8")

    assert "Strategy Pattern" in source
    assert "SRP" in source or "Single Responsibility" in source
    assert "DIP" in source or "Dependency Inversion" in source


# --- Queue patch (wiring) tests ---

def test_queue_patch_021_injects_ldap_bind_policy_via_di():
    """Queue patch 021 must inject LdapBindPolicy via @Autowired (DIP)."""
    source = QUEUE_PATCH_021.read_text(encoding="utf-8")

    assert "+\tprivate LdapBindPolicy ldapBindPolicy;" in source
    assert "+\t@Autowired" in source
    assert "ldapBindPolicy.resolve(configurationService)" in source


def test_queue_patch_021_removes_inline_bind_logic():
    """Queue patch 021 must remove the inline forceAdminBind logic from upstream."""
    source = QUEUE_PATCH_021.read_text(encoding="utf-8")

    # These should be removed (prefixed with -)
    assert '-\t\tboolean forceAdminBind = "v1-broad"' in source
    assert "-\t\tif (!forceAdminBind && AuthenticationService.isLogged())" in source


def test_queue_patch_021_uses_bind_credentials_record():
    """Queue patch 021 uses LdapBindCredentials record for clean value passing."""
    source = QUEUE_PATCH_021.read_text(encoding="utf-8")

    assert "bindCredentials.bindDn()" in source
    assert "bindCredentials.password()" in source


# --- Compose defaults test ---

def test_compose_defaults_bind_mode_to_authenticated_user_until_topology_overrides_it():
    source = COMPOSE_LIDER_PATH.read_text(encoding="utf-8")

    assert "LIDER_LDAP_BIND_MODE: ${LIDER_LDAP_BIND_MODE:-authenticated-user}" in source
    assert "LIDER_FORCE_LDAP_ADMIN_BIND: ${LIDER_FORCE_LDAP_ADMIN_BIND:-0}" in source


# --- Legacy patch guard ---

def test_legacy_patches_directory_contains_no_java_files():
    """Legacy patches/ directory has been fully cleaned — no Java files should exist."""
    legacy_dir = REPO_ROOT / "services" / "liderapi" / "patches"
    java_files = sorted(legacy_dir.glob("*.java")) if legacy_dir.is_dir() else []
    assert not java_files, (
        f"Legacy patches/ directory still contains Java files: {[f.name for f in java_files]}. "
        "All legacy overrides have been replaced by queue patches in wiring/patches/queue/."
    )
