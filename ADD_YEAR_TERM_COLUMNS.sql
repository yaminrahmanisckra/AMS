-- Add year and term columns to routine table
-- Run this in phpMyAdmin SQL tab

-- Check if columns exist first (optional - just to verify)
SELECT COLUMN_NAME 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'gronthon_ams2' 
  AND TABLE_NAME = 'routine' 
  AND COLUMN_NAME IN ('year', 'term');

-- If the above query returns empty, add the columns:

-- Add year column
ALTER TABLE `routine` 
ADD COLUMN `year` VARCHAR(20) NULL AFTER `teacher_id`;

-- Add term column  
ALTER TABLE `routine` 
ADD COLUMN `term` VARCHAR(20) NULL AFTER `year`;

-- Verify columns were added
DESCRIBE routine;

-- You should now see year and term in the column list
