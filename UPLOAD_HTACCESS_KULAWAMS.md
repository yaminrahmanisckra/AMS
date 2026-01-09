# Upload .htaccess for kulawams.xyz

## Quick Instructions

### Step 1: Upload `.htaccess` file

1. **cPanel → File Manager**
2. Navigate to: `/home/gronthon/kulawams.xyz/`
3. Upload file: `kulawams.htaccess` (from local repository)
4. Rename to: `.htaccess` (dot at the beginning)
5. Set permissions: `644`

### Step 2: Restart Application

**Via SSH:**
```bash
cd /home/gronthon/kulawams.xyz
touch tmp/restart.txt
```

**Or:**
```bash
touch passenger_wsgi.py
```

### Step 3: Test

Open `kulawams.xyz` in browser - should work now!

---

## File Content

The `.htaccess` file has been created based on your `aqpub.com` configuration, with these changes:
- `aqpub.com` → `kulawams.xyz` (all paths)
- PassengerAppRoot: `/home/gronthon/kulawams.xyz`
- PassengerPython: `/home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python`
- Mail settings: `recovery@kulawams.xyz`

## Important Notes

1. **CloudLinux Passenger Configuration** - DO NOT REMOVE or modify the Passenger configuration blocks
2. **Mail Settings** - Update mail password if different for kulawams.xyz
3. **File Permissions** - Must be `644` for `.htaccess`
4. **Restart Required** - Application must be restarted after uploading

## Troubleshooting

If still getting 404:

1. **Check file exists:**
   ```bash
   ls -la /home/gronthon/kulawams.xyz/.htaccess
   ```

2. **Check permissions:**
   ```bash
   chmod 644 /home/gronthon/kulawams.xyz/.htaccess
   ```

3. **Check Passenger Python path:**
   ```bash
   ls -la /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/python
   ```

4. **Check error logs:**
   - cPanel → Errors → Error Log
   - Look for Passenger-related errors

5. **Verify addon domain:**
   - cPanel → Domains → Addon Domains
   - Check Document Root is: `/home/gronthon/kulawams.xyz`
