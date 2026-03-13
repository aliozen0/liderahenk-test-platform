#!/usr/bin/env python3
import asyncio
import logging
import os
import time
import json
import configparser

import slixmpp

logging.basicConfig(level=logging.DEBUG, format="%(levelname)-8s %(message)s")

class AhenkAgent(slixmpp.ClientXMPP):
    def __init__(self, jid, password, host, port, agent_index, lider_jid):
        super().__init__(jid, password)
        
        self.agent_index = agent_index
        self.hostname = f"ahenk-{self.agent_index:03d}"
        self.ip_address = f"172.25.0.{100 + self.agent_index}"
        
        self.xmpp_host = host
        self.xmpp_port = port
        self.lider_jid = lider_jid
        
        # Add event handlers
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("disconnected", self.on_disconnect)
        self.add_event_handler("connection_failed", self.on_connection_failed)
        
        # Disable TLS cert verification for local dev (if server supports starttls with self-signed)
        self.ca_certs = None

    async def start(self, event):
        self.send_presence()
        self.get_roster()
        
        # Register after connection
        self.send_register()
        
        # Start heartbeat
        asyncio.create_task(self.heartbeat_loop())

    def send_register(self):
        mac = f"aa:bb:cc:dd:ee:{self.agent_index:02x}"
        
        payload = {
            "type": "REGISTER",
            "from": str(self.boundjid),
            "password": os.environ.get("XMPP_ADMIN_PASS", "secret"),
            "userName": os.environ.get("LIDER_USER", "lider-admin"),
            "userPassword": os.environ.get("LIDER_PASS", "secret"),
            "hostname": self.hostname,
            "ipAddresses": self.ip_address,
            "macAddresses": mac,
            "timestamp": int(time.time() * 1000)
        }
        
        msg = self.make_message(mto=self.lider_jid, mbody=json.dumps(payload), mtype="normal")
        msg.send()
        logging.info(f"[{self.hostname}] REGISTER message sent to {self.lider_jid}.")
        
    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(60)
            payload = {
                "type": "HEARTBEAT",
                "jid": self.boundjid.bare,
                "timestamp": str(int(time.time() * 1000))
            }
            msg = self.make_message(mto=self.lider_jid, mbody=json.dumps(payload), mtype="normal")
            msg.send()
            logging.info(f"[{self.hostname}] HEARTBEAT message sent.")

    def on_disconnect(self, event):
        logging.warning(f"[{self.hostname}] Disconnected from server.")

    def on_connection_failed(self, event):
        logging.error(f"[{self.hostname}] Connection failed.")

def main():
    config = configparser.ConfigParser()
    config.read("/etc/ahenk/ahenk.conf")
    
    # Try config or fallbacks
    domain   = config.get("CONNECTION", "domain",   fallback="liderahenk.org")
    host     = config.get("CONNECTION", "host",     fallback="ejabberd")
    port     = int(config.get("CONNECTION", "port",  fallback="5222"))
    
    # From environment
    agent_index = int(os.environ.get("AGENT_INDEX", "1"))
    password = os.environ.get("XMPP_ADMIN_PASS", "secret")
    xmpp_domain = os.environ.get("XMPP_DOMAIN", "liderahenk.org")
    xmpp_resource = os.environ.get("XMPP_RESOURCE", "LiderAPI")
    
    username = f"ahenk-{agent_index:03d}"
    jid = f"{username}@{domain}"
    lider_jid = f"lider_sunucu@{xmpp_domain}/{xmpp_resource}"
    
    logging.info(f"Starting AhenkAgent with JID: {jid} to server {host}:{port}")
    logging.info(f"Lider target JID: {lider_jid}")
    xmpp = AhenkAgent(jid, password, host, port, agent_index, lider_jid)
    xmpp.enable_direct_tls = False
    xmpp.enable_starttls = False
    xmpp.enable_plaintext = True
    xmpp['feature_mechanisms'].unencrypted_plain = True
    xmpp['feature_mechanisms'].unencrypted_scram = True

    
    # Optional flags
    xmpp.register_plugin('xep_0030') # Service Discovery
    xmpp.register_plugin('xep_0199') # XMPP Ping
    
    # Connect and process
    try:
        xmpp.connect(host=host, port=port)
        xmpp.loop.run_forever()
    except KeyboardInterrupt:
        logging.info("Interrupted. Exiting...")
        xmpp.disconnect()

if __name__ == "__main__":
    main()
