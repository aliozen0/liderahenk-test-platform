package tr.org.lider.platform.catalog;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

@Component
public class V1CatalogSeedService {

    public Map<String, PluginSeed> desiredPlugins() {
        Map<String, PluginSeed> desired = new LinkedHashMap<>();
        desired.put("script", new PluginSeed("script", "Betik çalıştır", true, true, true, true, false, false));
        desired.put("file-management", new PluginSeed("file-management", "Dosya Yönetimi", true, true, true, true, false, false));
        desired.put("resource-usage", new PluginSeed("resource-usage", "Kaynak kullanımı", true, false, false, true, false, false));
        desired.put("package-manager", new PluginSeed("package-manager", "Paket yönetimi", true, true, true, true, true, false));
        desired.put("local-user", new PluginSeed("local-user", "Yerel kullanıcı yönetimi", true, true, true, true, false, false));
        desired.put("network-manager", new PluginSeed("network-manager", "Ağ yönetimi", true, true, true, true, false, false));
        desired.put("ldap", new PluginSeed("ldap", "İstemci silme, ad değiştirme ve taşıma işlemleri", true, true, false, true, false, false));
        return desired;
    }

    public List<TaskSeed> desiredTasks() {
        return List.of(
            new TaskSeed("Dosya İçeriği Görüntüle", "file-management", "İstemcide bulunan dosya içeriğini getirir", "GET_FILE_CONTENT", false, "file-management", 1, "ROLE_FILE_MANAGEMENT"),
            new TaskSeed("Dosya İçeriği Düzenle", "write-to-file", "İstemcide belirtilen dosyanın içeriğini düzenler", "WRITE_TO_FILE", false, "file-management", 1, "ROLE_FILE_MANAGEMENT"),
            new TaskSeed("İstemci Sil", "delete-agent", "İstemciyi siler", "DELETE_AGENT", false, "ldap", 1, "ROLE_CLIENT_MANAGEMENT"),
            new TaskSeed("İstemci Taşı", "move-agent", "İstemciyi taşır", "MOVE_AGENT", true, "ldap", 1, "ROLE_CLIENT_MANAGEMENT"),
            new TaskSeed("İstemci Adını Değiştir", "rename-agent", "İstemci adını değiştirir", "RENAME_ENTRY", false, "ldap", 1, "ROLE_CLIENT_MANAGEMENT"),
            new TaskSeed("Yerel Kullanıcıları Listele", "local-user", "İstemcide bulunan yerel kullanıcıları listeler", "GET_USERS", false, "local-user", 1, "ROLE_LOCAL_USER"),
            new TaskSeed("Yerel Kullanıcı Ekle", "add-local-user", "İstemciye yerel kullanıcı ekler", "ADD_USER", false, "local-user", 1, "ROLE_LOCAL_USER"),
            new TaskSeed("Yerel Kullanıcı Sil", "delete-local-user", "İstemcide bulunan seçilen yerel kullanıcıyı siler", "DELETE_USER", false, "local-user", 1, "ROLE_LOCAL_USER"),
            new TaskSeed("Yerel Kullanıcı Düzenle", "edit-local-user", "İstemcide bulunan seçilen yerel kullanıcı düzenler", "EDIT_USER", false, "local-user", 1, "ROLE_LOCAL_USER"),
            new TaskSeed("Ağ Bilgilerini Getir", "network-manager", "İstemcinin ağ bilgilerini getirir", "GET_NETWORK_INFORMATION", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("DNS Kaydı Ekle", "add-dns", "İstemciye DNS kaydı ekler", "ADD_DNS", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Alan Adı Ekle", "add-domain", "İstemciye alan adı ekler", "ADD_DOMAIN", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Sunucu(Host) Ekle", "add-host", "İstemciye sunucu kaydı ekler", "ADD_HOST", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Ağ Ayarı Ekle", "add-network", "Yeni ağ ayarı ekler", "ADD_NETWORK", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Port İzin Ver", "allow-port", "Seçilen porta izin verir", "ALLOW_PORT", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("DNS Kaydı Sil", "delete-dns", "İstemcide DNS kaydı siler", "DELETE_DNS", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Alan Adı Sil", "delete-domain", "İstemcide bulunan alan adını siler", "DELETE_DOMAIN", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Sunucu(Host) Sil", "delete-host", "İstemcide bulunan sunucu kaydını siler", "DELETE_HOST", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Ağ Ayarı Sil", "delete-network", "İstemcide bulunan ağ ayarını siler", "DELETE_NETWORK", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Bilgisayar Adını Değiştir", "change-hostname", "İstemci bilgisayar adını değiştirir", "CHANGE_HOSTNAME", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Port Engelle", "block-port", "Seçilen portu engeller", "BLOCK_PORT", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            new TaskSeed("Paket Depolarını Getir", "repositories", "İstemcide bulunan paket depolarını listeler", "REPOSITORIES", false, "package-manager", 1, "ROLE_PACKAGE_REPO"),
            new TaskSeed("Paket Deposu Ekle veya Sil", "package-sources", "İstemcide bulunan paket deposunu siler veya yeni depo ekler", "PACKAGE_SOURCES", false, "package-manager", 1, "ROLE_PACKAGE_REPO"),
            new TaskSeed("Paket Kaldır", "package-management", "İstemcide bulunan paket veya paketleri kaldırır", "PACKAGE_MANAGEMENT", false, "package-manager", 1, "ROLE_PACKAGE_LIST"),
            new TaskSeed("Paket Kur veya Kaldır", "packages", "İstenilen paket deposundan istemciye paket kurar veya seçilen paketleri kaldırır", "PACKAGES", true, "package-manager", 1, "ROLE_PACKAGE_INSTALL_REMOVE"),
            new TaskSeed("İstemcideki Paketleri Listele", "installed-packages", "İstemcide bulunan paketleri listeler", "INSTALLED_PACKAGES", false, "package-manager", 1, "ROLE_PACKAGE_LIST"),
            new TaskSeed("Paket Kontrol Et", "check-package", "Paket kontrol eder", "CHECK_PACKAGE", true, "package-manager", 1, "ROLE_PACKAGE_CONTROL"),
            new TaskSeed("Kaynak Kullanımı", "resource-usage", "Anlık kaynak kullanımı bilgilerini getirir", "RESOURCE_INFO_FETCHER", false, "resource-usage", 1, "ROLE_RESOURCE_USAGE"),
            new TaskSeed("İstemci Bilgilerini Güncelle", "agent-info", "İstemci bilgilerini günceller", "AGENT_INFO", false, "resource-usage", 1, "ROLE_RESOURCE_USAGE"),
            new TaskSeed("Betik Çalıştır", "execute-script", "İstemcide betik çalıştırır", "EXECUTE_SCRIPT", true, "script", 1, "ROLE_SCRIPT")
        );
    }

    public List<ProfileSeed> desiredProfiles() {
        return List.of(
            new ProfileSeed("Betik Profili", "execute-script-profile", "Betik çalıştır", "EXECUTE_SCRIPT", "script", 1)
        );
    }

    public static final class PluginSeed {
        private final String name;
        private final String description;
        private final boolean machineOriented;
        private final boolean userOriented;
        private final boolean policyPlugin;
        private final boolean taskPlugin;
        private final boolean usesFileTransfer;
        private final boolean xBased;

        public PluginSeed(String name, String description, boolean machineOriented, boolean userOriented, boolean policyPlugin, boolean taskPlugin, boolean usesFileTransfer, boolean xBased) {
            this.name = name;
            this.description = description;
            this.machineOriented = machineOriented;
            this.userOriented = userOriented;
            this.policyPlugin = policyPlugin;
            this.taskPlugin = taskPlugin;
            this.usesFileTransfer = usesFileTransfer;
            this.xBased = xBased;
        }

        public String getName() { return name; }
        public String getDescription() { return description; }
        public boolean isMachineOriented() { return machineOriented; }
        public boolean isUserOriented() { return userOriented; }
        public boolean isPolicyPlugin() { return policyPlugin; }
        public boolean isTaskPlugin() { return taskPlugin; }
        public boolean isUsesFileTransfer() { return usesFileTransfer; }
        public boolean isXBased() { return xBased; }
    }

    public static final class TaskSeed {
        private final String name;
        private final String page;
        private final String description;
        private final String commandId;
        private final boolean multi;
        private final String pluginName;
        private final int state;
        private final String role;

        public TaskSeed(String name, String page, String description, String commandId, boolean multi, String pluginName, int state, String role) {
            this.name = name;
            this.page = page;
            this.description = description;
            this.commandId = commandId;
            this.multi = multi;
            this.pluginName = pluginName;
            this.state = state;
            this.role = role;
        }

        public String getName() { return name; }
        public String getPage() { return page; }
        public String getDescription() { return description; }
        public String getCommandId() { return commandId; }
        public boolean isMulti() { return multi; }
        public String getPluginName() { return pluginName; }
        public int getState() { return state; }
        public String getRole() { return role; }
    }

    public static final class ProfileSeed {
        private final String name;
        private final String page;
        private final String description;
        private final String commandId;
        private final String pluginName;
        private final int state;

        public ProfileSeed(String name, String page, String description, String commandId, String pluginName, int state) {
            this.name = name;
            this.page = page;
            this.description = description;
            this.commandId = commandId;
            this.pluginName = pluginName;
            this.state = state;
        }

        public String getName() { return name; }
        public String getPage() { return page; }
        public String getDescription() { return description; }
        public String getCommandId() { return commandId; }
        public String getPluginName() { return pluginName; }
        public int getState() { return state; }
    }
}
