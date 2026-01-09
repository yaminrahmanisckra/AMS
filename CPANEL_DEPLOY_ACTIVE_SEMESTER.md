# cPanel Deployment Guide: Active Semester Management Feature

এই গাইড অনুসরণ করে নতুন Active Semester Management feature টি cPanel এ deploy করুন।

**Project Configuration:**
- Project Path: `/home/gronthon/kulawams.xyz`
- Virtual Environment: `/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate`
- Domain: `kulawams.xyz`

## ✅ Pre-Deployment Checklist

- [x] সব কোড GitHub এ push করা হয়েছে
- [ ] Production database backup নেওয়া হয়েছে
- [ ] Production files backup নেওয়া হয়েছে

## 📋 Deployment Steps

### Step 1: cPanel Terminal এ Connect করুন

1. cPanel login করুন
2. **Terminal** বা **SSH Access** খুলুন
3. Project directory তে যান এবং virtual environment activate করুন:
   ```bash
   source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && cd /home/gronthon/kulawams.xyz
   ```

### Step 2: Git থেকে Latest Code Pull করুন

```bash
# Virtual environment activate করুন
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Project directory তে যান
cd /home/gronthon/kulawams.xyz

# Git repository pull করুন
git pull origin main

# অথবা যদি branch name ভিন্ন হয়
git pull origin master
```

### Step 3: Automated Deployment Script ব্যবহার করুন (Recommended)

```bash
# Script file cPanel এ upload করুন (যদি না থাকে)
# অথবা Terminal এ create করুন

# Script executable করুন
chmod +x deploy_active_semester.sh

# Script run করুন
./deploy_active_semester.sh
```

### Step 4: Manual Deployment (যদি Script কাজ না করে)

#### A. Virtual Environment Activate করুন:
```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
cd /home/gronthon/kulawams.xyz
```

#### B. Database Migration Run করুন:

**Option 1: Flask Migration (Recommended)**
```bash
flask db upgrade
```

**Option 2: Python Script**
```bash
python run_migration.py
```

**Option 3: Manual SQL (যদি migration কাজ না করে)**

phpMyAdmin এ গিয়ে এই SQL run করুন:

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

#### C. File Permissions Set করুন:
```bash
cd /home/gronthon/kulawams.xyz
chmod 644 utils/semester_utils.py
chmod 644 templates/admin/active_semester.html
chmod 755 utils/
chmod 755 templates/admin/
```

#### D. Application Restart করুন:

**cPanel Python App থেকে:**
1. cPanel এ **Setup Python App** এ যান
2. `kulawams.xyz` app খুঁজুন
3. **Restart** button click করুন

**অথবা Terminal থেকে:**
```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
```

### Step 5: নতুন Files Verify করুন

নিম্নলিখিত files গুলো upload হয়েছে কিনা check করুন:

```bash
cd /home/gronthon/kulawams.xyz
ls -la utils/semester_utils.py
ls -la templates/admin/active_semester.html
ls -la migrations/versions/add_active_semester_config_model.py
ls -la blueprints/course_management/models.py
```

### Step 6: Database Table Verify করুন

phpMyAdmin এ গিয়ে verify করুন যে `active_semester_config` table তৈরি হয়েছে:

```sql
-- Table exists check
SHOW TABLES LIKE 'active_semester_config';

-- Table structure check
DESCRIBE active_semester_config;

-- Should show:
-- id, academic_session, year, term, batch, is_active, 
-- activated_by, activated_at, deactivated_at

-- Check if table is empty (should be empty initially)
SELECT COUNT(*) FROM active_semester_config;
```

## ✅ Post-Deployment Testing

### 1. Login Test

- [ ] Admin account দিয়ে login করতে পারছেন
- [ ] Admin Dashboard load হচ্ছে

### 2. Active Semester Feature Test

- [ ] `https://kulawams.xyz/admin/active-semester` page open হচ্ছে
- [ ] Available sessions দেখাচ্ছে
- [ ] Active semester set করতে পারছেন
- [ ] Current active semester দেখাচ্ছে

### 3. Filtering Test

**Class Management:**
- [ ] Class Management page open হচ্ছে
- [ ] শুধুমাত্র Active Semester এর sessions দেখাচ্ছে (non-admin)
- [ ] Admin সব sessions দেখতে পারছেন

**Course Management:**
- [ ] Student Registration page কাজ করছে
- [ ] Coordinator Registration page কাজ করছে
- [ ] Active semester filtering কাজ করছে

**Result Management:**
- [ ] Result Management page open হচ্ছে
- [ ] Active semester এর results দেখাচ্ছে
- [ ] Archive view কাজ করছে

**Exam Evaluation:**
- [ ] Exam Evaluation page কাজ করছে
- [ ] Active semester filtering কাজ করছে

### 4. Backward Compatibility Test

- [ ] কোনো Active Semester set না করলেও সব data দেখাচ্ছে
- [ ] পুরাতন features সব কাজ করছে
- [ ] কোনো error log এ আসছে না

## 🔍 Verification Commands

### Check Migration Status

```bash
# Virtual environment activate করুন
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
cd /home/gronthon/kulawams.xyz

# Check migration status
flask db current
flask db history
```

### Check Error Logs

```bash
cd /home/gronthon/kulawams.xyz

# Application logs
tail -f logs/app_errors.log
tail -f logs/detailed_errors.log

# Real-time log monitoring
tail -50 logs/app_errors.log
```

### Check Database

```bash
# MySQL connection test (cPanel credentials ব্যবহার করুন)
# phpMyAdmin এ check করুন
```

## 🚨 Troubleshooting

### Issue 1: Virtual Environment Not Found

**Error:** `No such file or directory: /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate`

**Solution:**
```bash
# Check if path exists
ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Check alternative paths
ls -la /home/gronthon/virtualenv/kulawams.xyz/*/bin/activate

# cPanel Python App থেকে virtual environment path check করুন
```

### Issue 2: Migration Fails

**Error:** `Table 'active_semester_config' already exists`

**Solution:**
```bash
# phpMyAdmin এ check করুন table আছে কিনা
# যদি exists, তাহলে migration skip হবে
# অথবা manually drop করে আবার run করুন
```

### Issue 3: Import Error

**Error:** `ImportError: No module named 'utils.semester_utils'`

**Solution:**
```bash
cd /home/gronthon/kulawams.xyz

# Check if file exists
ls -la utils/semester_utils.py

# Check __init__.py exists
ls -la utils/__init__.py

# Check Python path
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "import sys; print(sys.path)"
```

### Issue 4: 500 Error on Admin Page

**Error:** Internal Server Error on `/admin/active-semester`

**Solution:**
```bash
cd /home/gronthon/kulawams.xyz
tail -50 logs/app_errors.log

# Check specific errors
grep -i "semester\|active_semester" logs/app_errors.log
```

### Issue 5: Passenger WSGI Not Found

**Error:** `passenger_wsgi.py not found`

**Solution:**
- cPanel Python App থেকে restart করুন
- অথবা file exists কিনা check করুন:
```bash
cd /home/gronthon/kulawams.xyz
ls -la passenger_wsgi.py
```

## 📝 Quick Deployment Commands (Copy-Paste Ready)

```bash
# All-in-one command
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
cd /home/gronthon/kulawams.xyz && \
git pull origin main && \
flask db upgrade && \
touch passenger_wsgi.py && \
echo "✅ Deployment completed!"
```

## 📞 Support

যদি কোনো সমস্যা হয়:

1. **Error Logs Check করুন:**
   ```bash
   cd /home/gronthon/kulawams.xyz
   tail -100 logs/app_errors.log
   ```

2. **Database Check করুন:** phpMyAdmin এ table structure verify করুন

3. **Git Status Check করুন:** সব files properly committed আছে কিনা
   ```bash
   cd /home/gronthon/kulawams.xyz
   git status
   ```

## ✅ Final Checklist

Deployment সম্পন্ন হওয়ার পর verify করুন:

- [ ] Database migration successful
- [ ] `active_semester_config` table created
- [ ] Admin page (`/admin/active-semester`) accessible
- [ ] Active semester set করা যায়
- [ ] Filtering works in all modules
- [ ] No errors in logs
- [ ] All existing features working
- [ ] Backward compatibility maintained

---

**Deployment Date:** _______________
**Deployed By:** _______________
**Version:** Active Semester Management v1.0
**Domain:** kulawams.xyz
