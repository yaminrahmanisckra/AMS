# 📤 Manual Upload Checklist - Active Semester Management

## 🎯 Files to Upload (সব files একসাথে)

### ✅ Core Files (অবশ্যই upload করতে হবে)

```
1. app.py
   → Upload to: /home/gronthon/kulawams.xyz/app.py
   → Replace existing file

2. utils/semester_utils.py
   → Upload to: /home/gronthon/kulawams.xyz/utils/semester_utils.py
   → Create utils folder if doesn't exist

3. utils/__init__.py (empty file)
   → Upload to: /home/gronthon/kulawams.xyz/utils/__init__.py
   → Create if doesn't exist

4. blueprints/course_management/models.py
   → Upload to: /home/gronthon/kulawams.xyz/blueprints/course_management/models.py
   → Replace existing file

5. templates/admin/active_semester.html
   → Upload to: /home/gronthon/kulawams.xyz/templates/admin/active_semester.html
   → Create admin folder if doesn't exist

6. templates/admin_dashboard.html
   → Upload to: /home/gronthon/kulawams.xyz/templates/admin_dashboard.html
   → Replace existing file
```

### ⚙️ Optional Files (Filtering এর জন্য)

```
7. blueprints/class_management/routes.py
   → Upload to: /home/gronthon/kulawams.xyz/blueprints/class_management/routes.py
   → Replace existing file

8. blueprints/course_management/routes.py
   → Upload to: /home/gronthon/kulawams.xyz/blueprints/course_management/routes.py
   → Replace existing file

9. blueprints/result_management/routes.py
   → Upload to: /home/gronthon/kulawams.xyz/blueprints/result_management/routes.py
   → Replace existing file
```

---

## 📋 Step-by-Step Upload Process

### Method 1: cPanel File Manager

1. **cPanel Login** → **File Manager**

2. **Navigate to:** `kulawams.xyz` folder

3. **For each file:**
   - Navigate to target folder
   - Click **Upload** button
   - Select file from local machine
   - Click **Upload**
   - Confirm **Replace** if asked

4. **Create folders if needed:**
   - `utils` folder (if doesn't exist)
   - `templates/admin` folder (if doesn't exist)

### Method 2: FTP Client (FileZilla, WinSCP, etc.)

1. **Connect to server:**
   - Host: `server9.hostingbangladesh.com` (or your server)
   - Username: `gronthon`
   - Password: (your password)
   - Port: `21` (FTP) or `22` (SFTP)

2. **Navigate to:** `/home/gronthon/kulawams.xyz`

3. **Upload files:**
   - Drag and drop files to correct folders
   - Replace existing files

---

## ✅ After Upload - Verification

### Terminal Commands (cPanel Terminal)

```bash
# 1. Go to project directory
cd /home/gronthon/kulawams.xyz

# 2. Check all files exist
echo "=== Checking Files ==="
ls -la app.py
ls -la utils/semester_utils.py
ls -la utils/__init__.py
ls -la blueprints/course_management/models.py
ls -la templates/admin/active_semester.html
ls -la templates/admin_dashboard.html

# 3. Test Python imports
echo "=== Testing Imports ==="
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')"
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig OK')"
python -c "from app import create_app; app = create_app(); print('✅ App loaded OK')"

# 4. Check routes
echo "=== Checking Routes ==="
grep -n "admin/active-semester" app.py

# 5. Restart application
echo "=== Restarting Application ==="
touch passenger_wsgi.py
echo "✅ Application restarted. Wait 10-15 seconds."
```

---

## 🧪 Browser Test

1. **Login:** Admin account দিয়ে login করুন
2. **Visit:** `https://kulawams.xyz/admin`
3. **Check:** "Active Semester Management" button দেখতে হবে
4. **Click:** Button click করুন
5. **Test:** 
   - Set Active Semester
   - Deactivate Semester

---

## 📝 Quick Reference

### File Locations Summary

| File | Server Path |
|------|-------------|
| `app.py` | `/home/gronthon/kulawams.xyz/app.py` |
| `semester_utils.py` | `/home/gronthon/kulawams.xyz/utils/semester_utils.py` |
| `__init__.py` | `/home/gronthon/kulawams.xyz/utils/__init__.py` |
| `models.py` | `/home/gronthon/kulawams.xyz/blueprints/course_management/models.py` |
| `active_semester.html` | `/home/gronthon/kulawams.xyz/templates/admin/active_semester.html` |
| `admin_dashboard.html` | `/home/gronthon/kulawams.xyz/templates/admin_dashboard.html` |

### Important Commands

```bash
# Restart application
cd /home/gronthon/kulawams.xyz && touch passenger_wsgi.py

# Check if route exists
grep -n "admin/active-semester" app.py

# Test import
python -c "from utils.semester_utils import get_active_semesters; print('OK')"
```

---

## ⚠️ Common Issues

### Issue 1: "404 Not Found"
- **Fix:** `app.py` upload করুন এবং `touch passenger_wsgi.py` run করুন

### Issue 2: "ImportError"
- **Fix:** Missing files upload করুন (check `ls -la` commands)

### Issue 3: Button not showing
- **Fix:** `templates/admin_dashboard.html` upload করুন

### Issue 4: Deactivate button not working
- **Fix:** `templates/admin/active_semester.html` upload করুন

---

## ✅ Final Checklist

- [ ] All 6 core files uploaded
- [ ] Optional files uploaded (if needed)
- [ ] Files verified (ls commands)
- [ ] Python imports tested
- [ ] Routes verified
- [ ] Application restarted
- [ ] Browser tested

---

**Note:** প্রতিবার নতুন feature add করার সময়, এই checklist follow করুন।

