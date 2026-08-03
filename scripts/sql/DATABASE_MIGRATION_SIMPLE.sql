-- Database Migration for Saved Routines Feature (SIMPLE VERSION)
-- Run each step separately in phpMyAdmin to avoid errors

-- STEP 1: Create saved_routine table (run this first)
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

-- STEP 2: Add foreign key for created_by_id (run this second - skip if error says constraint exists)
-- If you get error "Duplicate key" or constraint exists, skip this step
ALTER TABLE `saved_routine`
ADD CONSTRAINT `fk_saved_routine_created_by`
FOREIGN KEY (`created_by_id`) REFERENCES `users`(`id`) ON DELETE SET NULL;

-- STEP 3: Add saved_routine_id column (run this third - skip if error says column exists)
-- If you get error "Duplicate column name", skip this step
ALTER TABLE `routine` 
ADD COLUMN `saved_routine_id` INT NULL;

-- STEP 4: Add index (run this fourth - skip if error says index exists)
ALTER TABLE `routine` 
ADD INDEX `idx_saved_routine_id` (`saved_routine_id`);

-- STEP 5: Add foreign key (run this fifth - skip if error says constraint exists)
ALTER TABLE `routine`
ADD CONSTRAINT `fk_routine_saved_routine`
FOREIGN KEY (`saved_routine_id`) REFERENCES `saved_routine`(`id`) ON DELETE CASCADE;

-- STEP 6: Check if old index exists first (run this query to check):
-- SHOW INDEX FROM routine WHERE Key_name = '_day_time_room_uc';
-- If it exists, run STEP 6a, otherwise skip to STEP 7

-- STEP 6a: Drop old unique constraint (only if it exists)
ALTER TABLE `routine` 
DROP INDEX `_day_time_room_uc`;

-- STEP 7: Add new unique constraint (run this last - skip if error says index exists)
ALTER TABLE `routine` 
ADD UNIQUE KEY `_day_time_room_saved_routine_uc` (`day`, `time_slot`, `room_number`, `saved_routine_id`);
