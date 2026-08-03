-- Add is_revealed column to saved_routine table
-- Run this in phpMyAdmin SQL tab

-- Check if column exists first (optional - just to verify)
SELECT COLUMN_NAME 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'gronthon_ams2' 
  AND TABLE_NAME = 'saved_routine' 
  AND COLUMN_NAME = 'is_revealed';

-- If the above query returns empty, add the column:

-- Add is_revealed column
ALTER TABLE `saved_routine` 
ADD COLUMN `is_revealed` TINYINT(1) NOT NULL DEFAULT 0 AFTER `name`;

-- Verify column was added
DESCRIBE saved_routine;

-- You should now see is_revealed in the column list
