from hooks import network_state, runtime


def apply(confirm_mod, anonymous_mod, messaging_mod, execution_mod, registration_mod, util_mod, default_config_mod, system_mod, apt_helper_mod, context):
    agent_id = context["agent_id"]
    agent_hostname = context["agent_hostname"]

    def patched_show_message(message, title="Liderahenk Bildiri"):
        runtime.log(f"UI prompt bypassed: {title}")
        return "no_display"

    confirm_mod.show_message = patched_show_message
    anonymous_mod.show_message = patched_show_message
    messaging_mod.show_message = patched_show_message
    execution_mod.show_message = patched_show_message
    registration_mod.show_message = patched_show_message
    context["patched_show_message"] = patched_show_message

    original_execute = util_mod.Util.execute

    def patched_execute(command, stdin=None, env=None, cwd=None, shell=True, result=True, as_user=None, ip=None, detach=False):
        cmd = str(command).strip()
        lower = cmd.lower()

        if lower.startswith("sudo iptables ") or lower.startswith("iptables "):
            handled = network_state.handle_iptables_command(cmd)
            if handled is not None:
                return handled

        if lower.startswith("systemctl ") or " systemctl " in lower:
            return 0, f"container-mode skipped: {cmd}", ""
        if lower.startswith("pam-auth-update"):
            return 0, f"container-mode skipped: {cmd}", ""
        if lower in ("reboot", "shutdown -h now") or lower.startswith("shutdown "):
            return 0, f"container-mode skipped: {cmd}", ""
        if "dpkg -s ahenk" in lower:
            version = runtime.env("AHENK_VERSION", "2.0.1")
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
            as_user=None if runtime.env("AHENK_RUN_AS_ROOT", "1") == "1" else as_user,
            ip=ip,
            detach=detach,
        )

    util_mod.Util.execute = staticmethod(patched_execute)
    util_mod.Util.shutdown = staticmethod(lambda: runtime.log("shutdown bypassed"))
    util_mod.Util.install_with_dpkg = staticmethod(lambda full_path: runtime.log(f"plugin install bypassed: {full_path}"))
    util_mod.Util.get_agent_version = staticmethod(lambda: runtime.env("AHENK_VERSION", "2.0.1"))

    def apt_install(packages, update_cache=False, run_dpkg_configure=True, versions=None):
        if run_dpkg_configure:
            code, stdout, stderr = runtime.run_subprocess(["dpkg", "--configure", "-a"])
            if code != 0:
                return code, stdout, stderr
        if update_cache:
            code, stdout, stderr = runtime.run_subprocess(["apt-get", "update"])
            if code != 0:
                return code, stdout, stderr
        versions = versions or {}
        targets = []
        for package in packages:
            if package in versions and versions[package]:
                targets.append(f"{package}={versions[package]}")
            else:
                targets.append(package)
        return runtime.run_subprocess(["apt-get", "install", "-y", "--no-install-recommends", *targets])

    def apt_update(run_dpkg_configure=True):
        if run_dpkg_configure:
            code, stdout, stderr = runtime.run_subprocess(["dpkg", "--configure", "-a"])
            if code != 0:
                return code, stdout, stderr
        return runtime.run_subprocess(["apt-get", "update"])

    def apt_remove(packages, purge=False, update_cache=False, run_dpkg_configure=True):
        if run_dpkg_configure:
            code, stdout, stderr = runtime.run_subprocess(["dpkg", "--configure", "-a"])
            if code != 0:
                return code, stdout, stderr
        if update_cache:
            code, stdout, stderr = runtime.run_subprocess(["apt-get", "update"])
            if code != 0:
                return code, stdout, stderr
        cmd = ["apt-get", "purge" if purge else "remove", "-y", *packages]
        return runtime.run_subprocess(cmd)

    apt_helper_mod.AptHelper.install_packages = staticmethod(apt_install)
    apt_helper_mod.AptHelper.update_cache = staticmethod(apt_update)
    apt_helper_mod.AptHelper.remove_packages = staticmethod(apt_remove)

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

    default_config_mod.DefaultConfig.check_sssd_settings = lambda self: runtime.log("SSSD settings skipped in container-mode")
