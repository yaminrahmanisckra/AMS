# Quick Deployment Checklist - Active Semester Feature

## 🚀 Fast Track Deployment (5 Minutes)

### 1. cPanel Terminal এ এই Commands Run করুন:

```bash
# Virtual environment activate করুন এবং project directory তে যান
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && cd /home/gronthon/kulawams.xyz

# Pull latest code
git pull origin main

# Run migration
flask db upgrade
# অথবা
python run_migration.py

# Restart app
touch passenger_wsgi.py
```

### One-Line Command (Copy-Paste Ready):

```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && cd /home/gronthon/kulawams.xyz && git pull origin main && flask db upgrade && touch passenger_wsgi.py
```

### 2. Verify Database Table:

phpMyAdmin এ যান এবং run করুন:
```sql
SELECT * FROM active_semester_config;
```

যদি table না থাকে, তাহলে এই SQL run করুন:
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

### 3. Test করুন:

1. Admin login করুন
2. Visit: `/admin/active-semester`
3. একটি Active Semester set করুন
4. Check করুন filtering কাজ করছে কিনা

---

## ✅ Success Indicators

- ✅ `/admin/active-semester` page load হচ্ছে
- ✅ Active semester set করা যায়
- ✅ Filtering কাজ করছে (non-admin users শুধু active semester দেখছে)
- ✅ Admin সব data দেখতে পারছেন
- ✅ কোনো error log এ আসছে না

---

## ❌ Common Issues & Quick Fixes

### Table doesn't exist:
→ phpMyAdmin এ SQL run করুন (উপরে দেওয়া)

### 500 Error:
→ Check `logs/app_errors.log`

### Import Error:
→ Check `utils/semester_utils.py` file exists
→ Check `templates/admin/active_semester.html` exists

### Migration fails:
→ Manual SQL run করুন (উপরে দেওয়া)

---

**Detailed Guide:** See `CPANEL_DEPLOY_ACTIVE_SEMESTER.md`

