# Fix Multiple Migration Heads - kulawams.xyz

## সমস্যা

Multiple migration heads আছে:
- `3002f25a49ae` (head)
- `a4b5c6d7e8f9` (head) - আমাদের নতুন migration

## সমাধান: Option 1 - Specific Head Upgrade (সবচেয়ে সহজ)

### Step 1: Upgrade to Specific Head

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# আমাদের নতুন migration (a4b5c6d7e8f9) run করুন
flask db upgrade a4b5c6d7e8f9
```

### Step 2: Verify

```bash
# Check current revision
flask db current

# Should show: a4b5c6d7e8f9 (head)
```

### Step 3: Restart Application

```bash
touch passenger_wsgi.py
```

## সমাধান: Option 2 - Manual SQL (যদি Migration কাজ না করে)

phpMyAdmin এ এই SQL run করুন:

```sql
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

তারপর migration history manually update করুন:

```sql
INSERT INTO alembic_version (version_num) VALUES ('a4b5c6d7e8f9')
ON DUPLICATE KEY UPDATE version_num = 'a4b5c6d7e8f9';
```

## সমাধান: Option 3 - Create Merge Migration (যদি দুইটা head merge করতে চান)

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Merge migration তৈরি করুন
flask db merge -m "merge heads" 3002f25a49ae a4b5c6d7e8f9

# Upgrade করুন
flask db upgrade
```

## Quick Fix Command (Recommended)

```bash
cd /home/gronthon/kulawams.xyz && \
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
flask db upgrade a4b5c6d7e8f9 && \
flask db current && \
touch passenger_wsgi.py && \
echo "✅ Migration completed!"
```

## After Migration - Verify

```bash
# Check table exists
# phpMyAdmin এ check করুন
SELECT * FROM active_semester_config;

# Test app
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ OK')"
```

## Important Notes

1. **Option 1 (Specific Head)** সবচেয়ে সহজ - শুধুমাত্র আমাদের নতুন migration run করবে
2. **Option 2 (Manual SQL)** যদি migration commands কাজ না করে
3. **Option 3 (Merge)** যদি দুইটা head merge করতে চান (complex)

**Recommended:** Option 1 ব্যবহার করুন (`flask db upgrade a4b5c6d7e8f9`)

