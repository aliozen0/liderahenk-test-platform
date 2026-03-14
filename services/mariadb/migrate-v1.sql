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
