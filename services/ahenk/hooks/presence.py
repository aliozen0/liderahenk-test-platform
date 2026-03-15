import asyncio

from hooks import runtime


def apply(messenger_mod):
    original_messenger_init = messenger_mod.Messenger.__init__

    def patched_messenger_init(self):
        original_messenger_init(self)
        runtime.configure_plain_xmpp(self)
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
