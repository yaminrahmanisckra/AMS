# Fix: Passenger Not Running (LiteSpeed Serving Instead)

## Problem Identified

- ✅ `startup_error.log` is empty (app loads fine)
- ✅ Python app works when tested directly
- ❌ Browser shows 404 and `Server: LiteSpeed` (Passenger not being used)

**Issue:** Passenger is not being invoked. LiteSpeed web server is handling requests directly instead of passing them to Passenger.

## Solutions

### Solution 1: Check cPanel Python Application Setup

1. **cPanel → Applications → Python** (or **Setup Python App**)
2. Check if `kulawams.xyz` Python application exists
3. If **NOT listed**, you need to **Create Application**:
   - **Application Root:** `/home/gronthon/kulawams.xyz`
   - **Application URL:** `kulawams.xyz`
   - **Application Startup File:** `passenger_wsgi.py`
   - **Application Entry Point:** `application`
   - **Python Version:** `3.12`
4. Click **Create**
5. Make sure status is **Started/Active**

### Solution 2: Verify Passenger Module is Enabled

LiteSpeed might need Passenger module enabled. Check with hosting provider if Passenger/LSAPI is enabled for your account.

### Solution 3: Alternative .htaccess for LiteSpeed

If LiteSpeed is the web server, try this modified `.htaccess`:

```apache
# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION BEGIN
PassengerEnabled On
PassengerAppRoot "/home/gronthon/kulawams.xyz"
PassengerBaseURI "/"
PassengerAppType wsgi
PassengerStartupFile passenger_wsgi.py
PassengerPython "/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python"
# DO NOT REMOVE. CLOUDLINUX PASSENGER CONFIGURATION END

SetEnv CPANEL 1
SetEnv FLASK_ENV production

# LiteSpeed specific - route all requests to Passenger
<IfModule LiteSpeed>
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ passenger_wsgi.py/$1 [L]
</IfModule>

# Apache/standard rewrite (backup)
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ passenger_wsgi.py/$1 [QSA,L]
</IfModule>

# Security headers
<IfModule mod_headers.c>
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options SAMEORIGIN
</IfModule>

<FilesMatch "\.(env|pyc|log|sqlite|db)$">
    Require all denied
</FilesMatch>

Options -Indexes
AddDefaultCharset UTF-8

# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION BEGIN
<IfModule Litespeed>
SetEnv MAIL_SERVER recovery@kulawams.xyz
SetEnv MAIL_PORT 25
SetEnv MAIL_USE_TLS False
SetEnv MAIL_USE_SSL False
SetEnv MAIL_USERNAME recovery@kulawams.xyz
SetEnv MAIL_PASSWORD @24010905i
SetEnv MAIL_DEFAULT_SENDER recovery@kulawams.xyz
</IfModule>
# DO NOT REMOVE OR MODIFY. CLOUDLINUX ENV VARS CONFIGURATION END

# php handler
<IfModule mime_module>
  AddHandler application/x-httpd-ea-php72 .php .php7 .phtml
</IfModule>
```

### Solution 4: Contact Hosting Provider

If Passenger is not working, contact hosting provider and ask:
- Is Passenger/LSAPI enabled for my account?
- Why is LiteSpeed serving requests instead of Passenger?
- How do I enable Passenger for addon domain `kulawams.xyz`?

## Quick Check Commands

```bash
# Check if Python app exists in cPanel (if you have CLI access to cPanel)
# Otherwise check via cPanel web interface

# Check if Passenger is actually running
ps aux | grep -i passenger | grep -v grep

# Check LiteSpeed configuration (if accessible)
# Usually not accessible on shared hosting
```

## Most Important Action

**Go to cPanel → Applications → Python** and check if `kulawams.xyz` application exists and is started.

This is the most likely cause of the issue.
