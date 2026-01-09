# Active Semester Filtering - Fix Instructions

## Problem

Filtering কাজ করছে না - সব sessions দেখাচ্ছে, active semester-এর sessions-ই শুধু দেখানো উচিত ছিল।

## Root Cause Analysis

সম্ভাব্য কারণ:
1. সার্ভারে `utils/semester_utils.py` file আপডেট হয়নি
2. Filtering function import হচ্ছে না (ImportError)
3. User admin হিসেবে detect হচ্ছে (filtering bypass)
4. SQL query ঠিকমতো generate হচ্ছে না

## Solution

### Step 1: সার্ভারে File Upload করুন

**File**: `utils/semester_utils.py`
**Server Path**: `/home/gronthon/kulawams.xyz/utils/semester_utils.py`

### Step 2: Verify File on Server

```bash
cd /home/gronthon/kulawams.xyz
grep -n "Require exact academic_session match" utils/semester_utils.py
```

**Expected**: Line 146-147 এ এই text দেখা যাওয়া উচিত

### Step 3: Test Import

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from utils.semester_utils import filter_by_active_semester; print('✅ Import OK')"
```

### Step 4: Check Active Semester in Database

phpMyAdmin এ:

```sql
SELECT * FROM active_semester_config WHERE is_active = 1;
```

**Expected**: 
- academic_session: 2024-25
- year: Fourth
- term: First
- batch: 2022
- is_active: 1

### Step 5: Check if User is Admin

```sql
SELECT id, username, full_name, role 
FROM user 
WHERE username = 'yamin' OR full_name LIKE '%Yamin%';
```

**Check**: `role` field-এ `admin` আছে কিনা। যদি থাকে, তাহলে filtering apply হবে না (by design)।

### Step 6: Restart Application

```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
# Wait 10-15 seconds
```

### Step 7: Check Logs

```bash
cd /home/gronthon/kulawams.xyz
tail -100 tmp/error.log | grep -i "active semester\|filter"
```

**Look for**:
- "Active semesters for filtering: ..."
- "Applied active semester filter with ... condition(s)"
- "Applied active semester filtering for teacher ..."

### Step 8: Test Again

1. yamin account দিয়ে login করুন (admin না হলে)
2. Class Management visit করুন
3. শুধুমাত্র active semester-এর sessions দেখতে হবে

## If Still Not Working

### Check 1: Verify Filter is Being Called

Route-এ check করুন:
```python
if filter_by_active_semester and not is_admin(current_user):
    # This should execute
```

### Check 2: Verify Active Semester Data

```sql
-- Check active semester
SELECT * FROM active_semester_config WHERE is_active = 1;

-- Check session data
SELECT id, course_name, academic_session, year, term 
FROM class_session 
WHERE teacher_id = (SELECT id FROM teacher WHERE name = 'Md. Yamin Rahman')
AND archived = 0
ORDER BY created_at DESC;
```

### Check 3: Manual Test

```python
from utils.semester_utils import get_active_semesters, filter_by_active_semester
from blueprints.class_management.models import Session

# Get active semesters
active = get_active_semesters()
print("Active semesters:", [(s.academic_session, s.year, s.term, s.batch) for s in active])

# Test filter
query = Session.query.filter_by(archived=False)
filtered = filter_by_active_semester(query, Session, batch=None, admin_override=False)
sessions = filtered.all()
print("Filtered sessions:", [(s.course_name, s.academic_session, s.year, s.term) for s in sessions])
```

## Expected SQL Query

With active semester: 2024-25, Fourth, First, 2022

The filter should generate SQL like:
```sql
WHERE (
    academic_session = '2024-25' 
    AND LOWER(TRIM(CAST(year AS CHAR))) IN ('fourth', '4', '4th')
    AND LOWER(TRIM(CAST(term AS CHAR))) IN ('first', '1', '1st')
)
```

## Key Changes Made

1. **Removed NULL academic_session allowance**: আগে NULL academic_session সব active semester-এর সাথে match হত, এখন exact match required
2. **Improved year/term matching**: Format variations (First/1st/1) সব handle করে
3. **Added logging**: Debugging-এর জন্য logs যোগ করা হয়েছে

## Files Modified

1. `utils/semester_utils.py` - Core filtering logic fixed
2. `blueprints/class_management/routes.py` - Added error handling and logging

