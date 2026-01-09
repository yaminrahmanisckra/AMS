# Fix: Make Main Folder .htaccess Domain-Specific

## Problem

Main folder `/home/gronthon/.htaccess` affects all domains, including addon domains. This causes conflicts.

## Solution

Make main folder `.htaccess` **only apply to `grontho.net`** (main domain).

## Step 1: Check Current Main .htaccess

SSH-এ run করুন:
```bash
# Check main .htaccess
cat /home/gronthon/.htaccess | head -30
```

## Step 2: Modify Main .htaccess to Be Domain-Specific

Main folder `.htaccess`-এ domain-specific rules করুন:

### Option A: Wrap Existing Rules in Domain Check

```apache
# Only apply to main domain grontho.net
<If "%{HTTP_HOST} == 'grontho.net' || %{HTTP_HOST} == 'www.grontho.net'">
    # Your existing rules here
    # (keep all existing configuration)
</If>

# For other domains (addon domains), don't apply these rules
```

### Option B: Add Rewrite Condition at Top

```apache
# Skip this .htaccess for addon domains
RewriteEngine On

# If request is for kulawams.xyz, don't process this .htaccess
RewriteCond %{HTTP_HOST} ^kulawams\.xyz$ [NC]
RewriteRule ^(.*)$ - [L]

# Continue with rules for grontho.net
# (your existing rules)
```

## Step 3: Verify Addon Domain .htaccess

Make sure `/home/gronthon/kulawams.xyz/.htaccess` exists and is correct.

## Step 4: Restart Applications

```bash
# Restart main domain
touch /home/gronthon/tmp/restart.txt

# Restart addon domain  
touch /home/gronthon/kulawams.xyz/tmp/restart.txt
touch /home/gronthon/kulawams.xyz/passenger_wsgi.py
```

## Important Notes

1. **Each addon domain needs its own .htaccess** in its own directory
2. **Main folder .htaccess should only affect main domain**
3. **Use domain-specific conditions** to prevent conflicts
