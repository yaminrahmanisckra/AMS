# Fix kulawams.xyz 404 Error - .htaccess Configuration

## সমস্যা
`kulawams.xyz` addon domain 404 error দেখাচ্ছে `.htaccess` file change করার পর।

## সমাধান

### Step 1: `.htaccess` file তৈরি করুন `kulawams.xyz` directory-তে

**File Path**: `/home/gronthon/kulawams.xyz/.htaccess`

**Content**:
```apache
# cPanel Python/Flask Application Configuration for kulawams.xyz
# Passenger WSGI Configuration

# Enable Passenger for Python application
PassengerEnabled On
PassengerAppRoot /home/gronthon/kulawams.xyz
PassengerBaseURI /
PassengerAppType wsgi
PassengerStartupFile passenger_wsgi.py
PassengerPython /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python

# Set environment variables
SetEnv CPANEL 1
SetEnv FLASK_ENV production

# Increase memory and execution time
php_value memory_limit 1024M
php_value max_execution_time 600

# URL Rewriting - All requests to Flask app
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ passenger_wsgi.py/$1 [QSA,L]

# Security headers
<IfModule mod_headers.c>
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options SAMEORIGIN
    Header always set X-XSS-Protection "1; mode=block"
</IfModule>

# Cache static files
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/jpg "access plus 1 year"
    ExpiresByType image/jpeg "access plus 1 year"
    ExpiresByType image/gif "access plus 1 year"
    ExpiresByType image/ico "access plus 1 year"
    ExpiresByType image/svg+xml "access plus 1 year"
</IfModule>

# Enable compression
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/plain
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/xml
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE application/xhtml+xml
    AddOutputFilterByType DEFLATE application/rss+xml
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/x-javascript
</IfModule>

# Prevent access to sensitive files
<FilesMatch "\.(env|pyc|log|sqlite|db|ini|cfg|conf)$">
    Order allow,deny
    Deny from all
</FilesMatch>

# Allow access to static files
<FilesMatch "\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|pdf|xlsx|docx|zip)$">
    Order allow,deny
    Allow from all
</FilesMatch>

# Disable directory listing
Options -Indexes

# Error handling
ErrorDocument 500 "Internal Server Error - Please check the application logs"
ErrorDocument 404 "Page Not Found"
```

### Step 2: Verify cPanel Addon Domain Configuration

1. **cPanel → Domains → Addon Domains** এ যান
2. `kulawams.xyz` domain select করুন
3. **Document Root** check করুন: `/home/gronthon/kulawams.xyz`
4. যদি ভুল থাকে, **Edit** করুন এবং correct path set করুন

### Step 3: Verify `passenger_wsgi.py` exists

File path: `/home/gronthon/kulawams.xyz/passenger_wsgi.py`

**Content should be**:
```python
#!/usr/bin/env python3
"""
Passenger WSGI file for cPanel Python application deployment
"""

import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Set environment variables for cPanel
os.environ['CPANEL'] = '1'
os.environ['FLASK_ENV'] = 'production'

# Import the Flask application
from app import create_app

# Create the application instance
application = create_app()

# For debugging purposes
if __name__ == '__main__':
    application.run(debug=False, host='0.0.0.0', port=5000)
```

**File permissions**: `644` বা `755`

### Step 4: Restart Application

**Option 1: Touch restart file** (Recommended)
```bash
cd /home/gronthon/kulawams.xyz
touch tmp/restart.txt
```

**Option 2: Via cPanel**
- cPanel → Applications → Python App → kulawams.xyz → Restart

**Option 3: Touch passenger_wsgi.py**
```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
```

### Step 5: Clear Browser Cache

Browser cache clear করুন এবং আবার try করুন।

## Troubleshooting

### যদি এখনও 404 দেখায়:

1. **Check Error Logs**:
   ```bash
   # cPanel → Errors → Error Log
   # বা SSH-এ:
   tail -f /home/gronthon/kulawams.xyz/logs/app_errors.log
   ```

2. **Check .htaccess syntax**:
   ```bash
   # SSH-এ test করুন:
   apachectl -t
   # বা
   /usr/local/apache/bin/apachectl configtest
   ```

3. **Verify Passenger is enabled**:
   - cPanel → Select Python Version → Check Passenger is enabled

4. **Check file permissions**:
   ```bash
   cd /home/gronthon/kulawams.xyz
   chmod 644 .htaccess
   chmod 644 passenger_wsgi.py
   chmod 644 app.py
   ```

5. **Test passenger_wsgi.py directly**:
   ```bash
   cd /home/gronthon/kulawams.xyz
   source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
   python passenger_wsgi.py
   # কোনো error আসলে fix করুন
   ```

### যদি "Internal Server Error" দেখায়:

1. **Check Python application logs**
2. **Verify virtual environment path** in `.htaccess`:
   ```
   PassengerPython /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python
   ```
3. **Verify all dependencies installed**:
   ```bash
   source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
   pip list
   ```

## Quick Fix Commands (SSH)

```bash
# 1. Navigate to directory
cd /home/gronthon/kulawams.xyz

# 2. Create/update .htaccess (copy content from above)
nano .htaccess
# বা File Manager দিয়ে upload করুন

# 3. Verify passenger_wsgi.py exists and is correct
ls -la passenger_wsgi.py

# 4. Set correct permissions
chmod 644 .htaccess
chmod 644 passenger_wsgi.py

# 5. Restart application
touch tmp/restart.txt
# বা
touch passenger_wsgi.py

# 6. Check if Passenger is running
ps aux | grep passenger
```

## Important Notes

1. **`.htaccess` file** `kulawams.xyz` directory-তে থাকতে হবে (main directory `/home/gronthon/` এ নয়)
2. **Document Root** cPanel-এ correctly set করতে হবে
3. **Passenger Python path** virtual environment path match করতে হবে
4. **File permissions** সঠিক হতে হবে (644 for files, 755 for directories)

## Verification Checklist

- [ ] `.htaccess` file exists in `/home/gronthon/kulawams.xyz/`
- [ ] `passenger_wsgi.py` exists and has correct content
- [ ] Addon domain Document Root is `/home/gronthon/kulawams.xyz`
- [ ] File permissions are correct (644)
- [ ] Application restarted (touched restart file)
- [ ] Browser cache cleared
- [ ] Error logs checked (if still not working)
