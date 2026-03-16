package tr.org.lider.platform.ldap;

import tr.org.lider.ldap.LdapEntry;

public interface AgentDirectoryPresenceResolver {

    boolean isOnline(LdapEntry ldapEntry);
}
