-- External assessment mode for Class Management (revision o5p6q7r8s9t0)
-- Run in phpMyAdmin after uploading code.

SET @col_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'class_session'
      AND COLUMN_NAME = 'external_assessment_mode'
);

SET @sql = IF(
    @col_exists = 0,
    "ALTER TABLE class_session ADD COLUMN external_assessment_mode VARCHAR(20) NOT NULL DEFAULT 'best_three'",
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE alembic_version SET version_num = 'o5p6q7r8s9t0';
