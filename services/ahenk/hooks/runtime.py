import os
import sys
import types
import subprocess


def env(name, default=""):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def log(message):
    print(f"[container-patches] {message}", flush=True)


def build_context():
    agent_id = env("AGENT_ID", "ahenk-001")
    return {
        "agent_id": agent_id,
        "agent_hostname": env("AGENT_HOSTNAME", f"{agent_id}-host"),
        "agent_password": env("AGENT_XMPP_PASS", env("XMPP_AGENT_PASS", env("XMPP_ADMIN_PASS", "secret"))),
    }


def configure_plain_xmpp(client):
    client.use_tls = False
    client.disable_starttls = True
    client.force_starttls = False
    client.enable_starttls = False
    client.enable_direct_tls = False
    client.enable_plaintext = True
    try:
        client["feature_mechanisms"].unencrypted_plain = True
        client["feature_mechanisms"].unencrypted_scram = True
    except Exception:
        pass


def run_subprocess(cmd):
    child_env = dict(os.environ)
    child_env["DEBIAN_FRONTEND"] = "noninteractive"
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=child_env, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def install_compat_modules():
    _install_fake_apt()
    _install_fake_pystemd()


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


def _install_fake_pystemd():
    if "pystemd" in sys.modules:
        return

    pystemd_mod = types.ModuleType("pystemd")
    systemd1_mod = types.ModuleType("pystemd.systemd1")

    class _Unit:
        def __init__(self, *args, **kwargs):
            self.Unit = self

        def load(self):
            return self

    systemd1_mod.Unit = _Unit
    pystemd_mod.systemd1 = systemd1_mod

    sys.modules["pystemd"] = pystemd_mod
    sys.modules["pystemd.systemd1"] = systemd1_mod
