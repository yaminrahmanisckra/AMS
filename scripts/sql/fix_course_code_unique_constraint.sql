-- ============================================
-- Fix Course Code Unique Constraint
-- Allow same course code in different curricula
-- ============================================
-- 
-- This script:
-- 1. Drops the existing UNIQUE constraint on course_code column
-- 2. Adds a composite UNIQUE constraint on (curriculum_id, course_code)
--
-- This allows the same course code to exist in different curricula,
-- but ensures uniqueness within the same curriculum.
-- ============================================

USE `gronthon_ams2`;  -- Academic Management System database

-- Step 1: Drop existing UNIQUE constraint/index on course_code
-- MySQL creates a unique index with the column name when UNIQUE is specified in column definition
-- We need to drop this index before adding the composite constraint

-- Method 1: Try to drop by finding the constraint name dynamically
SET @index_name = NULL;

SELECT CONSTRAINT_NAME INTO @index_name
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'course'
  AND CONSTRAINT_TYPE = 'UNIQUE'
  AND CONSTRAINT_NAME LIKE '%course_code%'
LIMIT 1;

SET @sql = IF(@index_name IS NOT NULL,
    CONCAT('ALTER TABLE `course` DROP INDEX `', @index_name, '`'),
    'SELECT "No unique index found on course_code, skipping drop" AS message');

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Method 2: If Method 1 doesn't work, try common index names
-- Uncomment the line below if you get an error about index not found
-- ALTER TABLE `course` DROP INDEX IF EXISTS `course_code`;

-- Step 2: Add composite unique constraint
-- This allows same course_code in different curricula, but unique within same curriculum
ALTER TABLE `course`
ADD UNIQUE KEY `uq_curriculum_course_code` (`curriculum_id`, `course_code`);

-- Verify the constraint was added
SELECT 
    CONSTRAINT_NAME,
    CONSTRAINT_TYPE,
    TABLE_NAME
FROM information_schema.TABLE_CONSTRAINTS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'course'
  AND CONSTRAINT_NAME = 'uq_curriculum_course_code';

-- Success message
SELECT 'Course code unique constraint fixed successfully!' AS message;
SELECT 'Now you can use the same course code in different curricula.' AS note;

