import os
import sys
import types

_APPLIED = False


def _install_fake_apt():
    if "apt" in sys.modules:
        return

    apt_mod = types.ModuleType("apt")
    progress_mod = types.ModuleType("apt.progress")
    text_mod = types.ModuleType("apt.progress.text")
    base_mod = types.ModuleType("apt.progress.base")

    class _AcquireProgress:
        pass

    class _InstallProgress:
        pass

    class _FakeCache(dict):
        def update(self):
            return None

        def open(self, _arg=None):
            return None

        def commit(self, fetch_progress=None, install_progress=None):
            return None

        def get(self, key, default=None):
            return super().get(key, default)

    text_mod.AcquireProgress = _AcquireProgress
    base_mod.InstallProgress = _InstallProgress
    progress_mod.text = text_mod
    progress_mod.base = base_mod
    apt_mod.progress = progress_mod
    apt_mod.Cache = _FakeCache

    sys.modules["apt"] = apt_mod
    sys.modules["apt.progress"] = progress_mod
    sys.modules["apt.progress.text"] = text_mod
    sys.modules["apt.progress.base"] = base_mod


def _bootstrap():
    global _APPLIED
    if _APPLIED:
        return
    if os.environ.get("CONTAINER_MODE") != "1":
        return
    _install_fake_apt()
    from container_patches import apply

    apply()
    _APPLIED = True


_bootstrap()
