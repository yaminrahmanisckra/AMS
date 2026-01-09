# Git Conflict Resolution Guide - kulawams.xyz

## সমস্যা

Git pull করার সময় conflict হয়েছে কারণ:
1. Local files এ পরিবর্তন হয়েছে যা GitHub এর সাথে conflict করছে
2. Untracked file আছে যা overwrite হতে পারে

## Solution: Safe Deployment Commands

### Option 1: Stash Local Changes (Recommended - Safe)

```bash
# Virtual environment activate করুন
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
cd /home/gronthon/kulawams.xyz

# Local changes stash করুন (temporarily save)
git stash push -m "Local changes before deployment $(date +%Y%m%d_%H%M%S)"

# Untracked files backup করুন এবং remove করুন
git clean -fd

# Now pull
git pull origin main

# Stashed changes আবার apply করুন (যদি প্রয়োজন হয়)
git stash pop
```

### Option 2: Backup Local Changes and Reset (If you want to use GitHub version)

```bash
# Virtual environment activate করুন
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
cd /home/gronthon/kulawams.xyz

# Backup conflicting files
mkdir -p backup_$(date +%Y%m%d_%H%M%S)
git diff --name-only | xargs cp --parents -t backup_$(date +%Y%m%d_%H%M%S)/
cp fix_course_code_unique_constraint.sql backup_$(date +%Y%m%d_%H%M%S)/ 2>/dev/null || true

# Reset local changes (use GitHub version)
git reset --hard origin/main

# Remove untracked files
git clean -fd

# Pull latest
git pull origin main
```

### Option 3: Commit Local Changes First (If you want to keep them)

```bash
# Virtual environment activate করুন
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
cd /home/gronthon/kulawams.xyz

# Local changes commit করুন
git add .
git commit -m "Local production changes before merge"

# Untracked file handle করুন
rm fix_course_code_unique_constraint.sql  # অথবা commit করুন

# Pull and merge
git pull origin main

# If conflicts occur, resolve them manually
```

## Quick Fix Command (Copy-Paste Ready)

**যদি আপনি GitHub এর version ব্যবহার করতে চান (production এ recommended):**

```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
cd /home/gronthon/kulawams.xyz && \
git stash push -m "Local changes $(date +%Y%m%d_%H%M%S)" && \
git clean -fd && \
git pull origin main && \
flask db upgrade && \
touch passenger_wsgi.py
```

**যদি local changes রাখতে চান:**

```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
cd /home/gronthon/kulawams.xyz && \
git add . && \
git commit -m "Production changes" && \
rm -f fix_course_code_unique_constraint.sql && \
git pull origin main && \
flask db upgrade && \
touch passenger_wsgi.py
```

## Conflicting Files List

এই files গুলোতে local changes আছে:
- `app.py`
- `blueprints/course_management/models.py`
- `blueprints/course_management/routes.py`
- `blueprints/course_management/templates/course_management/coordinator_register_student.html`
- `blueprints/course_management/templates/course_management/coordinator_registrations.html`
- `blueprints/course_management/templates/course_management/student_registration.html`
- `blueprints/result_management/routes.py`
- `blueprints/result_management/templates/result_management/rm_add_marks.html`
- `extensions.py`
- `passenger_wsgi.py`
- `templates/exam_committee_chief/custom_remuneration.html`
- `templates/exam_evaluation_marks.html`
- `templates/remuneration_pdf_template.html`
- `templates/remuneration_placeholder.html`

**Untracked file:**
- `fix_course_code_unique_constraint.sql`

## Recommendation

Production environment এ **Option 1 (Stash)** recommended কারণ:
1. Local changes backup থাকে
2. GitHub এর latest version পাবেন
3. পরে যদি local changes প্রয়োজন হয়, stash থেকে apply করতে পারবেন

## After Resolving Conflict

1. ✅ Migration run করুন: `flask db upgrade`
2. ✅ Application restart করুন: `touch passenger_wsgi.py`
3. ✅ Test করুন: `https://kulawams.xyz/admin/active-semester`

## Check Stashed Changes Later

যদি stashed changes check করতে চান:

```bash
cd /home/gronthon/kulawams.xyz
git stash list
git stash show -p stash@{0}  # Latest stash দেখতে
git stash pop  # Apply করতে
```

