# Fix Indentation Error on Server

## Problem
The file shows correct indentation when viewing, but Python/Passenger still reports IndentationError. This is often caused by:
1. **Mixed tabs and spaces**
2. **Invisible characters**
3. **Wrong indentation width**

## Quick Fix on Server

Run this on the server to check and fix:

```bash
cd /home/gronthon/kulawams.xyz/blueprints/routine_management

# 1. Check for tabs (should show 0 tabs)
sed -n '193,195p' routes.py | grep -c $'\t' || echo "No tabs found (good)"

# 2. Check exact indentation
sed -n '193,195p' routes.py | cat -A
# Look for ^I (tabs) or wrong number of spaces

# 3. Fix if needed - replace tabs with spaces around line 193
# Backup first
cp routes.py routes.py.backup.$(date +%Y%m%d_%H%M%S)

# Fix tabs to spaces (if tabs found)
sed -i '193,200s/\t/    /g' routes.py

# Verify fix
python -m py_compile routes.py
# Should show no errors
```

## Alternative: Re-upload File

If fixing on server doesn't work, upload the fixed file from local repository:

1. **Local file is correct** (we verified)
2. **Upload via cPanel File Manager**:
   - Navigate to: `/home/gronthon/kulawams.xyz/blueprints/routine_management/`
   - Upload `routes.py`
   - **Replace** existing
   - Set permissions: `644`

3. **Verify after upload**:
   ```bash
   cd /home/gronthon/kulawams.xyz
   python -m py_compile blueprints/routine_management/routes.py
   python -c "from app import create_app; app = create_app(); print('✅ OK')"
   ```

4. **Restart**:
   ```bash
   rm -f startup_error.log passenger_wsgi.log
   touch tmp/restart.txt
   touch passenger_wsgi.py
   sleep 20
   cat startup_error.log 2>/dev/null
   ```

## Check for Hidden Characters

```bash
# Show all characters including tabs/spaces
sed -n '193,195p' routes.py | cat -A

# Should see:
# ^I = tab (BAD - replace with spaces)
# Spaces = spaces (GOOD)
```

## If Still Not Working

Check if there are other syntax errors:
```bash
python -m py_compile blueprints/routine_management/routes.py 2>&1
```

This will show the exact line and character position of the error.
