package tr.org.lider.services;

import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

import jakarta.annotation.PostConstruct;

import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import tr.org.lider.entities.PluginTask;
import tr.org.lider.platform.catalog.FeatureCatalogProvider;
import tr.org.lider.repositories.PluginTaskRepository;

@Service
public class PluginTaskService {

    private final PluginTaskRepository pluginTaskRepository;
    private final FeatureCatalogProvider featureCatalogProvider;

    public PluginTaskService(PluginTaskRepository pluginTaskRepository, FeatureCatalogProvider featureCatalogProvider) {
        this.pluginTaskRepository = pluginTaskRepository;
        this.featureCatalogProvider = featureCatalogProvider;
    }

    @PostConstruct
    public void init() {
    }

    public List<PluginTask> findAll() {
        return pluginTaskRepository.findAll(Sort.by("name")).stream()
            .filter(task -> task.getState() == 1)
            .filter(task -> featureCatalogProvider.activeTaskCommandIds().contains(task.getCommandId()))
            .sorted(Comparator.comparing(PluginTask::getName, String.CASE_INSENSITIVE_ORDER))
            .collect(Collectors.toList());
    }

    public List<PluginTask> findPluginTaskByCommandID(String commandId) {
        return pluginTaskRepository.findByCommandId(commandId).stream()
            .filter(task -> task.getState() == 1)
            .filter(task -> featureCatalogProvider.activeTaskCommandIds().contains(task.getCommandId()))
            .collect(Collectors.toList());
    }
}
