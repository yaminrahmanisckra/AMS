# Fix: "Unknown column" Error When Saving Routine

## Problem
Error: `(pymysql.err.OperationalError) (1054, "Unknown column`

This means the `saved_routine_id` column doesn't exist in the `routine` table.

## Solution: Add the Column

### Step 1: Check Current Columns

Run this in phpMyAdmin to see if the column exists:

```sql
DESCRIBE routine;
```

Look for `saved_routine_id` in the list. If it's not there, continue to Step 2.

### Step 2: Add the Column

Run these SQL commands **one by one** in phpMyAdmin (skip any that give "already exists" errors):

```sql
-- STEP 3: Add saved_routine_id column
ALTER TABLE `routine` 
ADD COLUMN `saved_routine_id` INT NULL;

-- STEP 4: Add index (for performance)
ALTER TABLE `routine` 
ADD INDEX `idx_saved_routine_id` (`saved_routine_id`);

-- STEP 5: Add foreign key constraint
ALTER TABLE `routine`
ADD CONSTRAINT `fk_routine_saved_routine`
FOREIGN KEY (`saved_routine_id`) REFERENCES `saved_routine`(`id`) ON DELETE CASCADE;

-- STEP 6: Drop old unique constraint (only if it exists)
ALTER TABLE `routine` 
DROP INDEX `_day_time_room_uc`;

-- STEP 7: Add new unique constraint with saved_routine_id
ALTER TABLE `routine` 
ADD UNIQUE KEY `_day_time_room_saved_routine_uc` (`day`, `time_slot`, `room_number`, `saved_routine_id`);
```

### Step 3: Verify

Run this to confirm the column was added:

```sql
DESCRIBE routine;
```

You should now see `saved_routine_id` in the column list.

### Step 4: Upload Files

After adding the column, upload these files to cPanel:

1. `blueprints/routine_management/routes.py`
2. `blueprints/routine_management/templates/routine_management/routine_new.html`

### Step 5: Restart Application

Restart the Python app from cPanel → Applications → Python

### Step 6: Test

Try saving a routine again - it should work now!
