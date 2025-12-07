# Deployment Checklist for cPanel

## ✅ Pre-Deployment

- [ ] Backup current production database
- [ ] Backup current production files
- [ ] Test all features locally
- [ ] Review all changes made

## 📤 Files to Upload

### Critical Updated Files (Must Upload)

1. **Application Core:**
   - [ ] `app.py`
   - [ ] `user_models.py`
   - [ ] `models.py`
   - [ ] `extensions.py`
   - [ ] `error_handler.py`
   - [ ] `email_config.py`
   - [ ] `passenger_wsgi.py`

2. **Class Management (Most Important):**
   - [ ] `blueprints/class_management/models.py` ⚠️ **CRITICAL**
   - [ ] `blueprints/class_management/routes.py` ⚠️ **CRITICAL**
   - [ ] `blueprints/class_management/__init__.py`
   - [ ] `blueprints/class_management/templates/class_management/index.html`
   - [ ] `blueprints/class_management/templates/class_management/course_file.html` ⚠️ **NEW**
   - [ ] `blueprints/class_management/templates/class_management/edit_course_outline.html` ⚠️ **NEW**

3. **Templates:**
   - [ ] `templates/dashboard.html` (Remuneration card, Version 2.0.0)
   - [ ] `templates/student_feedback_form.html` (Auto-fill fields)
   - [ ] All other template files

4. **Static Files:**
   - [ ] `static/css/style.css` (Sticky header)
   - [ ] `static/js/script.js` (Marks entry features)
   - [ ] `static/Fonts/kalpurush.ttf`

5. **Database Files:**
   - [ ] `mysql_schema.sql` (For new database)
   - [ ] `mysql_add_missing_columns.sql` (For existing database)
   - [ ] `MYSQL_SCHEMA_GUIDE.md` (Reference)

6. **Other Blueprints:**
   - [ ] All files in `blueprints/auth/`
   - [ ] All files in `blueprints/course_management/`
   - [ ] All files in `blueprints/result_management/`
   - [ ] All files in `blueprints/routine_management/`
   - [ ] All files in `blueprints/student_management/`

7. **Configuration:**
   - [ ] `requirements.txt`
   - [ ] `.env.example` (Don't upload actual `.env`)

8. **Migrations (If Using):**
   - [ ] `migrations/alembic.ini`
   - [ ] `migrations/env.py`
   - [ ] All files in `migrations/versions/`

## 🗄️ Database Setup

- [ ] Create MySQL database in cPanel
- [ ] Create database user and grant permissions
- [ ] Import `mysql_schema.sql` OR run `mysql_add_missing_columns.sql`
- [ ] Verify all 26 tables created
- [ ] Verify `course_outline` table has all columns:
  - [ ] `course_content_summary`
  - [ ] `clo_plo_mapping`
  - [ ] `evaluation_policy`
  - [ ] `cie_breakdown`
  - [ ] `smee_breakdown`
  - [ ] `course_file_components`
- [ ] Verify `class_session` table has:
  - [ ] `course_scope`
  - [ ] `split_group_id`
- [ ] Verify `class_student` table has:
  - [ ] `assessment_absent`

## ⚙️ Configuration

- [ ] Create/Update `.env` file with production values:
  - [ ] `SECRET_KEY`
  - [ ] `DATABASE_URL` (MySQL connection string)
  - [ ] `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`
  - [ ] `USE_SQLITE_LOCAL=false`
- [ ] Set file permissions (644 for files, 755 for directories)
- [ ] Install Python dependencies: `pip install -r requirements.txt`

## 🚀 Post-Deployment

- [ ] Restart application (via cPanel or touch `passenger_wsgi.py`)
- [ ] Test login functionality
- [ ] Test session creation
- [ ] Test session deletion (especially with course_outline)
- [ ] Test Course File feature
- [ ] Test Course Outline creation/editing
- [ ] Test Course Outline DOCX/PDF download
- [ ] Test AI weekly plan generation
- [ ] Test all other existing features
- [ ] Check error logs for any issues

## 🔍 Verification Tests

1. **Session Management:**
   - [ ] Create a new session
   - [ ] Delete a session (should work without errors)
   - [ ] Delete a session with course_outline (should work)

2. **Course Outline:**
   - [ ] Create course outline
   - [ ] Edit course outline
   - [ ] Add weekly plan
   - [ ] Generate AI weekly plan
   - [ ] Download as DOCX
   - [ ] Download as PDF

3. **Other Features:**
   - [ ] Dashboard shows Remuneration card
   - [ ] Footer shows Version 2.0.0
   - [ ] Student feedback form auto-fills fields
   - [ ] Marks entry table has sticky header
   - [ ] All other existing features work

## 📝 Notes

- Always backup before deployment
- Test in staging if possible
- Monitor error logs after deployment
- Keep deployment files organized

---

**Deployment Date:** _______________
**Deployed By:** _______________
**Version:** 2.0.0


