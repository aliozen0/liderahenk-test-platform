package tr.org.lider.platform.presence;

import java.util.Set;

public interface AgentPresenceProvider {

    boolean isOnline(String recipient);

    Set<String> getOnlineRecipients();
}
