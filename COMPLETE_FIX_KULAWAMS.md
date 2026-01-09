# Complete Fix for kulawams.xyz 404 Error

## Step-by-Step Complete Solution

### Step 1: Upload Fixed .htaccess File

File: `.htaccess.kulawams.fixed` (updated with complete Passenger configuration)

1. **cPanel → File Manager**
2. Navigate to `/home/gronthon/kulawams.xyz/`
3. **Delete existing `.htaccess`** (backup first if needed)
4. Upload `.htaccess.kulawams.fixed`
5. **Rename to `.htaccess`** (exactly - with dot at beginning)
6. **Set permissions: `644`**

### Step 2: Verify passenger_wsgi.py

**Check via SSH:**
```bash
cd /home/gronthon/kulawams.xyz
cat passenger_wsgi.py
```

**Should contain:**
```python
#!/usr/bin/env python3
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

os.environ['CPANEL'] = '1'
os.environ['FLASK_ENV'] = 'production'

from app import create_app

application = create_app()

if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=5000)
```

**Permissions:** `644` or `755`

### Step 3: Verify Python Path

```bash
# Check if Python path exists
ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python

# Should show: -rwxr-xr-x ... python

# If doesn't exist, check actual path:
ls -la /home/gronthon/virtualenv/kulawams.xyz/*/bin/python
```

### Step 4: Test Application Loads

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test import
python -c "from app import create_app; app = create_app(); print('✅ App OK')"

# If error, check what's wrong:
python -c "import sys; print(sys.path)"
python passenger_wsgi.py
# (Ctrl+C to stop)
```

### Step 5: Check Error Logs

**Via SSH:**
```bash
cd /home/gronthon/kulawams.xyz

# Check application logs
tail -100 logs/app_errors.log 2>/dev/null || echo "No app_errors.log"
tail -100 logs/detailed_errors.log 2>/dev/null || echo "No detailed_errors.log"

# Check cPanel error log
tail -100 ~/logs/kulawams.xyz.error.log 2>/dev/null || echo "Check cPanel → Errors"
```

**Via cPanel:**
- cPanel → Errors → Error Log
- Look for Passenger-related errors
- Look for Python import errors
- Look for file not found errors

### Step 6: Verify Addon Domain Setup

1. **cPanel → Domains → Addon Domains**
2. Find `kulawams.xyz`
3. **Document Root** should be: `/home/gronthon/kulawams.xyz`
4. If wrong, click **Edit** and fix it

### Step 7: Restart Application (Multiple Methods)

Try all these:

```bash
cd /home/gronthon/kulawams.xyz

# Method 1
touch tmp/restart.txt

# Method 2
touch passenger_wsgi.py

# Method 3
touch app.py

# Method 4 - Kill Passenger process (if exists)
pkill -f passenger || echo "No passenger process"

# Method 5 - Via cPanel
# cPanel → Applications → Python App → Restart
```

### Step 8: Check File Permissions

```bash
cd /home/gronthon/kulawams.xyz

# Set correct permissions
find . -type f -name "*.py" -exec chmod 644 {} \;
chmod 644 .htaccess
chmod 644 passenger_wsgi.py
chmod 644 app.py
chmod 755 .
```

### Step 9: Alternative .htaccess (If Still Not Working)

If Passenger still doesn't work, try this minimal version:

```apache
# Minimal Passenger Configuration
PassengerEnabled On
PassengerAppRoot "/home/gronthon/kulawams.xyz"
PassengerBaseURI "/"
PassengerAppType wsgi
PassengerStartupFile passenger_wsgi.py
PassengerPython "/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python"

RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ passenger_wsgi.py/$1 [L]
```

### Step 10: Check if Passenger Module is Enabled

```bash
# Check Apache modules (if access available)
# This might require root access, so contact hosting if needed

# Check if Passenger is installed
which passenger || echo "Passenger not in PATH"

# Check Passenger version
passenger --version 2>/dev/null || echo "Cannot check version"
```

## Common Error Messages and Solutions

### Error: "Passenger Python not found"
**Solution:**
```bash
# Verify path in .htaccess matches actual path
ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python

# If different version, update .htaccess:
# PassengerPython "/home/gronthon/virtualenv/kulawams.xyz/ACTUAL_VERSION/bin/python"
```

### Error: "Application failed to start"
**Solution:**
```bash
# Test app manually
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python passenger_wsgi.py
# Fix any import errors shown
```

### Error: "ModuleNotFoundError"
**Solution:**
```bash
# Install missing dependencies
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
pip install -r requirements.txt
```

### Error: "Permission denied"
**Solution:**
```bash
cd /home/gronthon/kulawams.xyz
chmod 644 .htaccess passenger_wsgi.py app.py
chmod 755 .
```

### Error: 404 on all routes
**Solution:**
- Verify rewrite rules in .htaccess
- Check PassengerAppRoot path is correct
- Verify passenger_wsgi.py exists and is readable

## Diagnostic Script

Run this complete diagnostic:

```bash
#!/bin/bash
cd /home/gronthon/kulawams.xyz

echo "=== 1. Checking Files ==="
ls -la .htaccess passenger_wsgi.py app.py 2>&1

echo -e "\n=== 2. Checking Python ==="
ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python 2>&1

echo -e "\n=== 3. Testing App Import ==="
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from app import create_app; app = create_app(); print('✅ App loads OK')" 2>&1

echo -e "\n=== 4. Checking .htaccess Content ==="
grep -i passenger .htaccess 2>&1 | head -10

echo -e "\n=== 5. Checking Error Logs ==="
tail -20 logs/app_errors.log 2>/dev/null || echo "No app_errors.log"
tail -20 ~/logs/kulawams.xyz.error.log 2>/dev/null || echo "Check cPanel error log"

echo -e "\n=== 6. File Permissions ==="
stat -c "%a %n" .htaccess passenger_wsgi.py app.py 2>&1

echo -e "\n=== Done ==="
```

## Contact Hosting Provider

If nothing works, contact hosting provider with:

1. **Domain:** kulawams.xyz
2. **Error:** 404 Not Found
3. **Application Type:** Python/Flask with Passenger
4. **Document Root:** /home/gronthon/kulawams.xyz
5. **Python Path:** /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python
6. **Error Logs:** (attach recent logs)
7. **What you've tried:** (list of troubleshooting steps)

Ask them to:
- Verify Passenger is enabled for your account
- Check Passenger configuration
- Verify Python application setup
- Check for any account-level restrictions

## Final Checklist

- [ ] Updated .htaccess uploaded and renamed correctly
- [ ] File permissions set (644 for files, 755 for directories)
- [ ] passenger_wsgi.py exists and is correct
- [ ] Python path in .htaccess matches actual path
- [ ] Application loads without errors when tested manually
- [ ] Addon domain Document Root is correct
- [ ] Application restarted (multiple methods tried)
- [ ] Error logs checked
- [ ] No conflicting .htaccess files
