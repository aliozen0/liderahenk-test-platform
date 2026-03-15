import os

_APPLIED = False

def _bootstrap():
    global _APPLIED
    if _APPLIED:
        return
    if os.environ.get("CONTAINER_MODE") != "1":
        return
    from hooks.runtime import install_compat_modules
    from container_patches import apply

    install_compat_modules()
    apply()
    _APPLIED = True


_bootstrap()
