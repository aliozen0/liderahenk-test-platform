package tr.org.lider.services;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import jakarta.annotation.PostConstruct;

import org.springframework.stereotype.Service;

import tr.org.lider.entities.PluginImpl;
import tr.org.lider.entities.PluginProfile;
import tr.org.lider.entities.PluginTask;
import tr.org.lider.platform.catalog.FeatureCatalogProvider;
import tr.org.lider.platform.catalog.V1CatalogSeedService;
import tr.org.lider.platform.catalog.V1CatalogSeedService.PluginSeed;
import tr.org.lider.platform.catalog.V1CatalogSeedService.ProfileSeed;
import tr.org.lider.platform.catalog.V1CatalogSeedService.TaskSeed;
import tr.org.lider.repositories.PluginProfileRepository;
import tr.org.lider.repositories.PluginRepository;
import tr.org.lider.repositories.PluginTaskRepository;

@Service
public class PluginService {

    private final PluginRepository pluginRepository;
    private final PluginTaskRepository pluginTaskRepository;
    private final PluginProfileRepository pluginProfileRepository;
    private final FeatureCatalogProvider featureCatalogProvider;
    private final V1CatalogSeedService catalogSeedService;

    public PluginService(
        PluginRepository pluginRepository,
        PluginTaskRepository pluginTaskRepository,
        PluginProfileRepository pluginProfileRepository,
        FeatureCatalogProvider featureCatalogProvider,
        V1CatalogSeedService catalogSeedService
    ) {
        this.pluginRepository = pluginRepository;
        this.pluginTaskRepository = pluginTaskRepository;
        this.pluginProfileRepository = pluginProfileRepository;
        this.featureCatalogProvider = featureCatalogProvider;
        this.catalogSeedService = catalogSeedService;
    }

    @PostConstruct
    private void init() {
        syncPlugins();
        syncTasks();
        syncProfiles();
    }

    private void syncPlugins() {
        Map<String, PluginSeed> desired = catalogSeedService.desiredPlugins();

        List<PluginImpl> current = new ArrayList<>();
        pluginRepository.findAll().forEach(current::add);
        Map<String, PluginImpl> byName = current.stream()
            .collect(Collectors.toMap(PluginImpl::getName, plugin -> plugin, (left, right) -> left));

        List<PluginImpl> toSave = new ArrayList<>();
        for (Map.Entry<String, PluginSeed> entry : desired.entrySet()) {
            PluginImpl existing = byName.get(entry.getKey());
            PluginImpl target = toPluginEntity(entry.getValue());
            if (existing == null) {
                toSave.add(target);
                continue;
            }
            copyPlugin(existing, target);
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
        List<TaskSeed> desired = catalogSeedService.desiredTasks();

        List<PluginTask> current = new ArrayList<>();
        pluginTaskRepository.findAll().forEach(current::add);
        Map<String, PluginTask> byPage = current.stream()
            .collect(Collectors.toMap(PluginTask::getPage, task -> task, (left, right) -> left));

        List<PluginTask> toSave = new ArrayList<>();
        for (TaskSeed seed : desired) {
            PluginTask existing = byPage.get(seed.getPage());
            PluginTask task = toTaskEntity(seed, resolvePlugin(seed.getPluginName()));
            if (existing == null) {
                toSave.add(task);
                continue;
            }
            existing.updateFrom(task);
            toSave.add(existing);
        }

        for (PluginTask task : current) {
            if (desired.stream().anyMatch(seed -> seed.getPage().equals(task.getPage()))) {
                continue;
            }
            task.setState(0);
            toSave.add(task);
        }

        pluginTaskRepository.saveAll(toSave);
    }

    private void syncProfiles() {
        List<ProfileSeed> desired = catalogSeedService.desiredProfiles();

        List<PluginProfile> current = new ArrayList<>();
        pluginProfileRepository.findAll().forEach(current::add);
        Map<String, PluginProfile> byPage = current.stream()
            .collect(Collectors.toMap(PluginProfile::getPage, profile -> profile, (left, right) -> left));

        List<PluginProfile> toSave = new ArrayList<>();
        for (ProfileSeed seed : desired) {
            PluginProfile existing = byPage.get(seed.getPage());
            PluginProfile profile = toProfileEntity(seed, resolvePlugin(seed.getPluginName()));
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
            if (featureCatalogProvider.activeProfilePages().contains(profile.getPage())) {
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
            .filter(plugin -> featureCatalogProvider.activePlugins().contains(plugin.getName()))
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
            .filter(task -> featureCatalogProvider.activePlugins().contains(task.getPlugin().getName()))
            .sorted(Comparator.comparing(PluginTask::getName, String.CASE_INSENSITIVE_ORDER))
            .collect(Collectors.toList());
    }

    public List<PluginProfile> findAllPluginProfile() {
        return pluginProfileRepository.findByState(1).stream()
            .filter(profile -> featureCatalogProvider.activeProfilePages().contains(profile.getPage()))
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

    private PluginImpl toPluginEntity(PluginSeed seed) {
        return new PluginImpl(
            seed.getName(),
            "1.0.0",
            seed.getDescription(),
            true,
            false,
            seed.isMachineOriented(),
            seed.isUserOriented(),
            seed.isPolicyPlugin(),
            seed.isTaskPlugin(),
            seed.isUsesFileTransfer(),
            seed.isXBased()
        );
    }

    private PluginTask toTaskEntity(TaskSeed seed, PluginImpl plugin) {
        return new PluginTask(
            seed.getName(),
            seed.getPage(),
            seed.getDescription(),
            seed.getCommandId(),
            seed.isMulti(),
            plugin,
            seed.getState(),
            seed.getRole()
        );
    }

    private PluginProfile toProfileEntity(ProfileSeed seed, PluginImpl plugin) {
        return new PluginProfile(
            seed.getName(),
            seed.getPage(),
            seed.getDescription(),
            seed.getCommandId(),
            plugin,
            seed.getState()
        );
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
}
