package tr.org.lider;

import java.util.List;
import java.util.Properties;

import jakarta.annotation.PostConstruct;

import org.apache.directory.api.ldap.model.exception.LdapException;
import org.apache.directory.api.ldap.model.message.SearchScope;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.support.SpringBootServletInitializer;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;

import tr.org.lider.ldap.LDAPServiceImpl;
import tr.org.lider.ldap.LdapEntry;
import tr.org.lider.security.CustomPasswordEncoder;

@SpringBootApplication
@EnableJpaRepositories(basePackages = {"tr.org.lider"})
@EntityScan(basePackages = {"tr.org.lider"})
@ComponentScan(basePackages = {"tr.org.lider"})
@EnableCaching
public class Lider2Application extends SpringBootServletInitializer {

	Logger logger = LoggerFactory.getLogger(this.getClass());
	
	@Autowired
	private LDAPServiceImpl ldapService;

	@Autowired
	private CustomPasswordEncoder encoder;
	
	@Value("${lider.url}")
	private String liderURL;
	
	@Override
	protected SpringApplicationBuilder configure(SpringApplicationBuilder application) {
		return application.sources(Lider2Application.class)
				.sources(Lider2Application.class)
				.properties(getProperties());
	}

	public static void main(String[] args) {
		new SpringApplicationBuilder(Lider2Application.class)
		.sources(Lider2Application.class)
		.properties(getProperties())
		.run(args);
	}


	static Properties getProperties() {
		Properties props = new Properties();
		props.put("spring.config.location","file:/etc/lider/lider.properties");
		return props;
	}
	
	@PostConstruct
	public void init() {		
		String filter = "(&(objectClass=pardusAccount)(objectClass=pardusLider)(objectClass=inetOrgPerson))";
		List<LdapEntry> ldapEntries;
		try {
			ldapEntries = ldapService.findSubEntries(filter,
					new String[] { "*" }, SearchScope.SUBTREE);
			for (LdapEntry user : ldapEntries) {
				String pwd = user.getUserPassword();
				// SSHA hash'lerini olduğu gibi bırak — OpenLDAP bind uyumluluğu için
				// Sadece ne Argon2 ne SSHA formatında olanları dönüştür
				if(pwd != null && !pwd.startsWith("{ARGON2}") && !pwd.startsWith("{SSHA}")) {
					logger.info(user.getDistinguishedName() + " password will be updated to Argon2");
					user.setUserPassword(encoder.encode(pwd));
					ldapService.updateEntry(user.getDistinguishedName(), "userPassword", "{ARGON2}" + user.getUserPassword());
					logger.info(user.getDistinguishedName() + " password is updated");
				}
			}
		} catch (LdapException e) {
			logger.error(e.getLocalizedMessage());
		}
	}

}
