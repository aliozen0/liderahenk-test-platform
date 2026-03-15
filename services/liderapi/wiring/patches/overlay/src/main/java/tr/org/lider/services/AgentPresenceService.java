package tr.org.lider.services;

import java.util.Set;

import org.springframework.stereotype.Service;

import tr.org.lider.platform.presence.AgentPresenceProvider;

@Service
public class AgentPresenceService {

    private final AgentPresenceProvider presenceProvider;

    public AgentPresenceService(AgentPresenceProvider presenceProvider) {
        this.presenceProvider = presenceProvider;
    }

    public boolean isOnline(String recipient) {
        return presenceProvider.isOnline(recipient);
    }

    public Set<String> getOnlineRecipients() {
        return presenceProvider.getOnlineRecipients();
    }
}
