-- External Course for Class Management (revision n4o5p6q7r8s9)
-- Run in phpMyAdmin after uploading code.

SET @col_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'class_session'
      AND COLUMN_NAME = 'is_external_course'
);

SET @sql = IF(
    @col_exists = 0,
    'ALTER TABLE class_session ADD COLUMN is_external_course TINYINT(1) NOT NULL DEFAULT 0',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE alembic_version SET version_num = 'n4o5p6q7r8s9';
