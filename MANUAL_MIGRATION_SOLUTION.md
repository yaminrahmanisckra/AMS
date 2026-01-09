# Manual Migration Solution - kulawams.xyz

## সমস্যা

Migration history mismatch - পুরানো migrations আবার run করার চেষ্টা করছে যেগুলো already applied হয়েছে।

## সমাধান: Manual SQL (সবচেয়ে সহজ এবং Safe)

### Step 1: Check Current Database State

phpMyAdmin এ এই SQL run করুন:

```sql
-- Check if table already exists
SHOW TABLES LIKE 'active_semester_config';

-- Check current migration version
SELECT * FROM alembic_version;

-- Check if year column exists in result_session (already exists)
DESCRIBE result_session;
```

### Step 2: Create Table Manually (যদি না থাকে)

phpMyAdmin এ এই SQL run করুন:

```sql
-- Create active_semester_config table
CREATE TABLE IF NOT EXISTS `active_semester_config` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `academic_session` VARCHAR(50) NOT NULL,
    `year` VARCHAR(50) NOT NULL,
    `term` VARCHAR(50) NOT NULL,
    `batch` VARCHAR(50) NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `activated_by` VARCHAR(100) NULL,
    `activated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `deactivated_at` DATETIME NULL,
    INDEX `idx_active_semester` (`academic_session`, `year`, `term`, `batch`, `is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### Step 3: Check Current Migration Version and Update

```sql
-- Check current version
SELECT * FROM alembic_version;

-- If version exists, update it
UPDATE alembic_version SET version_num = 'a4b5c6d7e8f9';

-- Or if no version exists, insert it
INSERT INTO alembic_version (version_num) VALUES ('a4b5c6d7e8f9');
```

### Step 4: Verify

```sql
-- Check table exists
SHOW TABLES LIKE 'active_semester_config';

-- Check table structure
DESCRIBE active_semester_config;

-- Check migration version
SELECT * FROM alembic_version;
```

### Step 5: Restart Application

Terminal এ:

```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
```

### Step 6: Test Application

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test import
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig found')"

# Test semester_utils
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')"
```

## Alternative: Skip Problematic Migrations

যদি migration history fix করতে চান, তাহলে:

### Option 1: Stamp Current Version (Skip to Latest)

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Stamp to our migration (skip all previous)
flask db stamp a4b5c6d7e8f9

# Verify
flask db current
```

### Option 2: Check What Migrations Are Already Applied

phpMyAdmin এ check করুন database structure:

```sql
-- Check if columns exist that migrations would create
DESCRIBE result_session;  -- year column exists?
DESCRIBE class_student;   -- attendance_marks_manual exists?
```

যদি সব columns already exist, তাহলে manually stamp করুন:

```bash
flask db stamp a4b5c6d7e8f9
```

## Recommended Solution

**সবচেয়ে সহজ এবং Safe:** Manual SQL ব্যবহার করুন (Step 2):

1. phpMyAdmin এ SQL run করুন (table create)
2. Migration version update করুন
3. Restart করুন
4. Test করুন

এই approach সবচেয়ে safe কারণ:
- কোনো old migration run হবে না
- শুধুমাত্র আমাদের প্রয়োজনীয় table তৈরি হবে
- কোনো existing data affected হবে না

