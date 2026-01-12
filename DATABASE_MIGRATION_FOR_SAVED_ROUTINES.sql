-- Database Migration for Saved Routines Feature
-- Run this SQL script on your cPanel MySQL database before uploading the code

-- 1. Create saved_routine table
CREATE TABLE IF NOT EXISTS `saved_routine` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `year` VARCHAR(20) NOT NULL UNIQUE,
    `name` VARCHAR(100) NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_by_id` INT NULL,
    INDEX `idx_year` (`year`),
    INDEX `idx_created_by` (`created_by_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 1b. Add foreign key for created_by_id (separate step for compatibility)
ALTER TABLE `saved_routine`
ADD CONSTRAINT `fk_saved_routine_created_by`
FOREIGN KEY (`created_by_id`) REFERENCES `users`(`id`) ON DELETE SET NULL;

-- 2. Add saved_routine_id column to routine table (column will be added at the end)
ALTER TABLE `routine` 
ADD COLUMN `saved_routine_id` INT NULL;

-- 3. Add index for saved_routine_id
ALTER TABLE `routine` 
ADD INDEX `idx_saved_routine_id` (`saved_routine_id`);

-- 4. Add foreign key
ALTER TABLE `routine`
ADD CONSTRAINT `fk_routine_saved_routine`
FOREIGN KEY (`saved_routine_id`) REFERENCES `saved_routine`(`id`) ON DELETE CASCADE;

-- 5. Drop old unique constraint (might need to check actual name first)
-- Check first: SHOW INDEX FROM routine;
ALTER TABLE `routine` 
DROP INDEX `_day_time_room_uc`;

-- 6. Add new unique constraint with saved_routine_id
ALTER TABLE `routine` 
ADD UNIQUE KEY `_day_time_room_saved_routine_uc` (`day`, `time_slot`, `room_number`, `saved_routine_id`);

-- Verification queries (run to check):
-- SELECT * FROM saved_routine;
-- DESCRIBE routine;
-- SHOW INDEX FROM routine;
