package tr.org.lider.platform.inventory;

import java.util.Date;
import java.util.List;
import java.util.Objects;
import java.util.function.Consumer;

import org.apache.directory.api.ldap.model.exception.LdapException;
import org.apache.directory.api.ldap.model.message.SearchScope;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import tr.org.lider.entities.AgentImpl;
import tr.org.lider.entities.AgentStatus;
import tr.org.lider.ldap.LDAPServiceImpl;
import tr.org.lider.ldap.LdapEntry;
import tr.org.lider.platform.presence.AgentPresenceProvider;
import tr.org.lider.repositories.AgentRepository;
import tr.org.lider.services.ConfigurationService;

@Component
public class LdapAgentInventoryReconciler implements AgentInventoryReconciler {

    private static final Logger logger = LoggerFactory.getLogger(LdapAgentInventoryReconciler.class);

    private final ConfigurationService configurationService;
    private final LDAPServiceImpl ldapService;
    private final AgentRepository agentRepository;
    private final AgentPresenceProvider agentPresenceProvider;

    public LdapAgentInventoryReconciler(
        ConfigurationService configurationService,
        LDAPServiceImpl ldapService,
        AgentRepository agentRepository,
        AgentPresenceProvider agentPresenceProvider
    ) {
        this.configurationService = configurationService;
        this.ldapService = ldapService;
        this.agentRepository = agentRepository;
        this.agentPresenceProvider = agentPresenceProvider;
    }

    @Override
    public void reconcileFromLdap() {
        try {
            List<LdapEntry> ldapAgents = ldapService.findSubEntries(
                configurationService.getAgentLdapBaseDn(),
                "(objectclass=pardusDevice)",
                new String[] { "*" },
                SearchScope.SUBTREE
            );

            int created = 0;
            int updated = 0;
            for (LdapEntry ldapAgent : ldapAgents) {
                if (ldapAgent == null || ldapAgent.getUid() == null || ldapAgent.getUid().isBlank()) {
                    continue;
                }

                String jid = ldapAgent.getUid().trim();
                String dn = ldapAgent.getDistinguishedName();
                String hostname = deriveHostname(ldapAgent);
                boolean online = agentPresenceProvider.isOnline(jid);

                List<AgentImpl> existingAgents = agentRepository.findByJid(jid);
                AgentImpl agent = existingAgents.isEmpty() ? new AgentImpl() : existingAgents.get(0);
                boolean dirty = existingAgents.isEmpty();
                Date now = new Date();

                dirty |= setIfChanged(agent.getJid(), jid, agent::setJid);
                dirty |= setIfChanged(agent.getDn(), dn, agent::setDn);
                dirty |= setIfChanged(agent.getPassword(), defaultPassword(ldapAgent), agent::setPassword);
                dirty |= setIfChanged(agent.getHostname(), hostname, agent::setHostname);
                dirty |= setIfChanged(agent.getIpAddresses(), defaultIpAddresses(agent.getIpAddresses()), agent::setIpAddresses);
                dirty |= setIfChanged(agent.getMacAddresses(), defaultMacAddresses(agent.getMacAddresses()), agent::setMacAddresses);
                dirty |= setIfChanged(agent.getDeleted(), Boolean.FALSE, agent::setDeleted);

                if (agent.getCreateDate() == null) {
                    agent.setCreateDate(now);
                    dirty = true;
                }
                agent.setModifyDate(now);
                if (agent.getEventDate() == null) {
                    agent.setEventDate(now);
                    dirty = true;
                }
                if (online) {
                    agent.setLastLoginDate(now);
                    dirty = true;
                }

                AgentStatus desiredStatus = online ? AgentStatus.Active : AgentStatus.Passive;
                if (agent.getAgentStatus() != desiredStatus) {
                    agent.setAgentStatus(desiredStatus);
                    dirty = true;
                }

                if (!dirty) {
                    continue;
                }

                agentRepository.save(agent);
                if (existingAgents.isEmpty()) {
                    created++;
                } else {
                    updated++;
                }
            }

            logger.info("Agent inventory sync completed. created={}, updated={}", created, updated);
        } catch (LdapException e) {
            logger.warn("Agent inventory sync failed: {}", e.getMessage());
        }
    }

    private String deriveHostname(LdapEntry ldapAgent) {
        String cn = ldapAgent.getCn();
        if (cn != null && !cn.isBlank()) {
            return cn.endsWith("-host") ? cn : cn + "-host";
        }
        String uid = ldapAgent.getUid();
        if (uid != null && !uid.isBlank()) {
            return uid.endsWith("-host") ? uid : uid + "-host";
        }
        return "unknown-host";
    }

    private String defaultPassword(LdapEntry ldapAgent) {
        String password = ldapAgent.getUserPassword();
        return (password == null || password.isBlank()) ? "secret" : password;
    }

    private String defaultIpAddresses(String currentValue) {
        return (currentValue == null || currentValue.isBlank()) ? "127.0.0.1" : currentValue;
    }

    private String defaultMacAddresses(String currentValue) {
        return (currentValue == null || currentValue.isBlank()) ? "00:00:00:00:00:00" : currentValue;
    }

    private <T> boolean setIfChanged(T currentValue, T desiredValue, Consumer<T> setter) {
        if (Objects.equals(currentValue, desiredValue)) {
            return false;
        }
        setter.accept(desiredValue);
        return true;
    }
}
