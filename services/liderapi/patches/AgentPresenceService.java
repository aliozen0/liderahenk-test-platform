package tr.org.lider.services;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Collections;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class AgentPresenceService {

    private static final Logger logger = LoggerFactory.getLogger(AgentPresenceService.class);
    private static final Duration CACHE_TTL = Duration.ofSeconds(3);
    private static final Duration STALE_CACHE_TTL = Duration.ofSeconds(30);

    private final HttpClient httpClient = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(3))
        .build();

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Object refreshLock = new Object();

    @Value("${xmpp.host:ejabberd}")
    private String xmppHost;

    @Value("${xmpp.service.name:liderahenk.org}")
    private String xmppDomain;

    private volatile Set<String> cachedRecipients = Collections.emptySet();
    private volatile long cachedAt = 0L;

    public boolean isOnline(String recipient) {
        if (recipient == null || recipient.isBlank()) {
            return false;
        }

        String normalized = normalize(recipient);
        if (normalized == null || normalized.isBlank()) {
            return false;
        }

        Set<String> onlineRecipients = getOnlineRecipients();
        if (onlineRecipients.contains(normalized)) {
            return true;
        }

        String bareUser = bareUser(normalized);
        if (onlineRecipients.contains(bareUser)) {
            return true;
        }

        if (!normalized.contains("@")) {
            return onlineRecipients.contains(normalized + "@" + xmppDomain);
        }

        return false;
    }

    public Set<String> getOnlineRecipients() {
        long now = System.currentTimeMillis();
        if (now - cachedAt <= CACHE_TTL.toMillis()) {
            return cachedRecipients;
        }

        synchronized (refreshLock) {
            now = System.currentTimeMillis();
            if (now - cachedAt <= CACHE_TTL.toMillis()) {
                return cachedRecipients;
            }

            try {
                Set<String> refreshed = fetchOnlineRecipients();
                cachedRecipients = refreshed;
                cachedAt = now;
                return refreshed;
            } catch (Exception e) {
                if (now - cachedAt <= STALE_CACHE_TTL.toMillis() && !cachedRecipients.isEmpty()) {
                    logger.debug("Falling back to stale ejabberd presence cache: {}", e.getMessage());
                    return cachedRecipients;
                }
                logger.warn("Failed to refresh ejabberd presence cache: {}", e.getMessage());
                cachedRecipients = Collections.emptySet();
                cachedAt = now;
                return cachedRecipients;
            }
        }
    }

    private Set<String> fetchOnlineRecipients() throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
            .uri(URI.create(resolveApiBaseUrl() + "/connected_users"))
            .timeout(Duration.ofSeconds(5))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString("{}"))
            .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IOException("HTTP " + response.statusCode());
        }

        JsonNode payload = objectMapper.readTree(response.body());
        if (payload == null || !payload.isArray()) {
            return Collections.emptySet();
        }

        Set<String> recipients = new HashSet<>();
        for (JsonNode node : payload) {
            if (node == null || !node.isTextual()) {
                continue;
            }
            String fullJid = normalize(node.asText());
            if (fullJid == null || fullJid.isBlank()) {
                continue;
            }
            recipients.add(fullJid);
            recipients.add(bareJid(fullJid));
            recipients.add(bareUser(fullJid));
        }
        return Collections.unmodifiableSet(recipients);
    }

    private String resolveApiBaseUrl() {
        String env = System.getenv("EJABBERD_API");
        if (env != null && !env.isBlank()) {
            return env.replaceAll("/+$", "");
        }
        return "http://" + xmppHost + ":5280/api";
    }

    private String normalize(String recipient) {
        if (recipient == null) {
            return null;
        }
        String normalized = recipient.trim();
        if (normalized.isEmpty()) {
            return normalized;
        }
        int slashIndex = normalized.indexOf('/');
        if (slashIndex >= 0) {
            normalized = normalized.substring(0, slashIndex);
        }
        return normalized.toLowerCase(Locale.ROOT);
    }

    private String bareJid(String recipient) {
        String normalized = normalize(recipient);
        return normalized == null ? "" : normalized;
    }

    private String bareUser(String recipient) {
        String normalized = normalize(recipient);
        if (normalized == null || normalized.isBlank()) {
            return "";
        }
        int atIndex = normalized.indexOf('@');
        if (atIndex < 0) {
            return normalized;
        }
        return normalized.substring(0, atIndex);
    }
}
