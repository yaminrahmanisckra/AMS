# Active Semester Filtering - Test & Debug Guide

## Current Issue

User activated semester:
- Academic Session: 2024-25
- Year: Fourth
- Term: First  
- Batch: 2022

But still seeing:
- Jurisprudence: 2025-26, First Year, First Term, Batch: (empty)

This should be filtered out but it's showing.

## Debugging Steps

### 1. Check if Filter is Being Applied

On server, check logs after visiting Class Management:

```bash
cd /home/gronthon/kulawams.xyz
tail -50 tmp/error.log | grep -i "active semester\|filter"
```

Look for:
- "Active semesters for filtering: ..."
- "Applied active semester filter with ... condition(s)"
- "Applied active semester filtering for teacher ..."

### 2. Check Active Semester in Database

```sql
SELECT * FROM active_semester_config WHERE is_active = 1;
```

Should show:
- academic_session: 2024-25
- year: Fourth
- term: First
- batch: 2022
- is_active: 1

### 3. Check Session Data

```sql
SELECT id, course_name, academic_session, year, term, batch 
FROM class_session 
WHERE teacher_id = (SELECT id FROM teacher WHERE name = 'Md. Yamin Rahman')
AND archived = 0;
```

Check if Jurisprudence session has:
- academic_session: 2025-26 (should NOT match 2024-25)
- year: First (should NOT match Fourth)
- term: First (matches, but others don't)

### 4. Test Filter Function Directly

```python
from utils.semester_utils import get_active_semesters, filter_by_active_semester
from blueprints.class_management.models import Session

# Get active semesters
active = get_active_semesters()
print(f"Active semesters: {[(s.academic_session, s.year, s.term, s.batch) for s in active]}")

# Test filter
query = Session.query.filter_by(archived=False)
filtered = filter_by_active_semester(query, Session, batch=None, admin_override=False)
sessions = filtered.all()
print(f"Filtered sessions: {[(s.course_name, s.academic_session, s.year, s.term) for s in sessions]}")
```

## Expected Behavior

With active semester: 2024-25, Fourth, First, 2022

Should show:
- Sessions with academic_session="2024-25" AND year="Fourth" AND term="First"
- Batch filtering only if Session model has batch field

Should NOT show:
- Jurisprudence (2025-26, First, First) - academic_session mismatch
- Any session with different academic_session, year, or term

## Possible Issues

1. **Filter not being applied**: Check if `filter_by_active_semester` is None (ImportError)
2. **User is admin**: Check if `is_admin(current_user)` returns True
3. **SQL query issue**: The filter might not be generating correct SQL
4. **Data mismatch**: Session data might not match what we expect

## Fix Verification

After uploading fixed `utils/semester_utils.py`:

1. Restart application: `touch passenger_wsgi.py`
2. Visit Class Management as teacher (not admin)
3. Check logs for filtering messages
4. Verify only active semester sessions show

