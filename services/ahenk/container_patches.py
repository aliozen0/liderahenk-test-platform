import json
import os
import sys
import types
import asyncio
import shlex
import subprocess
from datetime import datetime

_APPLIED = False
_NETWORK_POLICY_PATH = "/var/db/network-policy.json"


def _env(name, default=""):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _log(message):
    print(f"[container-patches] {message}", flush=True)


def _load_network_policy():
    default = {"blocked": {"input": [], "output": []}}
    try:
        with open(_NETWORK_POLICY_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        payload = default

    blocked = payload.setdefault("blocked", {})
    for direction in ("input", "output"):
        blocked.setdefault(direction, [])
    return payload


def _save_network_policy(policy):
    os.makedirs(os.path.dirname(_NETWORK_POLICY_PATH), exist_ok=True)
    with open(_NETWORK_POLICY_PATH, "w", encoding="utf-8") as handle:
        json.dump(policy, handle, indent=2, sort_keys=True)


def _extract_port_from_iptables(parts):
    for idx, part in enumerate(parts):
        if part == "--dport" and idx + 1 < len(parts):
            return parts[idx + 1]
        if part.startswith("--dport="):
            return part.split("=", 1)[1]
    return None


def _render_iptables_list():
    policy = _load_network_policy()
    lines = [
        "Chain INPUT",
    ]
    for port in sorted(set(policy["blocked"]["input"])):
        lines.append(f"DROP       tcp  --  anywhere             anywhere             tcp dpt:{port}")
    lines.append("Chain OUTPUT")
    for port in sorted(set(policy["blocked"]["output"])):
        lines.append(f"DROP       tcp  --  anywhere             anywhere             tcp dpt:{port}")
    return "\n".join(lines) + "\n"


def _handle_iptables_command(command):
    parts = shlex.split(str(command))
    if parts and parts[0] == "sudo":
        parts = parts[1:]
    if not parts:
        return None

    if parts[0] == "iptables-save":
        return 0, "", ""

    if parts[0] != "iptables":
        return None

    if "-L" in parts:
        return 0, _render_iptables_list(), ""

    action = None
    direction = None
    for idx, part in enumerate(parts):
        if part in ("-A", "-D") and idx + 1 < len(parts):
            action = part
            direction = parts[idx + 1].strip().lower()
            break

    port = _extract_port_from_iptables(parts)
    if action and direction in {"input", "output"} and port:
        policy = _load_network_policy()
        blocked = set(policy["blocked"][direction])
        if action == "-A":
            blocked.add(port)
        else:
            blocked.discard(port)
        policy["blocked"][direction] = sorted(blocked, key=lambda item: int(item))
        _save_network_policy(policy)
        return 0, "", ""

    return 0, "", ""


def _run_subprocess(cmd):
    env = dict(os.environ)
    env["DEBIAN_FRONTEND"] = "noninteractive"
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def _configure_plain_xmpp(client):
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


def apply():
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    agent_id = _env("AGENT_ID", "ahenk-001")
    agent_hostname = _env("AGENT_HOSTNAME", f"{agent_id}-host")
    agent_password = _env("AGENT_XMPP_PASS", _env("XMPP_AGENT_PASS", _env("XMPP_ADMIN_PASS", "secret")))

    _install_fake_apt()

    from slixmpp import ClientXMPP

    import base.agreement.confirm as confirm_mod
    import base.default_config.default_config as default_config_mod
    import base.execution.execution_manager as execution_mod
    import base.messaging.anonymous_messenger as anonymous_mod
    import base.messaging.messenger as messenger_mod
    import base.messaging.messaging as messaging_mod
    import base.registration.registration as registration_mod
    import base.system.system as system_mod
    import base.util.apt_helper as apt_helper_mod
    import base.util.util as util_mod
    from base.scope import Scope

    def patched_show_message(message, title="Liderahenk Bildiri"):
        _log(f"UI prompt bypassed: {title}")
        return "no_display"

    confirm_mod.show_message = patched_show_message
    anonymous_mod.show_message = patched_show_message
    messaging_mod.show_message = patched_show_message
    execution_mod.show_message = patched_show_message
    registration_mod.show_message = patched_show_message

    original_execute = util_mod.Util.execute

    def patched_execute(command, stdin=None, env=None, cwd=None, shell=True, result=True, as_user=None, ip=None, detach=False):
        cmd = str(command).strip()
        lower = cmd.lower()

        if lower.startswith("sudo iptables ") or lower.startswith("iptables "):
            handled = _handle_iptables_command(cmd)
            if handled is not None:
                return handled

        if lower.startswith("systemctl ") or " systemctl " in lower:
            return 0, f"container-mode skipped: {cmd}", ""
        if lower.startswith("pam-auth-update"):
            return 0, f"container-mode skipped: {cmd}", ""
        if lower in ("reboot", "shutdown -h now") or lower.startswith("shutdown "):
            return 0, f"container-mode skipped: {cmd}", ""
        if "dpkg -s ahenk" in lower:
            version = _env("AHENK_VERSION", "2.0.1")
            return 0, f"Version: {version}\n", ""
        if "dmidecode --string bios-vendor" in lower:
            return 0, "Container Vendor\n", ""
        if "dmidecode --string bios-release-date" in lower:
            return 0, "2026-02-23\n", ""
        if "dmidecode --string bios-version" in lower:
            return 0, "container-bios-1.0\n", ""
        if "dmidecode --string baseboard-manufacturer" in lower:
            return 0, "Container Vendor\n", ""
        if "dmidecode --string baseboard-product-name" in lower:
            return 0, "Container Board\n", ""
        if "dmidecode --string baseboard-version" in lower:
            return 0, "1.0\n", ""
        if "dmidecode --string baseboard-serial-number" in lower:
            return 0, f"{agent_id}-board\n", ""
        if "dmidecode --string baseboard-asset-tag" in lower:
            return 0, "container-asset-tag\n", ""
        if "dmidecode -t system" in lower:
            body = "\n".join(
                [
                    "System Information",
                    "Manufacturer: Container Vendor",
                    f"Product Name: {agent_hostname}",
                    "Version: container-1.0",
                ]
            )
            return 0, body + "\n", ""
        if "dmidecode --string system-version" in lower:
            return 0, f"{agent_hostname}\n", ""
        if lower.startswith("xrandr"):
            return 0, "", ""
        if lower.startswith("lsusb"):
            return 0, "", ""
        if lower.startswith("lpstat -a"):
            return 0, "", ""
        if "parse-edid" in lower:
            return 1, "", "parse-edid unavailable in container-mode"

        return original_execute(
            command,
            stdin=stdin,
            env=env,
            cwd=cwd,
            shell=shell,
            result=result,
            as_user=None if _env("AHENK_RUN_AS_ROOT", "1") == "1" else as_user,
            ip=ip,
            detach=detach,
        )

    util_mod.Util.execute = staticmethod(patched_execute)
    util_mod.Util.shutdown = staticmethod(lambda: _log("shutdown bypassed"))
    util_mod.Util.install_with_dpkg = staticmethod(lambda full_path: _log(f"plugin install bypassed: {full_path}"))
    util_mod.Util.get_agent_version = staticmethod(lambda: _env("AHENK_VERSION", "2.0.1"))

    def _apt_install(packages, update_cache=False, run_dpkg_configure=True, versions=None):
        if run_dpkg_configure:
            code, stdout, stderr = _run_subprocess(["dpkg", "--configure", "-a"])
            if code != 0:
                return code, stdout, stderr
        if update_cache:
            code, stdout, stderr = _run_subprocess(["apt-get", "update"])
            if code != 0:
                return code, stdout, stderr

        versions = versions or {}
        targets = []
        for package in packages:
            if package in versions and versions[package]:
                targets.append(f"{package}={versions[package]}")
            else:
                targets.append(package)
        return _run_subprocess(["apt-get", "install", "-y", "--no-install-recommends", *targets])

    def _apt_update(run_dpkg_configure=True):
        if run_dpkg_configure:
            code, stdout, stderr = _run_subprocess(["dpkg", "--configure", "-a"])
            if code != 0:
                return code, stdout, stderr
        return _run_subprocess(["apt-get", "update"])

    def _apt_remove(packages, purge=False, update_cache=False, run_dpkg_configure=True):
        if run_dpkg_configure:
            code, stdout, stderr = _run_subprocess(["dpkg", "--configure", "-a"])
            if code != 0:
                return code, stdout, stderr
        if update_cache:
            code, stdout, stderr = _run_subprocess(["apt-get", "update"])
            if code != 0:
                return code, stdout, stderr
        cmd = ["apt-get", "purge" if purge else "remove", "-y", *packages]
        return _run_subprocess(cmd)

    apt_helper_mod.AptHelper.install_packages = staticmethod(_apt_install)
    apt_helper_mod.AptHelper.update_cache = staticmethod(_apt_update)
    apt_helper_mod.AptHelper.remove_packages = staticmethod(_apt_remove)

    system_mod.System.Ahenk.pid_path = staticmethod(lambda: "/var/db/ahenk.pid")
    system_mod.System.Os.hostname = staticmethod(lambda: agent_hostname)
    system_mod.System.Hardware.monitors = staticmethod(lambda: [])
    system_mod.System.Hardware.screens = staticmethod(lambda: [])
    system_mod.System.Hardware.usb_devices = staticmethod(lambda: [])
    system_mod.System.Hardware.printers = staticmethod(lambda: [])
    system_mod.System.Hardware.system_definitions = staticmethod(
        lambda: ["Manufacturer: Container Vendor", f"Product Name: {agent_hostname}"]
    )
    system_mod.System.Hardware.machine_model = staticmethod(lambda: agent_hostname)
    system_mod.System.BIOS.vendor = staticmethod(lambda: (0, "Container Vendor\n", ""))
    system_mod.System.BIOS.release_date = staticmethod(lambda: (0, "2026-02-23\n", ""))
    system_mod.System.BIOS.version = staticmethod(lambda: (0, "container-bios-1.0\n", ""))
    system_mod.System.Hardware.BaseBoard.manufacturer = staticmethod(lambda: (0, "Container Vendor\n", ""))
    system_mod.System.Hardware.BaseBoard.product_name = staticmethod(lambda: (0, "Container Board\n", ""))
    system_mod.System.Hardware.BaseBoard.version = staticmethod(lambda: (0, "1.0\n", ""))
    system_mod.System.Hardware.BaseBoard.serial_number = staticmethod(lambda: (0, f"{agent_id}-board\n", ""))
    system_mod.System.Hardware.BaseBoard.asset_tag = staticmethod(lambda: (0, "container-asset-tag\n", ""))

    default_config_mod.DefaultConfig.check_sssd_settings = lambda self: _log("SSSD settings skipped in container-mode")

    def patched_install_plugin(self, arg):
        self.logger.warning("INSTALL_PLUGIN ignored in container-mode")

    execution_mod.ExecutionManager.install_plugin = patched_install_plugin

    original_send_direct_message = messenger_mod.Messenger.send_direct_message

    def patched_send_direct_message(self, msg):
        if str(msg) == "test":
            self.logger.debug("Ignoring upstream bootstrap test message")
            return
        return original_send_direct_message(self, msg)

    messenger_mod.Messenger.send_direct_message = patched_send_direct_message

    def patched_recv_direct_message(self, msg):
        if msg["type"] not in ["normal"]:
            return

        try:
            self.logger.info("Reading registration reply")
            body_text = str(msg["body"])
            self.logger.debug(f"Registration raw body: {body_text}")
            payload = json.loads(body_text)
            message_type = payload["type"]
            status = str(payload.get("status", "")).lower()
            self.logger.debug(f"Registration status: {status}")

            safe_payload = dict(payload)
            redacted = False
            for key in list(safe_payload.keys()):
                if "password" in key.lower():
                    safe_payload[key] = "********"
                    redacted = True
            if redacted:
                self.logger.info(f"---------->Received message: {safe_payload}")
            else:
                self.logger.info(f"---------->Received message: {body_text}")

            if status in {"registered", "registered_without_ldap", "already_exists"}:
                if status == "already_exists":
                    self.logger.info("Container-mode accepted ALREADY_EXISTS as successful registration")
                try:
                    self.event_manager.fireEvent("REGISTRATION_SUCCESS", payload)
                    self.logger.info("Disconnecting after successful registration...")
                    self.disconnect()
                    if hasattr(self, "_event_loop"):
                        try:
                            loop = self._event_loop
                            if not loop.is_closed():
                                loop.call_soon_threadsafe(loop.stop)
                        except Exception as exc:
                            self.logger.warning(f"Error stopping event loop: {exc}")
                    util_mod.Util.shutdown()
                except Exception as exc:
                    self.logger.exception(f"Registration success handler failed: {exc}")
                    self.disconnect()
                return

            if status == "not_authorized":
                self.logger.debug("[REGISTRATION IS FAILED]. User not authorized")
                patched_show_message(
                    "Bilgisayar Lider MYS ye alınamadı! Sadece yetkili kullanıcılar kayıt yapabilir.",
                    "Kullanıcı Yetkilendirme Hatası",
                )
                self.logger.debug("Disconnecting...")
                self.disconnect()
                if hasattr(self, "_event_loop"):
                    try:
                        loop = self._event_loop
                        if not loop.is_closed():
                            loop.call_soon_threadsafe(loop.stop)
                    except Exception as exc:
                        self.logger.warning(f"Error stopping event loop: {exc}")
                return

            if status == "registration_error":
                self.logger.info("[REGISTRATION IS FAILED] - New registration request will send")
                patched_show_message(
                    "Ahenk Lider MYS ye alınamadı. Kayıt esnasında hata oluştu. Lütfen sistem yöneticinize başvurunuz",
                    "Sistem Hatası",
                )
                self.logger.debug("Disconnecting...")
                self.disconnect()
                if hasattr(self, "_event_loop"):
                    try:
                        loop = self._event_loop
                        if not loop.is_closed():
                            loop.call_soon_threadsafe(loop.stop)
                    except Exception as exc:
                        self.logger.warning(f"Error stopping event loop: {exc}")
                return

            self.event_manager.fireEvent(message_type, body_text)
            self.logger.debug(f"Fired event is: {message_type}")
        except Exception as exc:
            self.logger.exception(f"Registration reply handler crashed: {exc}")
            return

    anonymous_mod.AnonymousMessenger.recv_direct_message = patched_recv_direct_message

    def patched_register(self, uuid_depend_mac=False):
        timestamp = datetime.now().strftime("%d-%m-%Y %I:%M")
        try:
            params = self.get_registration_params()
        except Exception as exc:
            _log(f"registration params fallback engaged: {exc}")
            params = {}

        params["hostname"] = agent_hostname
        params["ipAddresses"] = params.get("ipAddresses") or ", ".join(system_mod.System.Hardware.Network.ip_addresses())
        params["macAddresses"] = params.get("macAddresses") or ", ".join(system_mod.System.Hardware.Network.mac_addresses())

        cols = ["jid", "password", "registered", "params", "timestamp"]
        vals = [agent_id, agent_password, 0, json.dumps(params), timestamp]
        self.db_service.delete("registration", "1==1")
        self.db_service.update("registration", cols, vals)
        self.logger.debug("Container-mode registration parameters were created")

    registration_mod.Registration.register = patched_register

    def patched_registration_success(self, reg_reply):
        dn = str(reg_reply.get("agentDn") or "")
        self.directory_server = reg_reply.get("directoryServer", _env("DOMAIN_TYPE", "LDAP"))

        if self.conf_manager.has_section("MACHINE"):
            user_disabled = "true" if reg_reply.get("disableLocalUser", False) else "false"
            self.conf_manager.set("MACHINE", "user_disabled", user_disabled)

        self.db_service.update("registration", ["dn", "registered"], [dn, 1], "1==1")

        if self.conf_manager.has_section("CONNECTION"):
            self.conf_manager.set("CONNECTION", "uid", agent_id)
            self.conf_manager.set("CONNECTION", "password", agent_password)
            self.conf_manager.set("CONNECTION", "host", _env("XMPP_HOST", self.conf_manager.get("CONNECTION", "host")))
            self.conf_manager.set(
                "CONNECTION",
                "servicename",
                _env("XMPP_DOMAIN", self.conf_manager.get("CONNECTION", "servicename")),
            )

            with open("/etc/ahenk/ahenk.conf", "w") as configfile:
                self.conf_manager.write(configfile)

        self.logger.info(f"Container-mode registration completed for {agent_id} dn={dn}")

    registration_mod.Registration.registration_success = patched_registration_success

    def patched_anonymous_init(self, message, host=None, servicename=None):
        scope = Scope().get_instance()

        self.logger = scope.get_logger()
        self.configuration_manager = scope.get_configuration_manager()
        self.registration = scope.get_registration()
        self.event_manager = scope.get_event_manager()

        self.host = str(host or self.configuration_manager.get("CONNECTION", "host"))
        self.service = str(servicename or self.configuration_manager.get("CONNECTION", "servicename"))
        self.port = int(self.configuration_manager.get("CONNECTION", "port"))

        jid = f"{agent_id}@{self.service}"
        ClientXMPP.__init__(self, jid, agent_password)
        _configure_plain_xmpp(self)

        self.message = message
        self.receiver_resource = self.configuration_manager.get("CONNECTION", "receiverresource")
        self.receiver = (
            self.configuration_manager.get("CONNECTION", "receiverjid")
            + "@"
            + self.configuration_manager.get("CONNECTION", "servicename")
        )
        if self.receiver_resource:
            self.receiver += "/" + self.receiver_resource

        self.add_listeners()
        self.register_extensions()

    anonymous_mod.AnonymousMessenger.__init__ = patched_anonymous_init

    original_messenger_init = messenger_mod.Messenger.__init__

    def patched_messenger_init(self):
        original_messenger_init(self)
        _configure_plain_xmpp(self)
        self.ca_certs = None

    messenger_mod.Messenger.__init__ = patched_messenger_init

    def patched_messenger_connect_to_server(self):
        try:
            try:
                self.register_plugin("feature_mechanisms")
                if "feature_mechanisms" in self.plugin:
                    self["feature_mechanisms"].unencrypted_plain = True
                    self["feature_mechanisms"].unencrypted_scram = True
                    self.logger.debug("Plain auth enabled")
            except Exception as plugin_error:
                self.logger.warning(f"Could not configure plain auth: {plugin_error}")

            loop = asyncio.new_event_loop()
            self._event_loop = loop
            self._loop = loop

            self._event_loop_thread = messenger_mod.threading.Thread(
                target=self._run_event_loop,
                args=(loop,),
                daemon=True,
            )
            self._event_loop_thread.start()
            self.logger.debug("Event loop thread started")

            messenger_mod.time.sleep(0.1)
            self.logger.debug(f"Starting connection... Host: {self.hostname}, Port: {self.port}")

            async def connect_async():
                try:
                    connect_future = self.connect(host=self.hostname, port=int(self.port))
                    await connect_future
                    self.logger.debug("Socket connected, waiting for session_start event...")
                    try:
                        await self.wait_until("session_start", timeout=30)
                        self.logger.debug("Connection were established successfully")
                        self._connected = True
                        return True
                    except asyncio.TimeoutError:
                        self.logger.error("Connection failed - session_start timeout")
                        self._connected = False
                        return False
                    except Exception as session_error:
                        self.logger.error(f"Session start error: {session_error}")
                        self._connected = False
                        return False
                except Exception as exc:
                    self.logger.error(f"Connection error: {exc}")
                    self._connected = False
                    return False

            future = asyncio.run_coroutine_threadsafe(connect_async(), loop)
            try:
                result = future.result(timeout=35)
                if result:
                    self.logger.info("XMPP connection established successfully")
                    return True
                self.logger.error("XMPP connection failed")
                return False
            except Exception as exc:
                self.logger.error(f"Connection future error: {exc}")
                return False
        except Exception as exc:
            self.logger.exception(f"Connection to server is failed! Error Message: {exc}")
            return False

    messenger_mod.Messenger.connect_to_server = patched_messenger_connect_to_server

    _log(f"runtime patches active for {agent_id}")
