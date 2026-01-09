# Troubleshooting kulawams.xyz 404 Error

## Problem
Site is still showing 404 error after uploading .htaccess file.

## Solutions

### 1. Verify .htaccess File is Uploaded Correctly

**Check via SSH:**
```bash
cd /home/gronthon/kulawams.xyz
ls -la .htaccess
cat .htaccess | head -10
```

**Verify:**
- File exists
- File name is exactly `.htaccess` (with dot at the beginning)
- File permissions are `644`
- Contains Passenger configuration

### 2. Updated .htaccess File

The `.htaccess.kulawams` file has been updated with proper rewrite rules. 

**Key Fix:** Added catch-all rewrite rule to route ALL requests to Flask app, not just `/static/` requests.

### 3. Verify Passenger Configuration

**Check via SSH:**
```bash
cd /home/gronthon/kulawams.xyz

# Check Passenger Python path exists
ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python

# Check passenger_wsgi.py exists
ls -la passenger_wsgi.py

# Test Python import
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
python -c "from app import create_app; print('OK')"
```

### 4. Check Application Logs

**Error Logs:**
```bash
# cPanel → Errors → Error Log
# বা SSH-এ:
tail -50 /home/gronthon/kulawams.xyz/logs/app_errors.log
tail -50 /home/gronthon/kulawams.xyz/logs/detailed_errors.log
```

**Passenger Logs:**
```bash
# cPanel → Errors → Error Log
# Look for Passenger-related errors
```

### 5. Verify Addon Domain Configuration

1. **cPanel → Domains → Addon Domains**
2. Check `kulawams.xyz`:
   - Document Root: `/home/gronthon/kulawams.xyz`
   - Subdomain: Should not conflict
   - DNS: Pointing correctly

### 6. Restart Application Multiple Ways

Try all these methods:

```bash
cd /home/gronthon/kulawams.xyz

# Method 1: Touch restart file
touch tmp/restart.txt

# Method 2: Touch passenger_wsgi.py
touch passenger_wsgi.py

# Method 3: Touch app.py
touch app.py

# Method 4: Via cPanel
# cPanel → Applications → Python App → kulawams.xyz → Restart
```

### 7. Check File Permissions

```bash
cd /home/gronthon/kulawams.xyz

# Set correct permissions
chmod 644 .htaccess
chmod 644 passenger_wsgi.py
chmod 644 app.py
chmod 755 .  # Directory should be executable
```

### 8. Test Passenger Directly

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test if app loads
python passenger_wsgi.py
# Should not show errors (Ctrl+C to stop)

# Test app import
python -c "from app import create_app; app = create_app(); print('App loaded successfully')"
```

### 9. Check .htaccess Syntax

```bash
# Test Apache configuration (if apachectl available)
apachectl -t

# বা check for syntax errors manually
# Look for unclosed tags, quotes, etc.
```

### 10. Verify No Conflicting .htaccess

Check if there's a `.htaccess` in parent directory causing conflicts:

```bash
# Check parent directory
ls -la /home/gronthon/.htaccess

# If exists, check if it's interfering
cat /home/gronthon/.htaccess
```

### 11. Check DNS Resolution

```bash
# Verify domain resolves
nslookup kulawams.xyz
ping kulawams.xyz

# Check if domain is pointing to correct IP
dig kulawams.xyz
```

### 12. Contact Hosting Provider

If all above fails, contact hosting provider with:
- Domain: kulawams.xyz
- Error: 404 Not Found
- Document Root: /home/gronthon/kulawams.xyz
- Application Type: Python/Flask with Passenger
- Error logs (if any)

## Common Issues and Fixes

### Issue 1: "Passenger Python not found"
**Fix:** Verify Python path in .htaccess matches actual path

### Issue 2: "Application failed to start"
**Fix:** Check app.py for syntax errors, check logs

### Issue 3: "Module not found"
**Fix:** Ensure virtual environment has all dependencies installed

### Issue 4: "Permission denied"
**Fix:** Check file permissions, ensure web server user can read files

### Issue 5: "Rewrite rule not working"
**Fix:** Ensure mod_rewrite is enabled, rewrite conditions are correct

## Updated .htaccess Content

Make sure your `.htaccess` file has this rewrite section:

```apache
# URL Rewriting - Route all requests to Flask application
<IfModule mod_rewrite.c>
    RewriteEngine On
    
    # Skip rewrite for existing files and directories
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    
    # Route all requests to passenger_wsgi.py (Flask app)
    RewriteRule ^(.*)$ passenger_wsgi.py/$1 [QSA,L]
</IfModule>
```

## Quick Diagnostic Command

Run this to check everything:

```bash
cd /home/gronthon/kulawams.xyz && \
echo "=== Checking Files ===" && \
ls -la .htaccess passenger_wsgi.py app.py && \
echo "=== Checking Python ===" && \
ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python && \
echo "=== Testing App ===" && \
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate && \
python -c "from app import create_app; app = create_app(); print('✅ App loads successfully')" && \
echo "=== Restarting ===" && \
touch tmp/restart.txt && \
echo "✅ Done! Check site now."
```
