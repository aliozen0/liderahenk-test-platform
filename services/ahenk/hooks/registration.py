import json
from datetime import datetime

from hooks import runtime


def apply(anonymous_mod, registration_mod, util_mod, system_mod, Scope, ClientXMPP, context):
    agent_id = context["agent_id"]
    agent_hostname = context["agent_hostname"]
    agent_password = context["agent_password"]
    patched_show_message = context["patched_show_message"]

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

    anonymous_mod.AnonymousMessenger.recv_direct_message = patched_recv_direct_message

    def patched_register(self, uuid_depend_mac=False):
        timestamp = datetime.now().strftime("%d-%m-%Y %I:%M")
        try:
            params = self.get_registration_params()
        except Exception as exc:
            runtime.log(f"registration params fallback engaged: {exc}")
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
        self.directory_server = reg_reply.get("directoryServer", runtime.env("DOMAIN_TYPE", "LDAP"))

        if self.conf_manager.has_section("MACHINE"):
            user_disabled = "true" if reg_reply.get("disableLocalUser", False) else "false"
            self.conf_manager.set("MACHINE", "user_disabled", user_disabled)

        self.db_service.update("registration", ["dn", "registered"], [dn, 1], "1==1")

        if self.conf_manager.has_section("CONNECTION"):
            self.conf_manager.set("CONNECTION", "uid", agent_id)
            self.conf_manager.set("CONNECTION", "password", agent_password)
            self.conf_manager.set("CONNECTION", "host", runtime.env("XMPP_HOST", self.conf_manager.get("CONNECTION", "host")))
            self.conf_manager.set("CONNECTION", "servicename", runtime.env("XMPP_DOMAIN", self.conf_manager.get("CONNECTION", "servicename")))

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
        runtime.configure_plain_xmpp(self)

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
