# Fix Import Error - ActiveSemesterConfig

## সমস্যা

Import error হচ্ছে:
```
ImportError: cannot import name 'ActiveSemesterConfig' from 'blueprints.course_management.models'
```

**কারণ:** Server এ `blueprints/course_management/models.py` file এ `ActiveSemesterConfig` model নেই। Conflicts resolve করার সময় local version ব্যবহার করা হয়েছে।

## সমাধান

### Step 1: Conflicts Resolve করুন (GitHub Version ব্যবহার করুন)

Terminal এ এই commands run করুন:

```bash
cd /home/gronthon/kulawams.xyz

# Conflicts resolve করুন - GitHub version ব্যবহার করুন
git checkout --theirs app.py
git checkout --theirs blueprints/course_management/models.py
git checkout --theirs blueprints/result_management/routes.py
git checkout --theirs passenger_wsgi.py

# Conflicts mark করুন as resolved
git add app.py
git add blueprints/course_management/models.py
git add blueprints/result_management/routes.py
git add passenger_wsgi.py

# Stash clear করুন (যদি থাকে)
git stash drop 2>/dev/null || true

# Check conflicts
git status
```

### Step 2: Verify File Contains ActiveSemesterConfig

```bash
cd /home/gronthon/kulawams.xyz

# Check if ActiveSemesterConfig exists in models.py
grep -n "class ActiveSemesterConfig" blueprints/course_management/models.py

# Should show line number (around line 320)
# If not found, manually add it (see below)
```

### Step 3: If Model Still Missing, Manually Add

যদি `git checkout --theirs` কাজ না করে, তাহলে manually add করুন:

```bash
cd /home/gronthon/kulawams.xyz

# Backup current file
cp blueprints/course_management/models.py blueprints/course_management/models.py.backup

# Download from GitHub directly
cd blueprints/course_management/
curl -O https://raw.githubusercontent.com/yaminrahmanisckra/AMS/main/blueprints/course_management/models.py

# Or manually edit and add the model (see below)
```

### Step 4: Test Import

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test import
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig found')"

# Test semester_utils import
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')"
```

### Step 5: Run Migration

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
flask db upgrade
```

### Step 6: Restart Application

```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
```

## Manual Fix (If Git Doesn't Work)

যদি git commands কাজ না করে, তাহলে manually add করুন:

### Check Current File

```bash
cd /home/gronthon/kulawams.xyz
tail -50 blueprints/course_management/models.py
```

### Add ActiveSemesterConfig Model

File এ `SessionArchive` class এর পরে (around line 320) এই code add করুন:

```python
class ActiveSemesterConfig(db.Model):
    """Model to manage active semester configuration"""
    __tablename__ = 'active_semester_config'
    
    id = db.Column(db.Integer, primary_key=True)
    academic_session = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(50), nullable=False)
    term = db.Column(db.String(50), nullable=False)
    batch = db.Column(db.String(50), nullable=True)  # NULL = All batches, or specific batch
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    activated_by = db.Column(db.String(100), nullable=True)  # User who activated
    activated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    
    __table_args__ = (
        db.Index('idx_active_semester', 'academic_session', 'year', 'term', 'batch', 'is_active'),
    )
    
    def __repr__(self):
        batch_str = f" - Batch: {self.batch}" if self.batch else ""
        return f'<ActiveSemesterConfig {self.academic_session} - {self.year} - {self.term}{batch_str}>'
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'academic_session': self.academic_session,
            'year': self.year,
            'term': self.term,
            'batch': self.batch,
            'is_active': self.is_active,
            'activated_by': self.activated_by,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None
        }
```

### Also Update app.py Import

Ensure `app.py` file এ `ActiveSemesterConfig` import আছে:

```python
from blueprints.course_management.models import Course, DutyAssignment, Curriculum, CurriculumYearTerm, StudentCourseRegistration, SessionArchive, ActiveSemesterConfig
```

## All-in-One Fix Command

```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
cd /home/gronthon/kulawams.xyz && \
git checkout --theirs blueprints/course_management/models.py app.py blueprints/result_management/routes.py passenger_wsgi.py && \
git add blueprints/course_management/models.py app.py blueprints/result_management/routes.py passenger_wsgi.py && \
git stash drop 2>/dev/null || true && \
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig found')" && \
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')" && \
flask db upgrade && \
touch passenger_wsgi.py && \
echo "✅ All fixed!"
```

## Verification After Fix

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test 1: Check model exists
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig OK')"

# Test 2: Check semester_utils imports
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')"

# Test 3: Check app.py imports
python -c "from app import app; print('✅ App imports OK')"
```

## Troubleshooting

### If git checkout doesn't work:

```bash
# Download from GitHub
cd /home/gronthon/kulawams.xyz
curl -o blueprints/course_management/models.py https://raw.githubusercontent.com/yaminrahmanisckra/AMS/main/blueprints/course_management/models.py

# Check if downloaded correctly
grep -n "ActiveSemesterConfig" blueprints/course_management/models.py
```

### If file still doesn't have the model:

Check the end of the file and manually add the `ActiveSemesterConfig` class after `SessionArchive` class.

