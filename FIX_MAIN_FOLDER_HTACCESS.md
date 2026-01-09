# Fix: Main Folder .htaccess Conflict with Addon Domain

## Problem

- Main domain `grontho.net` works (has .htaccess in main folder)
- Addon domain `kulawams.xyz` doesn't work
- .htaccess in main folder (`/home/gronthon/`) might be interfering

## Solution

### Step 1: Check Main Folder .htaccess

SSH-এ check করুন:
```bash
# Check if .htaccess exists in main folder
ls -la /home/gronthon/.htaccess

# If exists, check its content
cat /home/gronthon/.htaccess | head -20
```

### Step 2: Verify Addon Domain .htaccess

```bash
# Check addon domain .htaccess
ls -la /home/gronthon/kulawams.xyz/.htaccess

# Should exist and have Passenger configuration
cat /home/gronthon/kulawams.xyz/.htaccess | grep -i passenger
```

### Step 3: Fix Main Folder .htaccess

Main folder `.htaccess` শুধু main domain-এর জন্য হওয়া উচিত, addon domains-কে interfere করা উচিত নয়।

**Option A: If main .htaccess is generic and affecting all domains**

Main folder `.htaccess`-এ addon domains exclude করুন:

```apache
# At the top of /home/gronthon/.htaccess, add:

# Skip this .htaccess for addon domains
RewriteEngine On
RewriteCond %{HTTP_HOST} ^kulawams\.xyz$ [NC]
RewriteRule ^(.*)$ - [L]

# Continue with existing rules for grontho.net...
```

**Option B: If main .htaccess should only affect grontho.net**

Main folder `.htaccess`-এ specific domain check করুন:

```apache
# Only apply rules for grontho.net
<If "%{HTTP_HOST} == 'grontho.net'">
    # Your existing rules here
</If>
```

### Step 4: Ensure Addon Domain Has Its Own .htaccess

Make sure `/home/gronthon/kulawams.xyz/.htaccess` exists with correct Passenger config.

## Quick Fix

```bash
cd /home/gronthon

# Check main .htaccess
if [ -f .htaccess ]; then
    echo "Main .htaccess exists"
    echo "First 10 lines:"
    head -10 .htaccess
else
    echo "No main .htaccess - good"
fi

# Check addon .htaccess  
if [ -f kulawams.xyz/.htaccess ]; then
    echo "Addon .htaccess exists"
    echo "Passenger config:"
    grep -i passenger kulawams.xyz/.htaccess | head -5
else
    echo "ERROR: Addon .htaccess missing!"
fi
```

## Most Likely Issue

Main folder `.htaccess` addon domain requests intercept করছে, তাই `kulawams.xyz`-এর `.htaccess` execute হচ্ছে না।

## Solution Priority

1. **Check main folder .htaccess content**
2. **Modify it to exclude addon domains** (or make it domain-specific)
3. **Ensure kulawams.xyz/.htaccess exists and is correct**
4. **Restart both applications**
