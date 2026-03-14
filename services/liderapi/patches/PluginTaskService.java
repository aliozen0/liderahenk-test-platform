package tr.org.lider.services;

import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import jakarta.annotation.PostConstruct;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import tr.org.lider.entities.PluginTask;
import tr.org.lider.repositories.PluginTaskRepository;

@Service
public class PluginTaskService {

    private static final Set<String> V1_COMMAND_IDS = Set.of(
        "EXECUTE_SCRIPT",
        "GET_FILE_CONTENT",
        "WRITE_TO_FILE",
        "RESOURCE_INFO_FETCHER",
        "AGENT_INFO",
        "REPOSITORIES",
        "PACKAGE_SOURCES",
        "PACKAGE_MANAGEMENT",
        "PACKAGES",
        "INSTALLED_PACKAGES",
        "CHECK_PACKAGE",
        "GET_USERS",
        "ADD_USER",
        "EDIT_USER",
        "DELETE_USER",
        "GET_NETWORK_INFORMATION",
        "ADD_DNS",
        "DELETE_DNS",
        "ADD_DOMAIN",
        "DELETE_DOMAIN",
        "ADD_HOST",
        "DELETE_HOST",
        "ADD_NETWORK",
        "DELETE_NETWORK",
        "CHANGE_HOSTNAME",
        "ALLOW_PORT",
        "BLOCK_PORT",
        "MOVE_AGENT",
        "RENAME_ENTRY",
        "DELETE_AGENT"
    );

    @Autowired
    private PluginTaskRepository pluginTaskRepository;

    @PostConstruct
    public void init() throws Exception {
    }

    public List<PluginTask> findAll() {
        return pluginTaskRepository.findAll(Sort.by("name")).stream()
            .filter(task -> task.getState() == 1)
            .filter(task -> V1_COMMAND_IDS.contains(task.getCommandId()))
            .sorted(Comparator.comparing(PluginTask::getName, String.CASE_INSENSITIVE_ORDER))
            .collect(Collectors.toList());
    }

    public List<PluginTask> findPluginTaskByCommandID(String commandId) {
        return pluginTaskRepository.findByCommandId(commandId).stream()
            .filter(task -> task.getState() == 1)
            .filter(task -> V1_COMMAND_IDS.contains(task.getCommandId()))
            .collect(Collectors.toList());
    }
}
