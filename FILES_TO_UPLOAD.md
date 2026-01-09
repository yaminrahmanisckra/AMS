# Files to Upload - Active Semester Management Feature

## 📋 Upload Location: `/home/gronthon/kulawams.xyz/`

### ✅ New Files (Must Upload)

এই files গুলো **NEW** এবং **MUST UPLOAD** করতে হবে:

#### 1. Utility Functions
**Location:** `utils/semester_utils.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/utils/semester_utils.py`
- **Status:** ⚠️ **CRITICAL** - Missing in server
- **Action:** Upload to `utils/` folder
- **Permission:** `644` (chmod 644)

#### 2. Admin Template
**Location:** `templates/admin/active_semester.html`
- **Full Path:** `/home/gronthon/kulawams.xyz/templates/admin/active_semester.html`
- **Status:** ⚠️ **CRITICAL** - Missing in server
- **Action:** Upload to `templates/admin/` folder
- **Permission:** `644` (chmod 644)

#### 3. Migration File
**Location:** `migrations/versions/add_active_semester_config_model.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/migrations/versions/add_active_semester_config_model.py`
- **Status:** ⚠️ **IMPORTANT** - For database migration
- **Action:** Upload to `migrations/versions/` folder
- **Permission:** `644` (chmod 644)

### ✅ Updated Files (Already Pulled from Git)

এই files গুলো **ALREADY UPDATED** via git pull, কিন্তু conflicts আছে। Conflicts resolve করার পর automatically ঠিক হয়ে যাবে:

#### 1. Main Application File
**Location:** `app.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/app.py`
- **Status:** ✅ Pulled (but has conflicts)
- **Action:** Resolve conflicts (use GitHub version)
- **Changes:** Admin routes for active semester management

#### 2. Course Management Models
**Location:** `blueprints/course_management/models.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/blueprints/course_management/models.py`
- **Status:** ✅ Pulled
- **Changes:** ActiveSemesterConfig model added

#### 3. Course Management Routes
**Location:** `blueprints/course_management/routes.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/blueprints/course_management/routes.py`
- **Status:** ✅ Pulled
- **Changes:** Active semester filtering added

#### 4. Class Management Routes
**Location:** `blueprints/class_management/routes.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/blueprints/class_management/routes.py`
- **Status:** ✅ Pulled
- **Changes:** Active semester filtering added

#### 5. Result Management Routes
**Location:** `blueprints/result_management/routes.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/blueprints/result_management/routes.py`
- **Status:** ✅ Pulled (but has conflicts)
- **Action:** Resolve conflicts (use GitHub version)
- **Changes:** Active semester filtering added

#### 6. Admin Dashboard Template
**Location:** `templates/admin_dashboard.html`
- **Full Path:** `/home/gronthon/kulawams.xyz/templates/admin_dashboard.html`
- **Status:** ✅ Pulled
- **Changes:** Link to active semester management added

#### 7. Passenger WSGI
**Location:** `passenger_wsgi.py`
- **Full Path:** `/home/gronthon/kulawams.xyz/passenger_wsgi.py`
- **Status:** ✅ Pulled (but has conflicts)
- **Action:** Resolve conflicts (use GitHub version)

### 📁 Directory Structure After Upload

```
/home/gronthon/kulawams.xyz/
├── app.py (✅ Updated - resolve conflicts)
├── passenger_wsgi.py (✅ Updated - resolve conflicts)
│
├── utils/ (⚠️ MUST CREATE if not exists)
│   ├── __init__.py (✅ Ensure exists)
│   └── semester_utils.py (❌ MISSING - MUST UPLOAD)
│
├── templates/
│   ├── admin/
│   │   └── active_semester.html (❌ MISSING - MUST UPLOAD)
│   └── admin_dashboard.html (✅ Updated)
│
├── blueprints/
│   ├── course_management/
│   │   └── models.py (✅ Updated)
│   │   └── routes.py (✅ Updated)
│   ├── class_management/
│   │   └── routes.py (✅ Updated)
│   └── result_management/
│       └── routes.py (✅ Updated - resolve conflicts)
│
└── migrations/
    └── versions/
        └── add_active_semester_config_model.py (❌ MISSING - MUST UPLOAD)
```

## 🚀 Quick Upload Guide

### Method 1: Using cPanel File Manager

#### Step 1: Upload `utils/semester_utils.py`

1. cPanel এ login করুন
2. **File Manager** খুলুন
3. Navigate করুন: `/home/gronthon/kulawams.xyz/`
4. `utils/` folder আছে কিনা check করুন
   - যদি না থাকে, create করুন: **New Folder** > নাম: `utils`
5. `utils/` folder এ click করুন
6. **Upload** button click করুন
7. `semester_utils.py` file upload করুন
8. Permissions set করুন: Right click > Change Permissions > `644`

#### Step 2: Upload `templates/admin/active_semester.html`

1. Navigate করুন: `/home/gronthon/kulawams.xyz/templates/`
2. `admin/` folder আছে কিনা check করুন
   - যদি না থাকে, create করুন: **New Folder** > নাম: `admin`
3. `admin/` folder এ click করুন
4. **Upload** button click করুন
5. `active_semester.html` file upload করুন
6. Permissions set করুন: `644`

#### Step 3: Upload Migration File

1. Navigate করুন: `/home/gronthon/kulawams.xyz/migrations/versions/`
2. **Upload** button click করুন
3. `add_active_semester_config_model.py` file upload করুন
4. Permissions set করুন: `644`

#### Step 4: Ensure `utils/__init__.py` exists

1. Navigate করুন: `/home/gronthon/kulawams.xyz/utils/`
2. `__init__.py` file আছে কিনা check করুন
   - যদি না থাকে, **New File** > নাম: `__init__.py` > content: (empty)
3. Permissions set করুন: `644`

### Method 2: Using FTP/SFTP

**FTP Client (FileZilla, WinSCP, etc.) দিয়ে:**

1. Connect করুন আপনার server এ
2. Navigate করুন: `/home/gronthon/kulawams.xyz/`
3. Upload করুন:
   - `utils/semester_utils.py` → `utils/` folder
   - `templates/admin/active_semester.html` → `templates/admin/` folder
   - `migrations/versions/add_active_semester_config_model.py` → `migrations/versions/` folder
4. Ensure `utils/__init__.py` exists

### Method 3: Using Terminal/SSH

```bash
# Navigate to project
cd /home/gronthon/kulawams.xyz

# Create directories if not exist
mkdir -p utils
mkdir -p templates/admin
mkdir -p migrations/versions

# Upload files via SCP (from your local machine)
# scp utils/semester_utils.py gronthon@your-server:/home/gronthon/kulawams.xyz/utils/
# scp templates/admin/active_semester.html gronthon@your-server:/home/gronthon/kulawams.xyz/templates/admin/
# scp migrations/versions/add_active_semester_config_model.py gronthon@your-server:/home/gronthon/kulawams.xyz/migrations/versions/

# Set permissions
chmod 644 utils/semester_utils.py
chmod 644 templates/admin/active_semester.html
chmod 644 migrations/versions/add_active_semester_config_model.py
chmod 755 utils/
chmod 755 templates/admin/
touch utils/__init__.py
chmod 644 utils/__init__.py
```

## ✅ Verification Checklist

Upload করার পর verify করুন:

```bash
cd /home/gronthon/kulawams.xyz

# Check files exist
ls -la utils/semester_utils.py
ls -la templates/admin/active_semester.html
ls -la migrations/versions/add_active_semester_config_model.py

# Check permissions
ls -l utils/semester_utils.py
ls -l templates/admin/active_semester.html

# Test Python import
python -c "from utils.semester_utils import get_active_semesters; print('✅ OK')"
```

## 📝 Files Summary

| File | Location | Status | Priority | Action |
|------|----------|--------|----------|--------|
| `utils/semester_utils.py` | `utils/` | ❌ Missing | ⚠️ CRITICAL | Upload |
| `templates/admin/active_semester.html` | `templates/admin/` | ❌ Missing | ⚠️ CRITICAL | Upload |
| `migrations/versions/add_active_semester_config_model.py` | `migrations/versions/` | ❌ Missing | ⚠️ IMPORTANT | Upload |
| `app.py` | Root | ✅ Updated | Resolve conflicts | Use GitHub version |
| `blueprints/result_management/routes.py` | `blueprints/result_management/` | ✅ Updated | Resolve conflicts | Use GitHub version |
| `passenger_wsgi.py` | Root | ✅ Updated | Resolve conflicts | Use GitHub version |

## 🔍 Important Notes

1. **Directory Structure:** Ensure these directories exist:
   - `utils/`
   - `templates/admin/`
   - `migrations/versions/`

2. **Permissions:**
   - Files: `644` (rw-r--r--)
   - Directories: `755` (rwxr-xr-x)

3. **File Sources:**
   - Local machine থেকে upload করুন
   - অথবা GitHub থেকে download করে upload করুন

4. **After Upload:**
   - Conflicts resolve করুন (Step 1 from FIX_DEPLOYMENT_ISSUES.md)
   - Migration run করুন: `flask db upgrade`
   - App restart করুন: `touch passenger_wsgi.py`

---

**Total Files to Upload: 3**
1. `utils/semester_utils.py`
2. `templates/admin/active_semester.html`
3. `migrations/versions/add_active_semester_config_model.py`

