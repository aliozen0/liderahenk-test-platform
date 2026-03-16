package tr.org.lider.platform.ldap;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import tr.org.lider.ldap.LdapEntry;
import tr.org.lider.message.service.IMessagingService;
import tr.org.lider.services.AgentPresenceService;

@Component
public class DefaultAgentDirectoryPresenceResolver implements AgentDirectoryPresenceResolver {

    private final AgentPresenceService agentPresenceService;
    private final IMessagingService messagingService;

    @Value("${xmpp.service.name:liderahenk.org}")
    private String xmppDomain;

    public DefaultAgentDirectoryPresenceResolver(
        AgentPresenceService agentPresenceService,
        IMessagingService messagingService
    ) {
        this.agentPresenceService = agentPresenceService;
        this.messagingService = messagingService;
    }

    @Override
    public boolean isOnline(LdapEntry ldapEntry) {
        if (ldapEntry == null || ldapEntry.getUid() == null || ldapEntry.getUid().isBlank()) {
            return false;
        }

        String uid = ldapEntry.getUid().trim();
        if (agentPresenceService.isOnline(uid)) {
            return true;
        }

        if (messagingService.isRecipientOnline(uid)) {
            return true;
        }

        String bareJid = uid.contains("@") ? uid : uid + "@" + xmppDomain;
        return messagingService.isRecipientOnline(bareJid);
    }
}
