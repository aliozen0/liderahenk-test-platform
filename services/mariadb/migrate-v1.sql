SET @schema_name = DATABASE();

SET @profile_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = @schema_name
              AND table_name = 'c_profile'
              AND column_name = 'profile_data'
              AND data_type <> 'longblob'
        ),
        'ALTER TABLE c_profile MODIFY COLUMN profile_data LONGBLOB NULL',
        'SELECT \"skip c_profile.profile_data\"'
    )
);
PREPARE stmt FROM @profile_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @operation_log_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = @schema_name
              AND table_name = 'c_operation_log'
              AND column_name = 'request_data'
              AND data_type <> 'longblob'
        ),
        'ALTER TABLE c_operation_log MODIFY COLUMN request_data LONGBLOB NULL',
        'SELECT \"skip c_operation_log.request_data\"'
    )
);
PREPARE stmt FROM @operation_log_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @command_execution_sql = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = @schema_name
              AND table_name = 'c_command_execution'
              AND column_name = 'dn'
              AND (
                  data_type <> 'varchar'
                  OR character_maximum_length <> 1000
              )
        ),
        'ALTER TABLE c_command_execution MODIFY COLUMN dn VARCHAR(1000) NULL',
        'SELECT \"skip c_command_execution.dn\"'
    )
);
PREPARE stmt FROM @command_execution_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE c_config
SET value = JSON_SET(
    value,
    '$.userLdapBaseDn',
    CONCAT('ou=users,', JSON_UNQUOTE(JSON_EXTRACT(value, '$.ldapRootDn')))
)
WHERE name = 'liderConfigParams'
  AND JSON_VALID(value)
  AND JSON_EXTRACT(value, '$.ldapRootDn') IS NOT NULL
  AND (
      JSON_EXTRACT(value, '$.userLdapBaseDn') IS NULL
      OR JSON_UNQUOTE(JSON_EXTRACT(value, '$.userLdapBaseDn')) = JSON_UNQUOTE(JSON_EXTRACT(value, '$.ldapRootDn'))
  );

UPDATE c_config
SET value = JSON_SET(
    value,
    '$.userGroupLdapBaseDn',
    JSON_UNQUOTE(JSON_EXTRACT(value, '$.groupLdapBaseDn'))
)
WHERE name = 'liderConfigParams'
  AND JSON_VALID(value)
  AND JSON_EXTRACT(value, '$.groupLdapBaseDn') IS NOT NULL
  AND JSON_UNQUOTE(JSON_EXTRACT(value, '$.userGroupLdapBaseDn')) <> JSON_UNQUOTE(JSON_EXTRACT(value, '$.groupLdapBaseDn'));

UPDATE c_config
SET value = JSON_SET(
    value,
    '$.ahenkGroupLdapBaseDn',
    CONCAT('ou=AgentGroups,', JSON_UNQUOTE(JSON_EXTRACT(value, '$.ldapRootDn')))
)
WHERE name = 'liderConfigParams'
  AND JSON_VALID(value)
  AND JSON_EXTRACT(value, '$.ldapRootDn') IS NOT NULL
  AND (
      JSON_EXTRACT(value, '$.ahenkGroupLdapBaseDn') IS NULL
      OR JSON_UNQUOTE(JSON_EXTRACT(value, '$.ahenkGroupLdapBaseDn')) = CONCAT('ou=Agent,ou=Groups,', JSON_UNQUOTE(JSON_EXTRACT(value, '$.ldapRootDn')))
  );

-- ============================================================================
-- FIX: Upstream JPA bug — CommandImpl.policy uses @OneToOne instead of
-- @ManyToOne, which causes Hibernate DDL auto-generation to create a bogus
-- single-column UNIQUE constraint on c_command.policy_id.  This prevents
-- the same policy from being executed to more than one target group, which
-- returns HTTP 417 "Task isn't executed" on every attempt after the first.
--
-- The composite unique (POLICY_ID, TASK_ID) declared in @Table is correct
-- and is kept intact.
--
-- Upstream source reference:
--   CommandImpl.java line 74-76 — @OneToOne  (should be @ManyToOne)
--   @JoinColumn(... unique = false)  — Hibernate ignores this for @OneToOne
-- ============================================================================
SET @fix_command_policy_unique = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'c_command'
              AND index_name = 'UKr5el9kgi9ctusbo8xn4i8w8ew'
        ),
        'ALTER TABLE c_command DROP INDEX UKr5el9kgi9ctusbo8xn4i8w8ew',
        'SELECT \"skip c_command policy_id unique — already dropped\"'
    )
);
PREPARE stmt FROM @fix_command_policy_unique;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

