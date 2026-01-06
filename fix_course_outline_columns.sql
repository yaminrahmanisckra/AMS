-- ============================================
-- FIX COURSE_OUTLINE TABLE - Add Missing Columns
-- ============================================

USE gronthon_ams2;

-- Helper procedure to add columns safely
DELIMITER $$

DROP PROCEDURE IF EXISTS AddColumnIfNotExists$$

CREATE PROCEDURE AddColumnIfNotExists(
    IN tableName VARCHAR(64),
    IN columnName VARCHAR(64),
    IN columnDefinition TEXT
)
BEGIN
    DECLARE columnExists INT DEFAULT 0;
    
    SELECT COUNT(*) INTO columnExists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = tableName
      AND COLUMN_NAME = columnName;
    
    IF columnExists = 0 THEN
        SET @sql = CONCAT('ALTER TABLE `', tableName, '` ADD COLUMN `', columnName, '` ', columnDefinition);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

DELIMITER ;

-- Add missing columns to course_outline table
CALL AddColumnIfNotExists('course_outline', 'credit_value', 'VARCHAR(20) NULL AFTER `smee_marks`');
CALL AddColumnIfNotExists('course_outline', 'course_type', 'VARCHAR(50) NULL AFTER `credit_value`');
CALL AddColumnIfNotExists('course_outline', 'level_term_section', 'VARCHAR(100) NULL AFTER `course_type`');
CALL AddColumnIfNotExists('course_outline', 'clo_data', 'TEXT NULL AFTER `level_term_section`');
CALL AddColumnIfNotExists('course_outline', 'plo_mapping', 'TEXT NULL AFTER `clo_data`');
CALL AddColumnIfNotExists('course_outline', 'student_access_enabled', 'BOOLEAN NOT NULL DEFAULT FALSE AFTER `other_issues`');

-- Clean up procedure
DROP PROCEDURE IF EXISTS AddColumnIfNotExists;




