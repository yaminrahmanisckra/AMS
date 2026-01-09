# Manual Upload Instructions: Delete Old Semester Data Feature

## Files to Upload to cPanel

### 1. Backend Files

#### `app.py`
- **Local Path**: `app.py`
- **Server Path**: `/home/gronthon/kulawams.xyz/app.py`
- **Changes**: Added two new routes:
  - `/admin/active-semester/preview-deletion` (POST)
  - `/admin/active-semester/delete-old-data` (POST)

### 2. Template Files

#### `templates/admin/active_semester.html`
- **Local Path**: `templates/admin/active_semester.html`
- **Server Path**: `/home/gronthon/kulawams.xyz/templates/admin/active_semester.html`
- **Changes**: Added "Delete Old Semester Data" section with form and JavaScript

## Step-by-Step Upload Instructions

### Step 1: Connect to cPanel File Manager or use FTP/SSH

### Step 2: Navigate to Project Directory
```
/home/gronthon/kulawams.xyz
```

### Step 3: Upload Files

1. **Upload `app.py`**
   - Backup existing file first (rename to `app.py.backup`)
   - Upload new `app.py` from local machine
   - Verify file permissions: `644` or `644` (readable by web server)

2. **Upload `templates/admin/active_semester.html`**
   - Backup existing file first (rename to `active_semester.html.backup`)
   - Upload new `active_semester.html` from local machine
   - Verify file permissions: `644`

### Step 4: Restart Application

After uploading files, restart the application by touching `passenger_wsgi.py`:

**Via SSH:**
```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
touch passenger_wsgi.py
```

**Or via cPanel Terminal:**
```bash
cd /home/gronthon/kulawams.xyz
touch passenger_wsgi.py
```

### Step 5: Verify Upload

1. Login to admin account
2. Navigate to: `/admin/active-semester`
3. Check if "Delete Old Semester Data" section is visible (red card with trash icon)
4. Test preview functionality:
   - Select Academic Session, Year, Term
   - Click "Preview Deletion" button
   - Should show counts of records to be deleted

## Important Notes

1. **No Database Migration Required**: This feature doesn't require any database schema changes.

2. **Backup Before Upload**: Always backup existing files before uploading new ones.

3. **File Permissions**: Ensure files are readable by the web server user.

4. **Testing**: After upload, test the feature with an inactive semester first before using on production data.

5. **Safety**: The feature includes multiple safety checks:
   - Cannot delete active semester data
   - Requires admin access
   - 3-step confirmation process
   - Transaction rollback on errors

## Troubleshooting

### If the feature doesn't appear:
1. Check file upload was successful
2. Verify `passenger_wsgi.py` was touched (application restarted)
3. Clear browser cache
4. Check browser console for JavaScript errors

### If preview doesn't work:
1. Check browser console for errors
2. Verify routes are accessible (check Flask logs)
3. Ensure user has admin privileges

### If deletion fails:
1. Check Flask application logs
2. Verify semester is inactive
3. Check database connection
4. Review error messages in browser

## File Checklist

- [ ] `app.py` uploaded
- [ ] `templates/admin/active_semester.html` uploaded
- [ ] `passenger_wsgi.py` touched (application restarted)
- [ ] Feature visible in admin panel
- [ ] Preview functionality tested
- [ ] Confirmation dialogs working

## Quick Upload Command (SSH)

If you have SSH access, you can also use these commands:

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Backup existing files
cp app.py app.py.backup.$(date +%Y%m%d_%H%M%S)
cp templates/admin/active_semester.html templates/admin/active_semester.html.backup.$(date +%Y%m%d_%H%M%S)

# Then upload new files via File Manager or SCP
# After upload:
touch passenger_wsgi.py
```

