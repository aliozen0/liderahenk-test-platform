package tr.org.lider.services;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import jakarta.annotation.PostConstruct;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import tr.org.lider.entities.PluginImpl;
import tr.org.lider.entities.PluginProfile;
import tr.org.lider.entities.PluginTask;
import tr.org.lider.repositories.PluginProfileRepository;
import tr.org.lider.repositories.PluginRepository;
import tr.org.lider.repositories.PluginTaskRepository;

@Service
public class PluginService {

    private static final Set<String> ACTIVE_PLUGIN_NAMES = Set.of(
        "script",
        "file-management",
        "resource-usage",
        "package-manager",
        "local-user",
        "network-manager",
        "ldap"
    );

    private static final Set<String> ACTIVE_PROFILE_PAGES = Set.of("execute-script-profile");

    @Autowired
    private PluginRepository pluginRepository;

    @Autowired
    private PluginTaskRepository pluginTaskRepository;

    @Autowired
    private PluginProfileRepository pluginProfileRepository;

    @PostConstruct
    private void init() {
        syncPlugins();
        syncTasks();
        syncProfiles();
    }

    private void syncPlugins() {
        Map<String, PluginImpl> desired = new LinkedHashMap<>();
        desired.put("script", plugin("script", "Betik çalıştır", true, true, true, true, false, false));
        desired.put("file-management", plugin("file-management", "Dosya Yönetimi", true, true, true, true, false, false));
        desired.put("resource-usage", plugin("resource-usage", "Kaynak kullanımı", true, false, false, true, false, false));
        desired.put("package-manager", plugin("package-manager", "Paket yönetimi", true, true, true, true, true, false));
        desired.put("local-user", plugin("local-user", "Yerel kullanıcı yönetimi", true, true, true, true, false, false));
        desired.put("network-manager", plugin("network-manager", "Ağ yönetimi", true, true, true, true, false, false));
        desired.put("ldap", plugin("ldap", "İstemci silme, ad değiştirme ve taşıma işlemleri", true, true, false, true, false, false));

        List<PluginImpl> current = new ArrayList<>();
        pluginRepository.findAll().forEach(current::add);
        Map<String, PluginImpl> byName = current.stream()
            .collect(Collectors.toMap(PluginImpl::getName, plugin -> plugin, (left, right) -> left));

        List<PluginImpl> toSave = new ArrayList<>();
        for (Map.Entry<String, PluginImpl> entry : desired.entrySet()) {
            PluginImpl existing = byName.get(entry.getKey());
            if (existing == null) {
                toSave.add(entry.getValue());
                continue;
            }
            copyPlugin(existing, entry.getValue());
            toSave.add(existing);
        }

        for (PluginImpl plugin : current) {
            if (desired.containsKey(plugin.getName())) {
                continue;
            }
            plugin.setActive(false);
            plugin.setTaskPlugin(false);
            plugin.setPolicyPlugin(false);
            plugin.setUsesFileTransfer(false);
            toSave.add(plugin);
        }

        pluginRepository.saveAll(toSave);
    }

    private void syncTasks() {
        List<TaskSeed> desired = List.of(
            task("Dosya İçeriği Görüntüle", "file-management", "İstemcide bulunan dosya içeriğini getirir", "GET_FILE_CONTENT", false, "file-management", 1, "ROLE_FILE_MANAGEMENT"),
            task("Dosya İçeriği Düzenle", "write-to-file", "İstemcide belirtilen dosyanın içeriğini düzenler", "WRITE_TO_FILE", false, "file-management", 1, "ROLE_FILE_MANAGEMENT"),
            task("İstemci Sil", "delete-agent", "İstemciyi siler", "DELETE_AGENT", false, "ldap", 1, "ROLE_CLIENT_MANAGEMENT"),
            task("İstemci Taşı", "move-agent", "İstemciyi taşır", "MOVE_AGENT", true, "ldap", 1, "ROLE_CLIENT_MANAGEMENT"),
            task("İstemci Adını Değiştir", "rename-agent", "İstemci adını değiştirir", "RENAME_ENTRY", false, "ldap", 1, "ROLE_CLIENT_MANAGEMENT"),
            task("Yerel Kullanıcıları Listele", "local-user", "İstemcide bulunan yerel kullanıcıları listeler", "GET_USERS", false, "local-user", 1, "ROLE_LOCAL_USER"),
            task("Yerel Kullanıcı Ekle", "add-local-user", "İstemciye yerel kullanıcı ekler", "ADD_USER", false, "local-user", 1, "ROLE_LOCAL_USER"),
            task("Yerel Kullanıcı Sil", "delete-local-user", "İstemcide bulunan seçilen yerel kullanıcıyı siler", "DELETE_USER", false, "local-user", 1, "ROLE_LOCAL_USER"),
            task("Yerel Kullanıcı Düzenle", "edit-local-user", "İstemcide bulunan seçilen yerel kullanıcı düzenler", "EDIT_USER", false, "local-user", 1, "ROLE_LOCAL_USER"),
            task("Ağ Bilgilerini Getir", "network-manager", "İstemcinin ağ bilgilerini getirir", "GET_NETWORK_INFORMATION", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("DNS Kaydı Ekle", "add-dns", "İstemciye DNS kaydı ekler", "ADD_DNS", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Alan Adı Ekle", "add-domain", "İstemciye alan adı ekler", "ADD_DOMAIN", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Sunucu(Host) Ekle", "add-host", "İstemciye sunucu kaydı ekler", "ADD_HOST", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Ağ Ayarı Ekle", "add-network", "Yeni ağ ayarı ekler", "ADD_NETWORK", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Port İzin Ver", "allow-port", "Seçilen porta izin verir", "ALLOW_PORT", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("DNS Kaydı Sil", "delete-dns", "İstemcide DNS kaydı siler", "DELETE_DNS", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Alan Adı Sil", "delete-domain", "İstemcide bulunan alan adını siler", "DELETE_DOMAIN", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Sunucu(Host) Sil", "delete-host", "İstemcide bulunan sunucu kaydını siler", "DELETE_HOST", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Ağ Ayarı Sil", "delete-network", "İstemcide bulunan ağ ayarını siler", "DELETE_NETWORK", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Bilgisayar Adını Değiştir", "change-hostname", "İstemci bilgisayar adını değiştirir", "CHANGE_HOSTNAME", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Port Engelle", "block-port", "Seçilen portu engeller", "BLOCK_PORT", false, "network-manager", 1, "ROLE_NETWORK_MANAGER"),
            task("Paket Depolarını Getir", "repositories", "İstemcide bulunan paket depolarını listeler", "REPOSITORIES", false, "package-manager", 1, "ROLE_PACKAGE_REPO"),
            task("Paket Deposu Ekle veya Sil", "package-sources", "İstemcide bulunan paket deposunu siler veya yeni depo ekler", "PACKAGE_SOURCES", false, "package-manager", 1, "ROLE_PACKAGE_REPO"),
            task("Paket Kaldır", "package-management", "İstemcide bulunan paket veya paketleri kaldırır", "PACKAGE_MANAGEMENT", false, "package-manager", 1, "ROLE_PACKAGE_LIST"),
            task("Paket Kur veya Kaldır", "packages", "İstenilen paket deposundan istemciye paket kurar veya seçilen paketleri kaldırır", "PACKAGES", true, "package-manager", 1, "ROLE_PACKAGE_INSTALL_REMOVE"),
            task("İstemcideki Paketleri Listele", "installed-packages", "İstemcide bulunan paketleri listeler", "INSTALLED_PACKAGES", false, "package-manager", 1, "ROLE_PACKAGE_LIST"),
            task("Paket Kontrol Et", "check-package", "Paket kontrol eder", "CHECK_PACKAGE", true, "package-manager", 1, "ROLE_PACKAGE_CONTROL"),
            task("Kaynak Kullanımı", "resource-usage", "Anlık kaynak kullanımı bilgilerini getirir", "RESOURCE_INFO_FETCHER", false, "resource-usage", 1, "ROLE_RESOURCE_USAGE"),
            task("İstemci Bilgilerini Güncelle", "agent-info", "İstemci bilgilerini günceller", "AGENT_INFO", false, "resource-usage", 1, "ROLE_RESOURCE_USAGE"),
            task("Betik Çalıştır", "execute-script", "İstemcide betik çalıştırır", "EXECUTE_SCRIPT", true, "script", 1, "ROLE_SCRIPT")
        );

        List<PluginTask> current = new ArrayList<>();
        pluginTaskRepository.findAll().forEach(current::add);
        Map<String, PluginTask> byPage = current.stream()
            .collect(Collectors.toMap(PluginTask::getPage, task -> task, (left, right) -> left));

        List<PluginTask> toSave = new ArrayList<>();
        for (TaskSeed seed : desired) {
            PluginTask existing = byPage.get(seed.page);
            PluginTask task = seed.toEntity(resolvePlugin(seed.pluginName));
            if (existing == null) {
                toSave.add(task);
                continue;
            }
            existing.updateFrom(task);
            toSave.add(existing);
        }

        for (PluginTask task : current) {
            if (desired.stream().anyMatch(seed -> seed.page.equals(task.getPage()))) {
                continue;
            }
            task.setState(0);
            toSave.add(task);
        }

        pluginTaskRepository.saveAll(toSave);
    }

    private void syncProfiles() {
        List<ProfileSeed> desired = List.of(
            profile("Betik Profili", "execute-script-profile", "Betik çalıştır", "EXECUTE_SCRIPT", "script", 1)
        );

        List<PluginProfile> current = new ArrayList<>();
        pluginProfileRepository.findAll().forEach(current::add);
        Map<String, PluginProfile> byPage = current.stream()
            .collect(Collectors.toMap(PluginProfile::getPage, profile -> profile, (left, right) -> left));

        List<PluginProfile> toSave = new ArrayList<>();
        for (ProfileSeed seed : desired) {
            PluginProfile existing = byPage.get(seed.page);
            PluginProfile profile = seed.toEntity(resolvePlugin(seed.pluginName));
            if (existing == null) {
                toSave.add(profile);
                continue;
            }
            existing.setName(profile.getName());
            existing.setPage(profile.getPage());
            existing.setDescription(profile.getDescription());
            existing.setCommandId(profile.getCommandId());
            existing.setPlugin(profile.getPlugin());
            existing.setState(profile.getState());
            toSave.add(existing);
        }

        for (PluginProfile profile : current) {
            if (ACTIVE_PROFILE_PAGES.contains(profile.getPage())) {
                continue;
            }
            profile.setState(0);
            toSave.add(profile);
        }

        pluginProfileRepository.saveAll(toSave);
    }

    public PluginImpl findPluginIdByName(String name) {
        List<PluginImpl> plugin = pluginRepository.findByName(name);
        return plugin.isEmpty() ? null : plugin.get(0);
    }

    public List<PluginImpl> findAllPlugins() {
        return pluginRepository.findAll().stream()
            .filter(PluginImpl::isActive)
            .filter(plugin -> ACTIVE_PLUGIN_NAMES.contains(plugin.getName()))
            .sorted(Comparator.comparing(PluginImpl::getName, String.CASE_INSENSITIVE_ORDER))
            .collect(Collectors.toList());
    }

    public PluginImpl getPlugin(Long id) {
        return pluginRepository.findOne(id);
    }

    public PluginImpl addPlugin(PluginImpl pluginImpl) {
        return pluginRepository.save(pluginImpl);
    }

    public void deletePlugin(PluginImpl pluginImpl) {
        pluginRepository.delete(pluginImpl);
    }

    public PluginImpl updatePlugin(PluginImpl pluginImpl) {
        return pluginRepository.save(pluginImpl);
    }

    public List<PluginImpl> findPluginByNameAndVersion(String name, String version) {
        return pluginRepository.findByNameAndVersion(name, version);
    }

    public List<PluginTask> findAllPluginTask() {
        return pluginTaskRepository.findByState(1).stream()
            .filter(task -> ACTIVE_PLUGIN_NAMES.contains(task.getPlugin().getName()))
            .sorted(Comparator.comparing(PluginTask::getName, String.CASE_INSENSITIVE_ORDER))
            .collect(Collectors.toList());
    }

    public List<PluginProfile> findAllPluginProfile() {
        return pluginProfileRepository.findByState(1).stream()
            .filter(profile -> ACTIVE_PROFILE_PAGES.contains(profile.getPage()))
            .sorted(Comparator.comparing(PluginProfile::getName, String.CASE_INSENSITIVE_ORDER))
            .collect(Collectors.toList());
    }

    public List<PluginImpl> findPluginByName(String name) {
        return pluginRepository.findByName(name);
    }

    public List<PluginTask> findPluginTaskByPage(String page) {
        return pluginTaskRepository.findByPage(page);
    }

    public List<PluginProfile> findPluginProfileByPage(String page) {
        return pluginProfileRepository.findByPage(page);
    }

    private PluginImpl resolvePlugin(String name) {
        PluginImpl plugin = findPluginIdByName(name);
        if (plugin == null) {
            throw new IllegalStateException("Plugin not seeded: " + name);
        }
        return plugin;
    }

    private PluginImpl plugin(
        String name,
        String description,
        boolean machineOriented,
        boolean userOriented,
        boolean policyPlugin,
        boolean taskPlugin,
        boolean usesFileTransfer,
        boolean xBased
    ) {
        return new PluginImpl(name, "1.0.0", description, true, false, machineOriented, userOriented, policyPlugin, taskPlugin, usesFileTransfer, xBased);
    }

    private TaskSeed task(
        String name,
        String page,
        String description,
        String commandId,
        boolean isMulti,
        String pluginName,
        int state,
        String role
    ) {
        return new TaskSeed(name, page, description, commandId, isMulti, pluginName, state, role);
    }

    private ProfileSeed profile(
        String name,
        String page,
        String description,
        String commandId,
        String pluginName,
        int state
    ) {
        return new ProfileSeed(name, page, description, commandId, pluginName, state);
    }

    private void copyPlugin(PluginImpl target, PluginImpl source) {
        target.setName(source.getName());
        target.setVersion(source.getVersion());
        target.setDescription(source.getDescription());
        target.setActive(source.isActive());
        target.setDeleted(false);
        target.setMachineOriented(source.isMachineOriented());
        target.setUserOriented(source.isUserOriented());
        target.setPolicyPlugin(source.isPolicyPlugin());
        target.setTaskPlugin(source.isTaskPlugin());
        target.setUsesFileTransfer(source.isUsesFileTransfer());
        target.setxBased(source.isxBased());
    }

    private static final class TaskSeed {
        private final String name;
        private final String page;
        private final String description;
        private final String commandId;
        private final boolean isMulti;
        private final String pluginName;
        private final int state;
        private final String role;

        private TaskSeed(String name, String page, String description, String commandId, boolean isMulti, String pluginName, int state, String role) {
            this.name = name;
            this.page = page;
            this.description = description;
            this.commandId = commandId;
            this.isMulti = isMulti;
            this.pluginName = pluginName;
            this.state = state;
            this.role = role;
        }

        private PluginTask toEntity(PluginImpl plugin) {
            return new PluginTask(name, page, description, commandId, isMulti, plugin, state, role);
        }
    }

    private static final class ProfileSeed {
        private final String name;
        private final String page;
        private final String description;
        private final String commandId;
        private final String pluginName;
        private final int state;

        private ProfileSeed(String name, String page, String description, String commandId, String pluginName, int state) {
            this.name = name;
            this.page = page;
            this.description = description;
            this.commandId = commandId;
            this.pluginName = pluginName;
            this.state = state;
        }

        private PluginProfile toEntity(PluginImpl plugin) {
            return new PluginProfile(name, page, description, commandId, plugin, state);
        }
    }
}
