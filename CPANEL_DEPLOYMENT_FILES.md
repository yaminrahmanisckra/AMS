# cPanel Deployment Guide - Updated Files List

## 📋 Files to Upload to cPanel

### 1. Core Application Files

```
app.py
user_models.py
models.py
extensions.py
error_handler.py
email_config.py
passenger_wsgi.py (for cPanel)
requirements.txt
```

### 2. Blueprints (All Updated Files)

#### Class Management (Most Important Updates)
```
blueprints/class_management/
├── __init__.py
├── models.py          ⚠️ UPDATED (CourseOutline relationship fixes)
├── routes.py          ⚠️ UPDATED (delete_session fix, course outline features)
└── templates/
    └── class_management/
        ├── index.html              ⚠️ UPDATED (Course File button)
        ├── course_file.html        ⚠️ NEW FILE
        └── edit_course_outline.html ⚠️ NEW FILE
```

#### Other Blueprints (Check if updated)
```
blueprints/auth/
├── __init__.py
├── routes.py
└── templates/ (all files)

blueprints/course_management/
├── __init__.py
├── models.py
├── routes.py
└── templates/ (all files)

blueprints/result_management/
├── models.py
├── routes.py
└── templates/ (all files)

blueprints/routine_management/
├── __init__.py
├── models.py
├── routes.py
└── templates/ (all files)

blueprints/student_management/
├── __init__.py
├── models.py
├── routes.py
└── templates/ (all files)
```

### 3. Templates (Root Level)

```
templates/
├── base.html
├── dashboard.html          ⚠️ UPDATED (Remuneration card, Version 2.0.0)
├── login.html
├── register.html
├── profile.html
├── admin_dashboard.html
├── class_management.html
├── result_management.html
├── student_feedback_form.html  ⚠️ UPDATED (Auto-fill fields)
└── (all other template files)
```

### 4. Static Files

```
static/
├── css/
│   └── style.css          ⚠️ UPDATED (sticky header styles)
├── js/
│   └── script.js          ⚠️ UPDATED (marks entry features)
└── Fonts/
    └── kalpurush.ttf
```

### 5. Database Files (For Reference)

```
mysql_schema.sql                    ⚠️ NEW FILE (Complete MySQL schema)
mysql_add_missing_columns.sql       ⚠️ NEW FILE (Safe migration)
MYSQL_SCHEMA_GUIDE.md              ⚠️ NEW FILE (Documentation)
MYSQL_MIGRATION_GUIDE.md           ⚠️ NEW FILE (Documentation)
```

### 6. Configuration Files

```
.env.example                        (Template - don't upload .env itself)
env.example
nginx.conf                          (If using nginx)
```

### 7. Migration Files (If Using Alembic)

```
migrations/
├── alembic.ini
├── env.py
└── versions/
    └── (all migration files)
```

---

## ❌ Files NOT to Upload

### Development Files
```
__pycache__/           (Python cache - will be regenerated)
*.pyc                   (Compiled Python files)
*.pyo                   (Optimized Python files)
.pytest_cache/          (Test cache)
.venv/                  (Virtual environment)
venv/                   (Virtual environment)
venv_feedback/          (Virtual environment)
venv_test/              (Virtual environment)
*.db                    (Local SQLite databases)
instance/               (Local database directory)
*.log                   (Log files)
logs/                   (Log directory)
app.pid                 (Process ID file)
app_output.log          (Output log)
```

### Backup Files
```
*.bak
*.bak2
*.backup.*
*.sqlite
*.db.backup.*
```

### IDE/Editor Files
```
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store
```

### Git Files (Optional - usually not needed)
```
.git/
.gitignore
.gitattributes
```

---

## 📦 Step-by-Step Upload Process

### Step 1: Prepare Files Locally

1. **Create a clean deployment folder:**
```bash
mkdir cpanel_deployment
cd cpanel_deployment
```

2. **Copy all necessary files** (excluding files in "NOT to Upload" list)

### Step 2: Upload via cPanel File Manager or FTP

**Option A: cPanel File Manager**
1. Login to cPanel
2. Go to **File Manager**
3. Navigate to your application directory (usually `public_html` or a subdirectory)
4. Upload files maintaining directory structure

**Option B: FTP/SFTP**
```bash
# Using FTP client like FileZilla
# Upload maintaining exact directory structure
```

### Step 3: Database Setup

1. **Import MySQL Schema:**
   - Go to **phpMyAdmin** in cPanel
   - Select your database
   - Click **Import**
   - Upload `mysql_schema.sql` (for new database)
   - OR upload `mysql_add_missing_columns.sql` (for existing database)

2. **Verify Tables:**
   - Check that all 26 tables are created
   - Verify `course_outline` table has all columns:
     - `course_content_summary`
     - `clo_plo_mapping`
     - `evaluation_policy`
     - `cie_breakdown`
     - `smee_breakdown`
     - `course_file_components`

### Step 4: Environment Configuration

1. **Create/Update `.env` file** in cPanel:
```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=mysql+pymysql://username:password@localhost/database_name
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
USE_SQLITE_LOCAL=false
```

2. **Set file permissions:**
```bash
# Via cPanel Terminal or SSH
chmod 644 .env
chmod 755 app.py
chmod -R 755 blueprints/
chmod -R 755 templates/
chmod -R 755 static/
```

### Step 5: Install Dependencies

1. **Via cPanel Terminal or SSH:**
```bash
cd /path/to/your/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 6: Run Migrations (If Using Alembic)

```bash
source venv/bin/activate
flask db upgrade
```

### Step 7: Restart Application

- If using **Passenger** (cPanel Python App): Restart from cPanel
- If using **WSGI**: Touch `passenger_wsgi.py` or restart via cPanel

---

## 🔍 Verification Checklist

After deployment, verify:

- [ ] All files uploaded successfully
- [ ] Database schema imported correctly
- [ ] All 26 tables exist in database
- [ ] `course_outline` table has all new columns
- [ ] `.env` file configured correctly
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Application restarted
- [ ] Can login to application
- [ ] Course File feature works
- [ ] Course Outline can be created/edited
- [ ] Session delete works (no errors)
- [ ] All other features work as expected

---

## 🚨 Important Notes

1. **Backup First:** Always backup your current production database and files before deployment

2. **Test Environment:** If possible, test in a staging environment first

3. **Database Migration:** 
   - For **new database**: Use `mysql_schema.sql`
   - For **existing database**: Use `mysql_add_missing_columns.sql` (safer, won't delete data)

4. **File Permissions:** Ensure proper permissions (644 for files, 755 for directories)

5. **Python Version:** Ensure cPanel Python version matches your local development version

6. **Dependencies:** Some packages might need compilation - ensure build tools are available

---

## 📝 Quick Upload Command (If Using Git)

If your cPanel supports Git:

```bash
# In cPanel Terminal
cd /path/to/your/app
git pull origin main  # or your branch name
pip install -r requirements.txt
flask db upgrade
# Restart app
```

---

## 🆘 Troubleshooting

### Issue: Import errors after upload
**Solution:** Check file permissions and ensure all `__init__.py` files are present

### Issue: Database connection errors
**Solution:** Verify `.env` file has correct `DATABASE_URL` and database credentials

### Issue: 500 errors
**Solution:** Check error logs in cPanel, verify all dependencies are installed

### Issue: Static files not loading
**Solution:** Check `static/` directory permissions and URL configuration

---

**Last Updated:** 2025-11-25
**Version:** 2.0.0


