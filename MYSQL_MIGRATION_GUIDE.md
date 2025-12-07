# MySQL Database Migration Guide - Safe Column Addition

## ⚠️ Important: Data Safety

**`mysql_schema.sql`** file-টি existing data **মুছে ফেলবে না** কারণ এটি `CREATE TABLE IF NOT EXISTS` ব্যবহার করে।

### কি হবে:
- ✅ Table না থাকলে তৈরি হবে
- ✅ Table থাকলে existing data অক্ষত থাকবে
- ❌ কিন্তু existing table-এ missing columns যোগ হবে না

## 🔧 Solution: Missing Columns যোগ করার জন্য

### Option 1: Safe Migration Script (Recommended)

`mysql_add_missing_columns.sql` file ব্যবহার করুন। এটি:
- ✅ Existing data মুছে ফেলবে না
- ✅ শুধুমাত্র missing columns যোগ করবে
- ✅ Column already থাকলে skip করবে
- ✅ Safe to run multiple times

### Option 2: Manual ALTER TABLE

phpMyAdmin-এ গিয়ে manually missing columns যোগ করুন:

```sql
-- class_session table-এ missing columns যোগ করুন
ALTER TABLE class_session 
ADD COLUMN IF NOT EXISTS course_scope VARCHAR(10) NOT NULL DEFAULT 'full',
ADD COLUMN IF NOT EXISTS split_group_id VARCHAR(36) NULL;

-- class_student table-এ missing column যোগ করুন
ALTER TABLE class_student 
ADD COLUMN IF NOT EXISTS assessment_absent TEXT NULL;

-- course_outline table-এ missing columns যোগ করুন
ALTER TABLE course_outline 
ADD COLUMN IF NOT EXISTS course_content_summary TEXT NULL,
ADD COLUMN IF NOT EXISTS clo_plo_mapping TEXT NULL,
ADD COLUMN IF NOT EXISTS evaluation_policy TEXT NULL,
ADD COLUMN IF NOT EXISTS cie_breakdown TEXT NULL,
ADD COLUMN IF NOT EXISTS smee_breakdown TEXT NULL,
ADD COLUMN IF NOT EXISTS course_file_components TEXT NULL;
```

**Note**: MySQL 5.7+ এ `IF NOT EXISTS` support করে না, তাই `mysql_add_missing_columns.sql` script ব্যবহার করুন যা automatically check করে।

## 📋 Step-by-Step Migration Process

### Scenario 1: Brand New Database
1. `mysql_schema.sql` import করুন
2. সব tables এবং columns তৈরি হবে

### Scenario 2: Existing Database (Data আছে)
1. **Backup নিন প্রথমে!** (Very Important)
2. `mysql_add_missing_columns.sql` import করুন
3. Missing columns যোগ হবে, existing data অক্ষত থাকবে

### Scenario 3: Verify Missing Columns
phpMyAdmin-এ এই query run করুন:

```sql
-- Check class_session columns
SHOW COLUMNS FROM class_session LIKE 'course_scope';
SHOW COLUMNS FROM class_session LIKE 'split_group_id';

-- Check class_student columns
SHOW COLUMNS FROM class_student LIKE 'assessment_absent';

-- Check course_outline columns
SHOW COLUMNS FROM course_outline LIKE 'course_content_summary';
SHOW COLUMNS FROM course_outline LIKE 'clo_plo_mapping';
SHOW COLUMNS FROM course_outline LIKE 'evaluation_policy';
SHOW COLUMNS FROM course_outline LIKE 'cie_breakdown';
SHOW COLUMNS FROM course_outline LIKE 'smee_breakdown';
SHOW COLUMNS FROM course_outline LIKE 'course_file_components';
```

## 🛡️ Safety Checklist

Migration করার আগে:

- [ ] **Database backup নিন** (phpMyAdmin → Export)
- [ ] Existing data count করুন (যেমন: `SELECT COUNT(*) FROM class_session;`)
- [ ] Migration script run করুন
- [ ] Data count আবার check করুন (same হওয়া উচিত)
- [ ] Application test করুন

## 📝 Important Columns to Add

### class_session table:
- `course_scope` (VARCHAR(10), DEFAULT 'full')
- `split_group_id` (VARCHAR(36))

### class_student table:
- `assessment_absent` (TEXT)

### course_outline table:
- `course_content_summary` (TEXT)
- `clo_plo_mapping` (TEXT)
- `evaluation_policy` (TEXT)
- `cie_breakdown` (TEXT)
- `smee_breakdown` (TEXT)
- `course_file_components` (TEXT)

## ⚠️ Common Issues

### Issue 1: "Column already exists" Error
**Solution**: `mysql_add_missing_columns.sql` script automatically handle করে। যদি manual ALTER TABLE করেন, error ignore করুন।

### Issue 2: Data Loss Concern
**Solution**: 
1. Backup নিন
2. Test environment-এ প্রথমে try করুন
3. `mysql_add_missing_columns.sql` script safe - এটি শুধু missing columns যোগ করে

### Issue 3: Foreign Key Errors
**Solution**: Script run করার আগে foreign key checks temporarily disable করুন:

```sql
SET FOREIGN_KEY_CHECKS = 0;
-- Run migration script
SET FOREIGN_KEY_CHECKS = 1;
```

## ✅ Verification After Migration

```sql
-- Check all tables exist
SHOW TABLES;

-- Check specific columns
SELECT COLUMN_NAME 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = 'your_database_name' 
AND TABLE_NAME = 'class_session' 
AND COLUMN_NAME IN ('course_scope', 'split_group_id');

-- Verify data is intact
SELECT COUNT(*) FROM class_session;
SELECT COUNT(*) FROM class_student;
SELECT COUNT(*) FROM course_outline;
```

## 📞 Summary

- **`mysql_schema.sql`**: New database-এর জন্য (existing data মুছে ফেলবে না, কিন্তু missing columns যোগ করবে না)
- **`mysql_add_missing_columns.sql`**: Existing database-এ missing columns যোগ করার জন্য (100% safe, data মুছে ফেলবে না)

**Always backup before migration!** 🛡️


