-- Add is_revealed column to saved_routine table
-- Just run this single line:

ALTER TABLE `saved_routine` ADD COLUMN `is_revealed` TINYINT(1) NOT NULL DEFAULT 0 AFTER `name`;
