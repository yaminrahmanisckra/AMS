# Active Semester Management - Manual Upload Instructions

## 📋 Files to Upload

এই feature-এর জন্য নিচের files গুলো সার্ভারে upload করতে হবে:

### 1. Core Application Files

| Local File | Server Path | Description |
|------------|-------------|-------------|
| `app.py` | `/home/gronthon/kulawams.xyz/app.py` | Main application file with routes |
| `utils/semester_utils.py` | `/home/gronthon/kulawams.xyz/utils/semester_utils.py` | Utility functions for semester management |
| `blueprints/course_management/models.py` | `/home/gronthon/kulawams.xyz/blueprints/course_management/models.py` | Database model (ActiveSemesterConfig) |

### 2. Template Files

| Local File | Server Path | Description |
|------------|-------------|-------------|
| `templates/admin/active_semester.html` | `/home/gronthon/kulawams.xyz/templates/admin/active_semester.html` | Active Semester Management page |
| `templates/admin_dashboard.html` | `/home/gronthon/kulawams.xyz/templates/admin_dashboard.html` | Admin dashboard with button |

### 3. Migration File (Optional - if using manual SQL)

| Local File | Server Path | Description |
|------------|-------------|-------------|
| `migrations/versions/add_active_semester_config_model.py` | `/home/gronthon/kulawams.xyz/migrations/versions/add_active_semester_config_model.py` | Database migration (if needed) |

### 4. Blueprint Files (Updated with filtering)

| Local File | Server Path | Description |
|------------|-------------|-------------|
| `blueprints/class_management/routes.py` | `/home/gronthon/kulawams.xyz/blueprints/class_management/routes.py` | Class management with filtering |
| `blueprints/course_management/routes.py` | `/home/gronthon/kulawams.xyz/blueprints/course_management/routes.py` | Course management with filtering |
| `blueprints/result_management/routes.py` | `/home/gronthon/kulawams.xyz/blueprints/result_management/routes.py` | Result management with filtering |

---

## 📤 Upload Steps

### Step 1: cPanel File Manager খুলুন

1. cPanel login করুন
2. **File Manager** click করুন
3. Navigate করুন: `kulawams.xyz` folder

### Step 2: Files Upload করুন

#### A. Main Application File

1. Navigate করুন: `kulawams.xyz` (root folder)
2. `app.py` file select করুন
3. **Upload** button click করুন
4. Local machine থেকে `app.py` select করুন
5. **Replace** confirm করুন (যদি prompt আসে)

#### B. Utils Folder

1. Navigate করুন: `kulawams.xyz/utils/` folder
2. যদি `utils` folder না থাকে → **New Folder** → `utils` create করুন
3. `utils/semester_utils.py` upload করুন
4. `utils/__init__.py` আছে কিনা check করুন (যদি না থাকে → empty file create করুন)

#### C. Models File

1. Navigate করুন: `kulawams.xyz/blueprints/course_management/` folder
2. `models.py` file select করুন
3. **Upload** → Local `blueprints/course_management/models.py` select করুন
4. **Replace** confirm করুন

#### D. Template Files

1. Navigate করুন: `kulawams.xyz/templates/admin/` folder
2. যদি `admin` folder না থাকে → **New Folder** → `admin` create করুন
3. `templates/admin/active_semester.html` upload করুন

4. Navigate করুন: `kulawams.xyz/templates/` folder
5. `admin_dashboard.html` upload করুন (replace করুন)

#### E. Blueprint Routes (Optional - যদি filtering চান)

1. Navigate করুন: `kulawams.xyz/blueprints/class_management/` folder
2. `routes.py` upload করুন (replace করুন)

3. Navigate করুন: `kulawams.xyz/blueprints/course_management/` folder
4. `routes.py` upload করুন (replace করুন)

5. Navigate করুন: `kulawams.xyz/blueprints/result_management/` folder
6. `routes.py` upload করুন (replace করুন)

---

## ✅ Verification Steps

### Step 1: Files Check করুন

cPanel Terminal এ এই commands run করুন:

```bash
cd /home/gronthon/kulawams.xyz

# Check main files
ls -la app.py
ls -la utils/semester_utils.py
ls -la blueprints/course_management/models.py
ls -la templates/admin/active_semester.html
ls -la templates/admin_dashboard.html

# Check if utils/__init__.py exists
ls -la utils/__init__.py
```

**Expected:** সব files দেখা যাওয়া উচিত

### Step 2: Python Import Test করুন

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test imports
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')"
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig OK')"
python -c "from app import create_app; app = create_app(); print('✅ App loaded OK')"
```

**Expected:** সব commands "✅ OK" message দেখাবে

### Step 3: Route Check করুন

```bash
cd /home/gronthon/kulawams.xyz
grep -n "admin/active-semester" app.py
```

**Expected Output:**
```
2019:    @app.route('/admin/active-semester')
2072:    @app.route('/admin/active-semester/set', methods=['POST'])
2130:    @app.route('/admin/active-semester/deactivate', methods=['POST'])
2132:    @app.route('/admin/active-semester/list', methods=['GET'])
```

---

## 🔄 Application Restart

### Step 1: Restart Application

```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
```

### Step 2: Wait 10-15 seconds

Application restart হতে কিছু সময় লাগবে

---

## 🧪 Testing

### Step 1: Browser Test

1. Browser এ login করুন (Admin account)
2. Visit করুন: `https://kulawams.xyz/admin`
3. **"Active Semester Management"** button দেখতে হবে (top-right corner)
4. Button click করুন → Active Semester Management page open হবে

### Step 2: Feature Test

1. **Set Active Semester:**
   - Session, Year, Term, Batch select করুন
   - "Set Active" button click করুন
   - Success message দেখতে হবে

2. **Deactivate Semester:**
   - "Current Active Semesters" section → "Deactivate" button click করুন
   - Confirmation → OK
   - Semester deactivate হবে

---

## ⚠️ Important Notes

1. **File Permissions:** Upload করার পর file permissions check করুন:
   ```bash
   chmod 644 app.py
   chmod 644 utils/semester_utils.py
   chmod 644 blueprints/course_management/models.py
   chmod 644 templates/admin/active_semester.html
   chmod 644 templates/admin_dashboard.html
   ```

2. **Database:** যদি `active_semester_config` table না থাকে, তাহলে manual SQL run করুন (phpMyAdmin):
   ```sql
   CREATE TABLE IF NOT EXISTS active_semester_config (
       id INT(11) NOT NULL AUTO_INCREMENT,
       academic_session VARCHAR(50) NOT NULL,
       year VARCHAR(50) NOT NULL,
       term VARCHAR(50) NOT NULL,
       batch VARCHAR(50) DEFAULT NULL,
       is_active TINYINT(1) NOT NULL DEFAULT 1,
       activated_by VARCHAR(100) DEFAULT NULL,
       activated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
       deactivated_at DATETIME DEFAULT NULL,
       PRIMARY KEY (id),
       INDEX idx_active_semester (academic_session, year, term, batch, is_active)
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
   ```

3. **Alembic Version:** phpMyAdmin এ:
   ```sql
   INSERT INTO alembic_version (version_num) VALUES ('a4b5c6d7e8f9')
   ON DUPLICATE KEY UPDATE version_num = 'a4b5c6d7e8f9';
   ```

---

## 📝 Quick Checklist

- [ ] `app.py` uploaded
- [ ] `utils/semester_utils.py` uploaded
- [ ] `utils/__init__.py` exists
- [ ] `blueprints/course_management/models.py` uploaded
- [ ] `templates/admin/active_semester.html` uploaded
- [ ] `templates/admin_dashboard.html` uploaded
- [ ] Blueprint routes uploaded (optional)
- [ ] Files verified (ls commands)
- [ ] Python imports tested
- [ ] Routes verified (grep command)
- [ ] Application restarted (touch passenger_wsgi.py)
- [ ] Browser tested

---

## 🆘 Troubleshooting

### Error: "Could not build url for endpoint 'admin_active_semester'"
- **Solution:** `app.py` file সঠিকভাবে upload হয়েছে কিনা check করুন

### Error: "ImportError: cannot import name 'ActiveSemesterConfig'"
- **Solution:** `blueprints/course_management/models.py` file upload করুন

### Error: "ImportError: cannot import name 'get_active_semesters'"
- **Solution:** `utils/semester_utils.py` এবং `utils/__init__.py` upload করুন

### Error: "404 Not Found" on `/admin/active-semester`
- **Solution:** `app.py` file upload করুন এবং application restart করুন

### Error: "Table 'active_semester_config' doesn't exist"
- **Solution:** phpMyAdmin এ manual SQL run করুন (উপরে দেওয়া আছে)

---

## 📞 Support

যদি কোনো সমস্যা হয়:
1. Error message copy করুন
2. Terminal output share করুন
3. Browser console errors check করুন

