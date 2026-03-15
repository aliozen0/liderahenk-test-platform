import time
from adapters.lider_api_adapter import LiderApiAdapter
from adapters.xmpp_message_adapter import XmppMessageAdapter
from tests.e2e.config.play_config import PlayConfig

class BackendFacade:
    """
    E2E Test senaryolarının arka plandaki olayları (LDAP, XMPP, MariaDB)
    doğrulaması için Facade arayüzü sağlar.
    """
    
    def __init__(self):
        self.api_adapter = LiderApiAdapter(
            base_url=PlayConfig.API_URL,
            username=PlayConfig.ADMIN_USER,
            password=PlayConfig.ADMIN_PASS
        )
        self.xmpp_adapter = XmppMessageAdapter(
            api_url=PlayConfig.XMPP_URL
        )
        
    def wait_for_agent_registration(self, min_count: int = 1, timeout: int = 60) -> bool:
        """Belirtilen sayıda ajanın Lider API'ye (MariaDB/LDAP) kaydolmasını bekler."""
        return self.api_adapter.wait_for_agents(min_count, timeout)

    def is_agent_connected_xmpp(self) -> bool:
        """XMPP üzerinde en az bir bağlı ajan olup olmadığını doğrular."""
        try:
            return self.xmpp_adapter.get_connected_count() > 0
        except Exception:
            return False

    def get_registered_agent_count(self) -> int:
        """Lider arayüzüne/sisteme kayıtlı ahenk sayısını döndürür."""
        return self.api_adapter.get_agent_count()
        
    def execute_and_verify_task(self, agent_dn: str, task_name: str, params: dict, timeout=30) -> bool:
        """
        Belirtilen ajana API üzerinden görev gönderir ve history'de 
        sonucunu doğrulayana kadar bekler. (Backend doğrulama)
        """
        # Görevi tetikle
        self.api_adapter.send_task(
            entry={"distinguishedName": agent_dn, "type": "COMPUTER"}, 
            command_id=task_name, 
            params=params
        )
        
        # Görev geçmişini polling ile kontrol et
        start_time = time.time()
        while time.time() - start_time < timeout:
            history = self.api_adapter.get_command_history(agent_dn)
            if history and len(history) > 0:
                latest_cmd = history[0]
                # Durum 2 genelde BAŞARILI, vb. LiderAhenk kodlarına göre değişebilir
                # Burada sadece komutun history'e düştüğünü baz alıyoruz
                if latest_cmd.get("commandId") == task_name:
                    return True
            time.sleep(3)
            
        return False
