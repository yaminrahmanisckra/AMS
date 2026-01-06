# cPanel Application Quick Fix Guide

## Problem: Application Stopped Working After File Replacement

If your application stopped working after replacing files (git pull or manual upload), follow these steps:

## Step 1: Run Diagnostic Script

```bash
cd ~/aqpub.com
git pull  # Get latest diagnostic script
bash diagnose_cpanel_issue.sh
```

This will show:
- Error logs (startup errors, application errors)
- Missing files
- File permission issues
- Import test results
- Dependency status

## Step 2: Run Fix Script

```bash
cd ~/aqpub.com
bash fix_cpanel_deployment.sh
```

This will automatically:
- Check and create `.env` file if missing
- Fix file permissions
- Verify passenger_wsgi.py
- Check dependencies
- Test application import

## Step 3: Manual Checks

### Check .env File

```bash
cd ~/aqpub.com
cat .env
```

**CRITICAL:** Ensure `.env` has:
- `DATABASE_URL=mysql+pymysql://username:password@localhost/database_name`
- `SECRET_KEY=your_secret_key_here`

If `.env` is missing or empty, restore it from backup or recreate it.

### Check Error Logs

```bash
# Startup errors (from improved passenger_wsgi.py)
tail -50 logs/passenger_startup_errors.log

# Application errors
tail -50 logs/app_errors.log
```

### Test Application Import

```bash
cd ~/aqpub.com
~/virtualenv/aqpub.com/3.12/bin/python3 -c "from app import create_app; app = create_app(); print('OK')"
```

### Fix Permissions

```bash
cd ~/aqpub.com
chmod 644 *.py *.txt .htaccess .env
chmod 755 blueprints/ templates/ static/ logs/ instance/
```

### Reinstall Dependencies (if needed)

```bash
cd ~/aqpub.com
~/virtualenv/aqpub.com/3.12/bin/pip3 install -r requirements.txt
```

## Step 4: Restart Application

### Option 1: cPanel Interface
1. cPanel → Software → Setup Python App
2. Select `aqpub.com`
3. Click **Restart**

### Option 2: Terminal
```bash
cd ~/aqpub.com
touch passenger_wsgi.py
```

## Common Issues and Solutions

### Issue 1: .env File Missing
**Symptom:** Application can't connect to database
**Solution:** Restore `.env` file with correct DATABASE_URL and SECRET_KEY

### Issue 2: File Permissions Wrong
**Symptom:** Files not readable or directories not accessible
**Solution:** Run `fix_cpanel_deployment.sh` or manually fix permissions

### Issue 3: Dependencies Missing
**Symptom:** Import errors in logs
**Solution:** Reinstall dependencies using virtual environment's pip

### Issue 4: passenger_wsgi.py Issues
**Symptom:** Startup errors in `logs/passenger_startup_errors.log`
**Solution:** Ensure you have the improved version with error handling

### Issue 5: Application Not Restarting
**Symptom:** Changes not taking effect
**Solution:** Restart via cPanel Python App interface

## Verification

After fixing, verify:
1. Application starts without errors
2. Browser can access the website
3. No errors in `logs/passenger_startup_errors.log`
4. No critical errors in `logs/app_errors.log`

## Important Notes

- `.env` file is in `.gitignore` - it should NOT be overwritten by git pull
- If `.env` was overwritten, restore it from backup
- Virtual environment packages are separate from system Python
- Always restart application after file changes
- Check `logs/passenger_startup_errors.log` for startup issues




