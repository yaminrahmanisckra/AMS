# cPanel Upload Instructions for Saved Routines Feature

## Files to Upload

Upload the following modified files to your cPanel:

### Modified Files:
1. `blueprints/routine_management/models.py` - Added SavedRoutine model and saved_routine_id to Routine
2. `blueprints/routine_management/routes.py` - Added saved routines API endpoints and batch course filtering
3. `blueprints/routine_management/templates/routine_management/index.html` - Added Saved Routines UI
4. `blueprints/routine_management/templates/routine_management/routine_new.html` - Added batch filter UI and saved routine support
5. `templates/base.html` - Added View Routine link to navigation

### Files Location in cPanel:
- Models: `public_html/blueprints/routine_management/models.py`
- Routes: `public_html/blueprints/routine_management/routes.py`
- Templates: `public_html/blueprints/routine_management/templates/routine_management/`
- Base template: `public_html/templates/base.html`

## Database Migration Required

**IMPORTANT:** Before uploading code, you MUST run the database migration!

### Steps:

1. **Access cPanel MySQL Databases:**
   - Go to cPanel → MySQL Databases
   - Open phpMyAdmin for your database

2. **Run SQL Migration:**
   - Open the SQL tab in phpMyAdmin
   - Copy and paste the contents of `DATABASE_MIGRATION_FOR_SAVED_ROUTINES.sql`
   - Execute the SQL script

3. **Verify Migration:**
   ```sql
   -- Check if saved_routine table exists
   DESCRIBE saved_routine;
   
   -- Check if saved_routine_id column exists in routine table
   DESCRIBE routine;
   
   -- Check indexes
   SHOW INDEX FROM routine;
   ```

### Alternative: Step-by-Step SQL (if above fails)

If the combined SQL fails, run these one by one:

```sql
-- Step 1: Create saved_routine table
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

-- Step 2: Add foreign key (if users table exists)
ALTER TABLE `saved_routine`
ADD CONSTRAINT `fk_saved_routine_created_by`
FOREIGN KEY (`created_by_id`) REFERENCES `users`(`id`) ON DELETE SET NULL;

-- Step 3: Add saved_routine_id to routine table
ALTER TABLE `routine` 
ADD COLUMN `saved_routine_id` INT NULL AFTER `term`;

-- Step 4: Add index
ALTER TABLE `routine` 
ADD INDEX `idx_saved_routine_id` (`saved_routine_id`);

-- Step 5: Add foreign key
ALTER TABLE `routine`
ADD CONSTRAINT `fk_routine_saved_routine`
FOREIGN KEY (`saved_routine_id`) REFERENCES `saved_routine`(`id`) ON DELETE CASCADE;

-- Step 6: Drop old unique constraint (check actual name first)
ALTER TABLE `routine` 
DROP INDEX `_day_time_room_uc`;

-- Step 7: Add new unique constraint
ALTER TABLE `routine` 
ADD UNIQUE KEY `_day_time_room_saved_routine_uc` (`day`, `time_slot`, `room_number`, `saved_routine_id`);
```

## Upload Order

1. **First:** Run database migration (SQL script)
2. **Then:** Upload modified files via File Manager or FTP
3. **Finally:** Test the application

## Testing After Upload

1. Go to Routine Management dashboard
2. Check if "Saved Routines" section appears
3. Try creating a new saved routine (year-based)
4. Try loading and editing a saved routine
5. Test batch course filtering in the courses panel

## Rollback (if needed)

If you need to rollback:

```sql
-- Remove saved_routine_id from routine
ALTER TABLE `routine` 
DROP FOREIGN KEY `fk_routine_saved_routine`,
DROP INDEX `idx_saved_routine_id`,
DROP COLUMN `saved_routine_id`;

-- Restore old unique constraint
ALTER TABLE `routine` 
DROP INDEX `_day_time_room_saved_routine_uc`,
ADD UNIQUE KEY `_day_time_room_uc` (`day`, `time_slot`, `room_number`);

-- Drop saved_routine table (will delete all saved routines!)
DROP TABLE IF EXISTS `saved_routine`;
```

## Notes

- The migration is backward compatible - existing routines (without saved_routine_id) will still work
- New routines will be associated with saved routines by year
- Old routines (saved_routine_id = NULL) will continue to function as before
