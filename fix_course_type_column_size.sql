-- ============================================
-- Fix Course Type Column Size
-- Increase course_type column size to accommodate longer values
-- ============================================
-- 
-- This script:
-- 1. Increases course_type column size from VARCHAR(20) to VARCHAR(50)
--
-- This allows longer course type names like "Dissertation Proposal (PG)"
-- ============================================

USE `gronthon_ams2`;  -- Academic Management System database

-- Increase course_type column size from VARCHAR(20) to VARCHAR(50)
ALTER TABLE `course` 
MODIFY COLUMN `course_type` VARCHAR(50) NOT NULL;

-- Verify the change
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'course'
  AND COLUMN_NAME = 'course_type';

-- Success message
SELECT 'Course type column size increased successfully!' AS message;
SELECT 'Now course_type can store up to 50 characters.' AS note;

