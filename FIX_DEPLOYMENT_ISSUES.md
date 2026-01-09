# Fix Deployment Issues - kulawams.xyz

## Current Issues

1. ✅ Git pull successful
2. ⚠️ Merge conflicts in: `app.py`, `blueprints/result_management/routes.py`, `passenger_wsgi.py`
3. ❌ Missing file: `utils/semester_utils.py`

## Solution: Quick Fix Commands

### Step 1: Resolve Merge Conflicts (Use GitHub Version)

```bash
cd /home/gronthon/kulawams.xyz

# Conflicts resolve করুন - GitHub version ব্যবহার করুন (production এ recommended)
git checkout --theirs app.py
git checkout --theirs blueprints/result_management/routes.py
git checkout --theirs passenger_wsgi.py

# Conflicts mark করুন as resolved
git add app.py
git add blueprints/result_management/routes.py
git add passenger_wsgi.py

# Stash clear করুন
git stash drop
```

### Step 2: Create Missing File `utils/semester_utils.py`

```bash
cd /home/gronthon/kulawams.xyz

# utils directory ensure করুন
mkdir -p utils

# Create semester_utils.py file
cat > utils/semester_utils.py << 'EOF'
"""
Utility functions for Active Semester Management
"""
from extensions import db
from sqlalchemy import or_, and_
from blueprints.course_management.models import ActiveSemesterConfig


def get_active_semesters(batch=None):
    """
    Get all active semester configurations.
    
    Args:
        batch: Optional batch to filter by. If None, returns all active semesters.
    
    Returns:
        List of ActiveSemesterConfig objects
    """
    query = ActiveSemesterConfig.query.filter_by(is_active=True)
    
    if batch is not None:
        # Return active semester for specific batch or NULL batch (applies to all)
        query = query.filter(
            (ActiveSemesterConfig.batch == batch) | 
            (ActiveSemesterConfig.batch.is_(None))
        )
    
    return query.order_by(
        ActiveSemesterConfig.academic_session.desc(),
        ActiveSemesterConfig.year.asc(),
        ActiveSemesterConfig.term.asc()
    ).all()


def is_semester_active(academic_session, year, term, batch=None):
    """
    Check if a specific semester is active.
    
    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
    
    Returns:
        Boolean indicating if the semester is active
    """
    query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True
    )
    
    if batch is not None:
        # Check for specific batch or NULL batch (applies to all)
        query = query.filter(
            (ActiveSemesterConfig.batch == batch) | 
            (ActiveSemesterConfig.batch.is_(None))
        )
    else:
        # If batch is None, check if there's an active semester for this session/year/term
        # regardless of batch
        pass
    
    return query.first() is not None


def filter_by_active_semester(query, model, batch=None, admin_override=False):
    """
    Filter a query to only include records from active semesters.
    This is a generic function that works with models that have academic_session, year, term fields.
    
    Args:
        query: SQLAlchemy query object
        model: SQLAlchemy model class
        batch: Optional batch to filter by
        admin_override: If True, returns query without filtering (for admin users)
    
    Returns:
        Filtered query object
    """
    if admin_override:
        return query
    
    active_semesters = get_active_semesters(batch=batch)
    
    if not active_semesters:
        # If no active semester configured, return empty query
        # This prevents showing all data when no semester is marked active
        return query.filter(False)
    
    # Build filter conditions for active semesters
    conditions = []
    for sem in active_semesters:
        condition = and_(
            getattr(model, 'academic_session') == sem.academic_session,
            getattr(model, 'year') == sem.year,
            getattr(model, 'term') == sem.term
        )
        
        # If semester config has a specific batch, filter by batch too
        if sem.batch and hasattr(model, 'batch'):
            condition = and_(condition, getattr(model, 'batch') == sem.batch)
        
        conditions.append(condition)
    
    if conditions:
        # Combine conditions with OR
        return query.filter(or_(*conditions))
    
    return query.filter(False)


def get_active_semester_info(batch=None):
    """
    Get human-readable information about active semesters.
    
    Args:
        batch: Optional batch to filter by
    
    Returns:
        List of dictionaries with semester information
    """
    active_semesters = get_active_semesters(batch=batch)
    return [sem.to_dict() for sem in active_semesters]


def set_active_semester(academic_session, year, term, batch=None, activated_by=None, deactivate_others=True):
    """
    Set a semester as active. Optionally deactivate other semesters.
    
    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
        activated_by: User who activated the semester
        deactivate_others: If True, deactivate all other semesters for the same batch
    
    Returns:
        ActiveSemesterConfig object or None
    """
    from datetime import datetime
    
    # Check if already exists and is active
    existing_query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True
    )
    
    if batch is not None:
        existing_query = existing_query.filter_by(batch=batch)
    else:
        existing_query = existing_query.filter(ActiveSemesterConfig.batch.is_(None))
    
    existing = existing_query.first()
    
    if existing:
        # Already active, just update activated_by and timestamp
        if activated_by:
            existing.activated_by = activated_by
        existing.activated_at = datetime.utcnow()
        db.session.commit()
        return existing
    
    # Deactivate other semesters if requested
    if deactivate_others:
        other_semesters_query = ActiveSemesterConfig.query.filter_by(is_active=True)
        
        if batch is not None:
            # Deactivate other semesters for same batch or NULL batch
            other_semesters_query = other_semesters_query.filter(
                (ActiveSemesterConfig.batch == batch) | 
                (ActiveSemesterConfig.batch.is_(None))
            )
        else:
            # If batch is None, deactivate all other semesters with NULL batch
            other_semesters_query = other_semesters_query.filter(
                ActiveSemesterConfig.batch.is_(None)
            )
        
        for sem in other_semesters_query.all():
            sem.is_active = False
            sem.deactivated_at = datetime.utcnow()
    
    # Create new active semester config
    new_config = ActiveSemesterConfig(
        academic_session=academic_session,
        year=year,
        term=term,
        batch=batch,
        is_active=True,
        activated_by=activated_by
    )
    
    db.session.add(new_config)
    db.session.commit()
    
    return new_config


def deactivate_semester(academic_session, year, term, batch=None):
    """
    Deactivate a specific semester.
    
    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
    
    Returns:
        True if deactivated, False if not found
    """
    from datetime import datetime
    
    query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True
    )
    
    if batch is not None:
        query = query.filter_by(batch=batch)
    else:
        query = query.filter(ActiveSemesterConfig.batch.is_(None))
    
    semester = query.first()
    
    if semester:
        semester.is_active = False
        semester.deactivated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    return False
EOF

# __init__.py ensure করুন
touch utils/__init__.py

# Permissions set করুন
chmod 644 utils/semester_utils.py
chmod 755 utils/
```

### Step 3: Complete Deployment

```bash
cd /home/gronthon/kulawams.xyz

# Migration run করুন
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
flask db upgrade

# Restart app
touch passenger_wsgi.py
```

## All-in-One Fix Command

```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
cd /home/gronthon/kulawams.xyz && \
git checkout --theirs app.py blueprints/result_management/routes.py passenger_wsgi.py && \
git add app.py blueprints/result_management/routes.py passenger_wsgi.py && \
git stash drop && \
mkdir -p utils && \
python3 -c "
from pathlib import Path
content = '''\"\"\"
Utility functions for Active Semester Management
\"\"\"
from extensions import db
from sqlalchemy import or_, and_
from blueprints.course_management.models import ActiveSemesterConfig

def get_active_semesters(batch=None):
    query = ActiveSemesterConfig.query.filter_by(is_active=True)
    if batch is not None:
        query = query.filter((ActiveSemesterConfig.batch == batch) | (ActiveSemesterConfig.batch.is_(None)))
    return query.order_by(ActiveSemesterConfig.academic_session.desc(), ActiveSemesterConfig.year.asc(), ActiveSemesterConfig.term.asc()).all()

def is_semester_active(academic_session, year, term, batch=None):
    query = ActiveSemesterConfig.query.filter_by(academic_session=academic_session, year=year, term=term, is_active=True)
    if batch is not None:
        query = query.filter((ActiveSemesterConfig.batch == batch) | (ActiveSemesterConfig.batch.is_(None)))
    return query.first() is not None

def filter_by_active_semester(query, model, batch=None, admin_override=False):
    if admin_override:
        return query
    active_semesters = get_active_semesters(batch=batch)
    if not active_semesters:
        return query.filter(False)
    conditions = []
    for sem in active_semesters:
        condition = and_(getattr(model, 'academic_session') == sem.academic_session, getattr(model, 'year') == sem.year, getattr(model, 'term') == sem.term)
        if sem.batch and hasattr(model, 'batch'):
            condition = and_(condition, getattr(model, 'batch') == sem.batch)
        conditions.append(condition)
    if conditions:
        return query.filter(or_(*conditions))
    return query.filter(False)

def get_active_semester_info(batch=None):
    active_semesters = get_active_semesters(batch=batch)
    return [sem.to_dict() for sem in active_semesters]

def set_active_semester(academic_session, year, term, batch=None, activated_by=None, deactivate_others=True):
    from datetime import datetime
    existing_query = ActiveSemesterConfig.query.filter_by(academic_session=academic_session, year=year, term=term, is_active=True)
    if batch is not None:
        existing_query = existing_query.filter_by(batch=batch)
    else:
        existing_query = existing_query.filter(ActiveSemesterConfig.batch.is_(None))
    existing = existing_query.first()
    if existing:
        if activated_by:
            existing.activated_by = activated_by
        existing.activated_at = datetime.utcnow()
        db.session.commit()
        return existing
    if deactivate_others:
        other_semesters_query = ActiveSemesterConfig.query.filter_by(is_active=True)
        if batch is not None:
            other_semesters_query = other_semesters_query.filter((ActiveSemesterConfig.batch == batch) | (ActiveSemesterConfig.batch.is_(None)))
        else:
            other_semesters_query = other_semesters_query.filter(ActiveSemesterConfig.batch.is_(None))
        for sem in other_semesters_query.all():
            sem.is_active = False
            sem.deactivated_at = datetime.utcnow()
    new_config = ActiveSemesterConfig(academic_session=academic_session, year=year, term=term, batch=batch, is_active=True, activated_by=activated_by)
    db.session.add(new_config)
    db.session.commit()
    return new_config

def deactivate_semester(academic_session, year, term, batch=None):
    from datetime import datetime
    query = ActiveSemesterConfig.query.filter_by(academic_session=academic_session, year=year, term=term, is_active=True)
    if batch is not None:
        query = query.filter_by(batch=batch)
    else:
        query = query.filter(ActiveSemesterConfig.batch.is_(None))
    semester = query.first()
    if semester:
        semester.is_active = False
        semester.deactivated_at = datetime.utcnow()
        db.session.commit()
        return True
    return False
'''
Path('utils/semester_utils.py').write_text(content)
Path('utils/__init__.py').touch()
" && \
chmod 644 utils/semester_utils.py && \
chmod 755 utils/ && \
flask db upgrade && \
touch passenger_wsgi.py && \
echo "✅ All fixed and deployed!"
```

## Alternative: Manual File Upload

যদি command না কাজ করে, তাহলে:

1. `utils/semester_utils.py` file টি GitHub থেকে download করুন
2. cPanel File Manager দিয়ে `/home/gronthon/kulawams.xyz/utils/` folder এ upload করুন
3. Permissions set করুন: `chmod 644 utils/semester_utils.py`

## After Fix

1. ✅ Verify file exists: `ls -la utils/semester_utils.py`
2. ✅ Test import: `python -c "from utils.semester_utils import get_active_semesters; print('OK')"`
3. ✅ Check admin page: Visit `/admin/active-semester`
4. ✅ Run migration: `flask db upgrade`

