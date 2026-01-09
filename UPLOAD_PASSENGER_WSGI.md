# Upload Updated passenger_wsgi.py

## Updated File

The `passenger_wsgi.py` file has been updated with:
- Virtual environment activation using `activate_this.py`
- Comprehensive error logging
- Startup error logging to file
- Better environment setup

## Upload Instructions

### Step 1: Upload passenger_wsgi.py

1. **cPanel → File Manager**
2. Navigate to `/home/gronthon/kulawams.xyz/`
3. Upload updated `passenger_wsgi.py` file
4. **Set permissions: `644` or `755`**

### Step 2: Check Log Files (After Upload)

SSH-এ:
```bash
cd /home/gronthon/kulawams.xyz

# Check startup error log
cat startup_error.log 2>/dev/null || echo "No startup errors"

# Check passenger WSGI log
tail -50 passenger_wsgi.log 2>/dev/null || echo "No log file yet"
```

### Step 3: Restart Application

```bash
cd /home/gronthon/kulawams.xyz
touch tmp/restart.txt
touch passenger_wsgi.py

# Wait for restart
sleep 10
```

### Step 4: Check for Errors

```bash
# Check startup errors
cat startup_error.log 2>/dev/null

# Check application logs
tail -50 passenger_wsgi.log 2>/dev/null
```

## Troubleshooting

If you see errors in `startup_error.log`:
- Fix the errors shown
- Common issues:
  - Missing dependencies (install via pip)
  - Import errors (check file paths)
  - Database connection issues (check .env file)

## Benefits of Updated Version

1. **Virtual Environment Activation**: Ensures all packages from venv are available
2. **Error Logging**: Errors are logged to `startup_error.log` for easy debugging
3. **Application Logging**: Application logs go to `passenger_wsgi.log`
4. **Better Error Messages**: Full traceback helps identify issues quickly
