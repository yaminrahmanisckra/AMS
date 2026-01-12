# cPanel Upload Guide - Saved Routines Feature

## 🔴 IMPORTANT: Database Migration আগে করতে হবে!

### Step 1: Database Migration (phpMyAdmin)

1. **cPanel → MySQL Databases → phpMyAdmin** এ যান
2. আপনার database select করুন
3. **SQL** tab এ যান
4. `DATABASE_MIGRATION_FOR_SAVED_ROUTINES.sql` file-এর content copy করে paste করুন
5. **Go** button click করুন

**SQL Script:**
```sql
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

-- 2. Add foreign key for created_by_id
ALTER TABLE `saved_routine`
ADD CONSTRAINT `fk_saved_routine_created_by`
FOREIGN KEY (`created_by_id`) REFERENCES `users`(`id`) ON DELETE SET NULL;

-- 3. Add saved_routine_id column to routine table
ALTER TABLE `routine` 
ADD COLUMN `saved_routine_id` INT NULL AFTER `term`;

-- 4. Add index
ALTER TABLE `routine` 
ADD INDEX `idx_saved_routine_id` (`saved_routine_id`);

-- 5. Add foreign key
ALTER TABLE `routine`
ADD CONSTRAINT `fk_routine_saved_routine`
FOREIGN KEY (`saved_routine_id`) REFERENCES `saved_routine`(`id`) ON DELETE CASCADE;

-- 6. Drop old unique constraint (check if exists first)
ALTER TABLE `routine` 
DROP INDEX IF EXISTS `_day_time_room_uc`;

-- 7. Add new unique constraint
ALTER TABLE `routine` 
ADD UNIQUE KEY `_day_time_room_saved_routine_uc` (`day`, `time_slot`, `room_number`, `saved_routine_id`);
```

**Verification (চেক করার জন্য):**
```sql
-- Check if table exists
DESCRIBE saved_routine;

-- Check if column added
DESCRIBE routine;

-- Should see saved_routine_id column
```

---

### Step 2: Files Upload (cPanel File Manager বা FTP)

এই files upload করুন:

1. ✅ `blueprints/routine_management/models.py`
2. ✅ `blueprints/routine_management/routes.py`
3. ✅ `blueprints/routine_management/templates/routine_management/index.html`
4. ✅ `blueprints/routine_management/templates/routine_management/routine_new.html`
5. ✅ `templates/base.html`

**File Paths in cPanel:**
- `public_html/blueprints/routine_management/models.py`
- `public_html/blueprints/routine_management/routes.py`
- `public_html/blueprints/routine_management/templates/routine_management/index.html`
- `public_html/blueprints/routine_management/templates/routine_management/routine_new.html`
- `public_html/templates/base.html`

---

### Step 3: Application Restart

Terminal বা SSH access থাকলে:
```bash
cd /home/gronthon/kulawams.xyz  # (অথবা আপনার path)
touch passenger_wsgi.py
```

না থাকলে cPanel Python App section থেকে app restart করুন।

---

### Step 4: Testing

1. ✅ Routine Management dashboard এ যান
2. ✅ "Saved Routines" section দেখা যাচ্ছে কিনা check করুন
3. ✅ "Create New Routine" button click করে একটি routine তৈরি করুন (year: 2026)
4. ✅ Routine edit করতে "Edit" button click করুন
5. ✅ Courses panel এ "Batch" filter option আছে কিনা check করুন
6. ✅ Batch filter দিয়ে courses load হচ্ছে কিনা test করুন

---

## ⚠️ Troubleshooting

### Error: Table already exists
- No problem! Table already created, continue with next steps

### Error: Column already exists  
- `saved_routine_id` column already exists, skip step 3

### Error: Foreign key constraint fails
- প্রথমে `saved_routine` table create করুন, তারপর foreign key add করুন

### Error: Constraint name different
- `_day_time_room_uc` constraint-এর নাম ভিন্ন হতে পারে
- phpMyAdmin → routine table → Structure → Indexes এ actual নাম check করুন

---

## ✅ Success Checklist

- [ ] Database migration successful (saved_routine table exists)
- [ ] saved_routine_id column added to routine table
- [ ] All files uploaded
- [ ] Application restarted
- [ ] Saved Routines section visible
- [ ] Can create new saved routine
- [ ] Can load and edit saved routine
- [ ] Batch course filter working
