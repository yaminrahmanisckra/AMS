# Download models.py from GitHub - Fix Missing ActiveSemesterConfig

## সমস্যা

Server এ `blueprints/course_management/models.py` file এ `ActiveSemesterConfig` model নেই।

## সমাধান: GitHub থেকে Download করুন

### Option 1: Download from GitHub (Recommended)

```bash
cd /home/gronthon/kulawams.xyz

# Backup current file
cp blueprints/course_management/models.py blueprints/course_management/models.py.backup_$(date +%Y%m%d_%H%M%S)

# Download from GitHub main branch
curl -o blueprints/course_management/models.py https://raw.githubusercontent.com/yaminrahmanisckra/AMS/main/blueprints/course_management/models.py

# Verify model exists
grep -n "class ActiveSemesterConfig" blueprints/course_management/models.py

# Should show line number (around 320)
```

### Option 2: If GitHub Download Doesn't Work

cPanel File Manager দিয়ে manually add করুন:

1. cPanel → File Manager
2. Navigate: `/home/gronthon/kulawams.xyz/blueprints/course_management/`
3. `models.py` file open করুন (Edit)
4. File এর শেষে যান (around line 318, `SessionArchive` class এর পরে)
5. এই code add করুন:

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

6. Save করুন

### Step 3: Verify and Test

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Check model exists
grep -n "class ActiveSemesterConfig" blueprints/course_management/models.py
# Should show: 320:class ActiveSemesterConfig(db.Model):

# Test import
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig found')"

# Test semester_utils
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')"
```

### Step 4: Complete Deployment

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Migration run করুন
flask db upgrade

# Restart app
touch passenger_wsgi.py
```

## All-in-One Command

```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
cd /home/gronthon/kulawams.xyz && \
cp blueprints/course_management/models.py blueprints/course_management/models.py.backup_$(date +%Y%m%d_%H%M%S) && \
curl -o blueprints/course_management/models.py https://raw.githubusercontent.com/yaminrahmanisckra/AMS/main/blueprints/course_management/models.py && \
grep -n "class ActiveSemesterConfig" blueprints/course_management/models.py && \
python -c "from blueprints.course_management.models import ActiveSemesterConfig; print('✅ ActiveSemesterConfig found')" && \
python -c "from utils.semester_utils import get_active_semesters; print('✅ semester_utils OK')" && \
flask db upgrade && \
touch passenger_wsgi.py && \
echo "✅ All fixed and deployed!"
```

