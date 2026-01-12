-- Database Migration for Saved Routines Feature (SAFE VERSION - Handles existing objects)
-- Run this SQL script on your cPanel MySQL database

-- Step 1: Create saved_routine table (only if it doesn't exist)
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

-- Step 2: Add foreign key for created_by_id (only if constraint doesn't exist)
-- Check if constraint exists first - if it does, this will fail gracefully
SET @dbname = DATABASE();
SET @tablename = "saved_routine";
SET @constraintname = "fk_saved_routine_created_by";
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename)
      AND (CONSTRAINT_NAME = @constraintname)
  ) > 0,
  "SELECT 'Constraint already exists' AS result",
  CONCAT("ALTER TABLE `", @tablename, "` ADD CONSTRAINT `", @constraintname, "` FOREIGN KEY (`created_by_id`) REFERENCES `users`(`id`) ON DELETE SET NULL;")
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Step 3: Add saved_routine_id column to routine table (only if column doesn't exist)
SET @colname = "saved_routine_id";
SET @tablename2 = "routine";
SET @preparedStatement2 = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename2)
      AND (COLUMN_NAME = @colname)
  ) > 0,
  "SELECT 'Column already exists' AS result",
  CONCAT("ALTER TABLE `", @tablename2, "` ADD COLUMN `", @colname, "` INT NULL;")
));
PREPARE alterIfNotExists2 FROM @preparedStatement2;
EXECUTE alterIfNotExists2;
DEALLOCATE PREPARE alterIfNotExists2;

-- Step 4: Add index for saved_routine_id (only if index doesn't exist)
SET @indexname = "idx_saved_routine_id";
SET @preparedStatement3 = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename2)
      AND (INDEX_NAME = @indexname)
  ) > 0,
  "SELECT 'Index already exists' AS result",
  CONCAT("ALTER TABLE `", @tablename2, "` ADD INDEX `", @indexname, "` (`saved_routine_id`);")
));
PREPARE alterIfNotExists3 FROM @preparedStatement3;
EXECUTE alterIfNotExists3;
DEALLOCATE PREPARE alterIfNotExists3;

-- Step 5: Add foreign key constraint (only if constraint doesn't exist)
SET @constraintname2 = "fk_routine_saved_routine";
SET @preparedStatement4 = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename2)
      AND (CONSTRAINT_NAME = @constraintname2)
  ) > 0,
  "SELECT 'Constraint already exists' AS result",
  CONCAT("ALTER TABLE `", @tablename2, "` ADD CONSTRAINT `", @constraintname2, "` FOREIGN KEY (`saved_routine_id`) REFERENCES `saved_routine`(`id`) ON DELETE CASCADE;")
));
PREPARE alterIfNotExists4 FROM @preparedStatement4;
EXECUTE alterIfNotExists4;
DEALLOCATE PREPARE alterIfNotExists4;

-- Step 6: Drop old unique constraint (if it exists)
SET @oldindexname = "_day_time_room_uc";
SET @preparedStatement5 = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename2)
      AND (INDEX_NAME = @oldindexname)
  ) > 0,
  CONCAT("ALTER TABLE `", @tablename2, "` DROP INDEX `", @oldindexname, "`;"),
  "SELECT 'Old index does not exist' AS result"
));
PREPARE dropIfExists FROM @preparedStatement5;
EXECUTE dropIfExists;
DEALLOCATE PREPARE dropIfExists;

-- Step 7: Add new unique constraint (only if it doesn't exist)
SET @newindexname = "_day_time_room_saved_routine_uc";
SET @preparedStatement6 = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
    WHERE
      (TABLE_SCHEMA = @dbname)
      AND (TABLE_NAME = @tablename2)
      AND (INDEX_NAME = @newindexname)
  ) > 0,
  "SELECT 'New index already exists' AS result",
  CONCAT("ALTER TABLE `", @tablename2, "` ADD UNIQUE KEY `", @newindexname, "` (`day`, `time_slot`, `room_number`, `saved_routine_id`);")
));
PREPARE alterIfNotExists6 FROM @preparedStatement6;
EXECUTE alterIfNotExists6;
DEALLOCATE PREPARE alterIfNotExists6;

-- Verification queries:
-- DESCRIBE saved_routine;
-- DESCRIBE routine;
-- SHOW INDEX FROM routine;
