package tr.org.lider.platform.catalog;

import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Component;

@Component
public class V1FeatureCatalogProvider implements FeatureCatalogProvider {

    private static final Set<String> ACTIVE_PLUGIN_NAMES = Set.of(
        "script",
        "file-management",
        "resource-usage",
        "package-manager",
        "local-user",
        "network-manager",
        "ldap"
    );

    private static final Set<String> ACTIVE_TASK_COMMAND_IDS = Set.of(
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

    private static final Set<String> ACTIVE_PROFILE_PAGES = Set.of("execute-script-profile");

    private static final List<String> ACTIVE_TASK_PAGES = List.of(
        "file-management",
        "write-to-file",
        "delete-agent",
        "move-agent",
        "rename-agent",
        "local-user",
        "add-local-user",
        "delete-local-user",
        "edit-local-user",
        "network-manager",
        "add-dns",
        "add-domain",
        "add-host",
        "add-network",
        "allow-port",
        "delete-dns",
        "delete-domain",
        "delete-host",
        "delete-network",
        "change-hostname",
        "block-port",
        "repositories",
        "package-sources",
        "package-management",
        "packages",
        "installed-packages",
        "check-package",
        "resource-usage",
        "agent-info",
        "execute-script"
    );

    @Override
    public Set<String> activePlugins() {
        return ACTIVE_PLUGIN_NAMES;
    }

    @Override
    public Set<String> activeTaskCommandIds() {
        return ACTIVE_TASK_COMMAND_IDS;
    }

    @Override
    public Set<String> activeProfilePages() {
        return ACTIVE_PROFILE_PAGES;
    }

    @Override
    public List<String> activeTaskPages() {
        return ACTIVE_TASK_PAGES;
    }
}
