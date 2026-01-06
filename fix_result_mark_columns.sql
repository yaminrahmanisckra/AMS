-- Fix missing columns in result_mark table
-- Add thesis_evaluation and presentation columns for Thesis subjects

USE gronthon_ams2;

-- Add thesis_evaluation column (ignore error if already exists)
ALTER TABLE `result_mark` 
ADD COLUMN `thesis_evaluation` FLOAT NULL AFTER `defense`;

-- Add presentation column (ignore error if already exists)
ALTER TABLE `result_mark` 
ADD COLUMN `presentation` FLOAT NULL AFTER `thesis_evaluation`;

-- Note: If you get "Duplicate column name" error, that means the column already exists - that's OK!
