package tr.org.lider.platform.dashboard;

import java.util.List;

import org.apache.directory.api.ldap.model.exception.LdapException;
import org.apache.directory.api.ldap.model.message.SearchScope;
import org.springframework.stereotype.Component;

import tr.org.lider.ldap.LDAPServiceImpl;
import tr.org.lider.ldap.LdapEntry;
import tr.org.lider.platform.presence.AgentPresenceProvider;
import tr.org.lider.services.ConfigurationService;

@Component
public class LdapDashboardComputerMetricsProvider implements DashboardComputerMetricsProvider {

    private final ConfigurationService configurationService;
    private final LDAPServiceImpl ldapService;
    private final AgentPresenceProvider agentPresenceProvider;

    public LdapDashboardComputerMetricsProvider(
        ConfigurationService configurationService,
        LDAPServiceImpl ldapService,
        AgentPresenceProvider agentPresenceProvider
    ) {
        this.configurationService = configurationService;
        this.ldapService = ldapService;
        this.agentPresenceProvider = agentPresenceProvider;
    }

    @Override
    public int totalComputerCount() {
        return fetchComputerEntries().size();
    }

    @Override
    public int totalOnlineComputerCount() {
        int online = 0;
        for (LdapEntry ldapComputer : fetchComputerEntries()) {
            if (ldapComputer != null && agentPresenceProvider.isOnline(ldapComputer.getUid())) {
                online++;
            }
        }
        return online;
    }

    private List<LdapEntry> fetchComputerEntries() {
        try {
            return ldapService.findSubEntries(
                configurationService.getAgentLdapBaseDn(),
                "(objectclass=pardusDevice)",
                new String[] { "*" },
                SearchScope.SUBTREE
            );
        } catch (LdapException e) {
            throw new IllegalStateException("Failed to query LDAP computer entries", e);
        }
    }
}
