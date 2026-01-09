# cPanel Upload Guide - Fix for exam-evaluation Error

## Problem Fixed
- **Error**: `UnboundLocalError: cannot access local variable 'is_admin' where it is not associated with a value`
- **Location**: `/exam-evaluation` route
- **Fix**: Removed redundant local import of `is_admin` (it's already imported globally)

## Files to Upload

### 1. app.py
- **Path**: `/Users/isckra/Documents/App Projects/Academic Management System/app.py`
- **Server Path**: `/home/gronthon/kulawams.xyz/app.py` (for kulawams.xyz)
- **Server Path**: `/home/gronthon/aqpub.com/app.py` (for aqpub.com, if same codebase)

## Upload Instructions

### Method 1: cPanel File Manager (Recommended)

1. **Login to cPanel**
   - Go to your cPanel login page
   - Enter your credentials

2. **Open File Manager**
   - Find "Files" section
   - Click on "File Manager"

3. **Navigate to Domain Directory**
   - For `kulawams.xyz`: Navigate to `/home/gronthon/kulawams.xyz/`
   - For `aqpub.com`: Navigate to `/home/gronthon/aqpub.com/`

4. **Upload app.py**
   - Select `app.py` in the directory (if it exists, you'll need to replace it)
   - Click "Upload" button at the top
   - In the upload dialog:
     - Click "Select File"
     - Choose the fixed `app.py` from your local machine
     - Wait for upload to complete
   
5. **Replace Existing File** (if prompted)
   - If `app.py` already exists, you'll be asked to replace it
   - Click "Replace" or "Overwrite" to confirm

6. **Set Permissions** (if needed)
   - Right-click on `app.py`
   - Select "Change Permissions"
   - Ensure it has read permissions (644 or 644 is usually fine)

### Method 2: Terminal/SSH (If Available)

```bash
# Navigate to your local project directory
cd "/Users/isckra/Documents/App Projects/Academic Management System"

# Upload using SCP (replace with your actual server details)
scp app.py gronthon@your-server-ip:/home/gronthon/kulawams.xyz/app.py

# Or use rsync for better reliability
rsync -avz app.py gronthon@your-server-ip:/home/gronthon/kulawams.xyz/app.py
```

### Method 3: FTP Client

1. **Connect via FTP**
   - Use an FTP client (FileZilla, Cyberduck, etc.)
   - Host: Your server hostname/IP
   - Username: `gronthon`
   - Password: Your FTP/cPanel password
   - Port: 21 (or 22 for SFTP)

2. **Navigate and Upload**
   - Navigate to `/home/gronthon/kulawams.xyz/` (or aqpub.com)
   - Upload `app.py`
   - Replace existing file if prompted

## After Upload - Restart Application

### Step 1: Restart via Terminal (Recommended)

```bash
# SSH into your server
ssh gronthon@your-server-ip

# Navigate to domain directory
cd /home/gronthon/kulawams.xyz

# Restart Passenger application
touch passenger_wsgi.py

# Wait 15-20 seconds for restart
sleep 20

# Test the fix
curl -I https://kulawams.xyz/exam-evaluation 2>&1 | grep -E "HTTP/"
```

### Step 2: Restart via cPanel (Alternative)

1. **Go to Python App Manager**
   - cPanel → Applications → Python App Manager

2. **Find Your App**
   - Look for `kulawams.xyz` (or `aqpub.com`)
   - Click the "Restart" button (circular arrow icon)

3. **Wait 15-20 seconds** for application to restart

## Verify the Fix

### 1. Check for Errors

```bash
# Check startup errors
cat /home/gronthon/kulawams.xyz/startup_error.log 2>/dev/null || echo "✅ No startup errors"

# Check application logs
tail -20 /home/gronthon/kulawams.xyz/passenger_wsgi.log | grep -i "error\|exception" | tail -5
```

### 2. Test the Route

**Via Browser:**
- Visit: `https://kulawams.xyz/exam-evaluation`
- Should load without "Error 500"
- Should show the exam evaluation page

**Via Terminal:**
```bash
curl -I https://kulawams.xyz/exam-evaluation 2>&1 | grep -E "HTTP/"
# Should return: HTTP/2 200 or HTTP/2 302 (not 500)
```

### 3. Test Full Page Load

```bash
curl -L https://kulawams.xyz/exam-evaluation 2>&1 | head -30
# Should show HTML content, not error message
```

## Troubleshooting

### If Error Persists

1. **Check File Was Uploaded Correctly**
   ```bash
   # Verify file exists and is correct size
   ls -lh /home/gronthon/kulawams.xyz/app.py
   
   # Check if fix is present (should NOT find the redundant import)
   grep -n "from role_utils import is_admin" /home/gronthon/kulawams.xyz/app.py | grep -v "^13:"
   # Should return nothing (only line 13 should have it at the top)
   ```

2. **Clear Python Cache**
   ```bash
   cd /home/gronthon/kulawams.xyz
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -type d -exec rm -r {} + 2>/dev/null
   touch passenger_wsgi.py
   sleep 20
   ```

3. **Check Application Logs**
   ```bash
   tail -50 /home/gronthon/kulawams.xyz/passenger_wsgi.log | tail -20
   ```

4. **Verify app.py Syntax**
   ```bash
   cd /home/gronthon/kulawams.xyz
   source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
   python3 -m py_compile app.py
   deactivate
   # Should return nothing if syntax is correct
   ```

## Quick Summary

1. ✅ Upload `app.py` to `/home/gronthon/kulawams.xyz/`
2. ✅ Replace existing file if prompted
3. ✅ Restart application: `touch passenger_wsgi.py` or via cPanel
4. ✅ Wait 15-20 seconds
5. ✅ Test: Visit `https://kulawams.xyz/exam-evaluation`

## Notes

- The fix removes a redundant `from role_utils import is_admin` at line 918
- `is_admin` is already imported globally at line 13-22, so the local import was causing a scope conflict
- The error occurred because `is_admin` was being used at line 874 before the local import at line 918, creating an `UnboundLocalError`

---

**Last Updated**: 2026-01-09
**Fixed Issue**: UnboundLocalError in exam-evaluation route
