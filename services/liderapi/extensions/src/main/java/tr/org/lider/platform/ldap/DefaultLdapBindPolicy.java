package tr.org.lider.platform.ldap;

import java.util.Locale;
import java.util.Set;

import org.springframework.stereotype.Component;

import tr.org.lider.security.User;
import tr.org.lider.services.AuthenticationService;
import tr.org.lider.services.ConfigurationService;

/**
 * Default Strategy implementation for LDAP bind credential resolution.
 *
 * <p>Design: <b>Strategy Pattern</b> — {@link LdapBindPolicy} is the strategy
 * interface; this class is the default (and currently only) concrete strategy.
 * Upstream {@code LDAPServiceImpl} depends solely on the interface via
 * {@code @Autowired}, never on this concrete class.</p>
 *
 * <p>SOLID alignment:
 * <ul>
 *   <li><b>SRP</b> — bind credential resolution is this class's only job.</li>
 *   <li><b>OCP</b> — new bind modes are added here; upstream is untouched.</li>
 *   <li><b>DIP</b> — upstream depends on abstraction ({@link LdapBindPolicy}),
 *       not on this concrete implementation.</li>
 * </ul></p>
 */
@Component
public class DefaultLdapBindPolicy implements LdapBindPolicy {

    private static final Set<String> SERVICE_ACCOUNT_BIND_MODES = Set.of(
        "service-account",
        "admin",
        "platform"
    );

    @Override
    public LdapBindCredentials resolve(ConfigurationService configurationService) {
        if (!isServiceAccountMode() && AuthenticationService.isLogged()) {
            User user = AuthenticationService.getUser();
            if (user != null && user.getPassword() != null && !user.getPassword().isEmpty()) {
                return new LdapBindCredentials(user.getDn(), user.getPassword());
            }
        }

        return new LdapBindCredentials(
            configurationService.getLdapUsername(),
            configurationService.getLdapPassword()
        );
    }

    private boolean isServiceAccountMode() {
        String forceFlag = System.getenv("LIDER_FORCE_LDAP_ADMIN_BIND");
        if ("1".equals(forceFlag)) {
            return true;
        }

        String bindMode = System.getenv("LIDER_LDAP_BIND_MODE");
        String effective = (bindMode == null || bindMode.isBlank())
            ? "authenticated-user"
            : bindMode.trim().toLowerCase(Locale.ROOT);

        return SERVICE_ACCOUNT_BIND_MODES.contains(effective);
    }
}
