package tr.org.lider.platform.ldap;

import org.springframework.stereotype.Component;

import tr.org.lider.security.User;
import tr.org.lider.services.AuthenticationService;
import tr.org.lider.services.ConfigurationService;

@Component
public class DefaultLdapBindPolicy implements LdapBindPolicy {

    @Override
    public LdapBindCredentials resolve(ConfigurationService configurationService) {
        boolean forceAdminBind = "v1-broad".equalsIgnoreCase(System.getenv("LIDER_FEATURE_PROFILE"))
            || "1".equals(System.getenv("LIDER_FORCE_LDAP_ADMIN_BIND"));

        if (!forceAdminBind && AuthenticationService.isLogged()) {
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
}
