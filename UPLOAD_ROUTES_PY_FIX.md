# Upload Fixed routes.py to Fix IndentationError

## Problem
The server still shows IndentationError at line 194, which means the fixed `routes.py` file hasn't been uploaded yet or the old version is cached.

## Solution
Upload the fixed `blueprints/routine_management/routes.py` file to the server.

## Upload Instructions

### Step 1: Verify Local File is Correct

Local file should have correct indentation at line 193-194:
```python
193|    try:
194|        room = Room.query.get_or_404(id)
```

### Step 2: Upload to Server

**Via cPanel File Manager:**
1. cPanel → File Manager
2. Navigate to: `/home/gronthon/kulawams.xyz/blueprints/routine_management/`
3. Upload `routes.py` from local repository
4. **Replace** existing file
5. **Set permissions: `644`**

### Step 3: Verify Upload on Server

SSH-এ run করুন:
```bash
cd /home/gronthon/kulawams.xyz

# Check syntax
python -m py_compile blueprints/routine_management/routes.py
# Should show NO errors

# Check specific lines
sed -n '193,194p' blueprints/routine_management/routes.py
# Should show:
#     try:
#         room = Room.query.get_or_404(id)
```

### Step 4: Restart Application

```bash
cd /home/gronthon/kulawams.xyz

# Clear any caches
rm -f startup_error.log 2>/dev/null
rm -f passenger_wsgi.log 2>/dev/null

# Restart
touch tmp/restart.txt
touch passenger_wsgi.py
sleep 20
```

### Step 5: Verify Error is Fixed

```bash
# Check startup error (should be empty or no IndentationError)
cat startup_error.log 2>/dev/null | head -20

# Test app load
python -c "from app import create_app; app = create_app(); print('✅ OK')"
```

## File Details

**Local File:** `blueprints/routine_management/routes.py`  
**Server Path:** `/home/gronthon/kulawams.xyz/blueprints/routine_management/routes.py`  
**Permissions:** `644`  
**Lines to Check:** 193-194 (should have proper indentation)

## Quick Upload Command (If you have SCP access)

```bash
# From local machine
scp blueprints/routine_management/routes.py user@server:/home/gronthon/kulawams.xyz/blueprints/routine_management/routes.py
```

## After Upload

1. Verify file is uploaded correctly
2. Restart application
3. Check startup_error.log (should be empty)
4. Test site in browser
