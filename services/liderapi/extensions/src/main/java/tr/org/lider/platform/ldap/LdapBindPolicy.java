package tr.org.lider.platform.ldap;

import tr.org.lider.services.ConfigurationService;

public interface LdapBindPolicy {

    LdapBindCredentials resolve(ConfigurationService configurationService);
}
