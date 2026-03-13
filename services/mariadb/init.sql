-- ============================================================
-- LiderAhenk — MariaDB Seed Data
-- ============================================================
-- Spring Boot Hibernate SpringPhysicalNamingStrategy kullanır:
--   @Table(name = "C_CONFIG") → c_config (lowercase)
--   @Column(name = "CONFIG_ID") → config_id (lowercase)
-- Bu yüzden tüm isimler lowercase olmalı!
-- ============================================================

-- c_config tablosunu oluştur (Hibernate DDL'den önce çalışır)
CREATE TABLE IF NOT EXISTS c_config (
    config_id   BIGINT NOT NULL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL UNIQUE,
    value       TEXT,
    create_date DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    modify_date DATETIME(6) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Hibernate sequence tablosu
CREATE TABLE IF NOT EXISTS c_config_seq (
    next_val BIGINT
) ENGINE=InnoDB;
INSERT IGNORE INTO c_config_seq (next_val) VALUES (100);

-- liderConfigParams — ConfigParams JSON
-- Docker ortamına uygun değerler: ldap, ejabberd, mariadb hostname'leri
INSERT IGNORE INTO c_config (config_id, name, value, create_date) VALUES (
    1,
    'liderConfigParams',
    '{"liderLocale":"tr","ldapServer":"ldap","ldapPort":"1389","ldapUsername":"cn=admin,dc=liderahenk,dc=org","ldapPassword":"DEGISTIR","ldapRootDn":"dc=liderahenk,dc=org","ldapUseSsl":false,"ldapAllowSelfSignedCert":false,"ldapSearchAttributes":"cn,objectClass,uid,liderPrivilege","ldapMailNotifierAttributes":"cn, mail, departmentNumber, uid","ldapEmailAttribute":"mail","agentLdapBaseDn":"ou=Ahenkler,dc=liderahenk,dc=org","agentLdapIdAttribute":"cn","agentLdapJidAttribute":"uid","agentLdapObjectClasses":"pardusDevice,device","userLdapBaseDn":"dc=liderahenk,dc=org","userLdapUidAttribute":"uid","userLdapPrivilegeAttribute":"liderPrivilege","userLdapObjectClasses":"pardusAccount,pardusLider","userAuthorizationEnabled":true,"groupLdapObjectClasses":"groupOfNames","roleLdapObjectClasses":"sudoRole","groupLdapBaseDn":"ou=Groups,dc=liderahenk,dc=org","userLdapRolesDn":"ou=Roles,dc=liderahenk,dc=org","userGroupLdapBaseDn":"ou=Roles,dc=liderahenk,dc=org","ahenkGroupLdapBaseDn":"ou=Agent,ou=Groups,dc=liderahenk,dc=org","xmppHost":"ejabberd","xmppPort":5222,"xmppUsername":"lider_sunucu","xmppPassword":"secret","xmppResource":"LiderAPI","xmppServiceName":"liderahenk.org","xmppMaxRetryConnectionCount":5,"xmppPacketReplayTimeout":10000,"xmppPingTimeout":300,"xmppUseSsl":false,"xmppAllowSelfSignedCert":false,"xmppUseCustomSsl":false,"xmppPresencePriority":1,"fileServerProtocol":"SSH","fileServerHost":"liderapi","fileServerPort":22,"fileServerUsername":"lider","fileServerPassword":"secret","fileServerPluginPath":"/plugins/ahenk-{0}_{1}_amd64.deb","fileServerAgreementPath":"/home/pardus/sample-agreement.txt","fileServerAgentFilePath":"/agent-files/{0}/","taskManagerCheckFutureTask":true,"taskManagerFutureTaskCheckPeriod":60000,"alarmCheckReport":true,"mailAddress":"","mailPassword":"","mailHost":"","mailSmtpPort":587,"mailSmtpAuth":true,"mailSmtpStartTlsEnable":true,"mailSmtpSslEnable":false,"mailSmtpConnTimeout":5000,"mailSmtpTimeout":5000,"mailSmtpWriteTimeout":5000,"mailSendOnTaskCompletion":false,"mailCheckTaskCompletionPeriod":60000,"mailSendOnPolicyCompletion":false,"mailCheckPolicyCompletionPeriod":120000,"hotDeploymentPath":"/usr/share/lider-server/deploy/","cronTaskList":"BACKUP_WITH_MONITORING_TASK,SERVICE_MANAGEMENT","entrySizeLimit":20,"cronIntervalEntrySize":10,"disableLocalUser":false,"domainType":"LDAP","sudoRoleType":"LDAP","ahenkRepoAddress":"","ahenkRepoKeyAddress":"","machineEventStatus":false,"machineEventDay":120,"clientSize":1,"allowVNCConnectionWithoutPermission":true,"pardusRepoAddress":"http://depo.pardus.org.tr/pardus","pardusRepoComponent":"yirmibir main contrib non-free","enableDelete4Directory":false,"allowDynamicDNSUpdate":false,"selectedRegistrationType":"DEFAULT","isTwoFactorEnabled":false,"otpExpiryDuration":300000}',
    NOW(6)
);
