def apply(execution_mod, messenger_mod):
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
