# Reveal Feature Upload Guide

## Database Migration ✅
- `is_revealed` column already added to `saved_routine` table

## Files to Upload to cPanel

Upload these 3 files to your server:

### 1. Models File
**Path on server:** `blueprints/routine_management/models.py`
- Replace the existing file

### 2. Routes File  
**Path on server:** `blueprints/routine_management/routes.py`
- Replace the existing file

### 3. Template File
**Path on server:** `blueprints/routine_management/templates/routine_management/index.html`
- Replace the existing file

## Steps to Upload

1. Login to cPanel
2. Go to File Manager
3. Navigate to your application directory (e.g., `public_html` or domain root)
4. Upload the 3 files above to their respective locations
5. Restart Python Application (if needed):
   - Go to "Setup Python App"
   - Click "Restart" on your application

## Testing

After uploading:

1. **Go to Routine Management Dashboard**
   - Navigate to `/routine-management/`

2. **Check Saved Routines Section**
   - You should see a "Status" column
   - Each routine should have a "Reveal/Hide" button

3. **Test Reveal Functionality**
   - Click "Reveal" button on a routine
   - Confirm the dialog
   - Status should change to "Revealed" (green badge)
   - Button should change to "Hide"

4. **Test View Routine (for all users)**
   - Go to `/routine-management/view_routine`
   - The revealed routine should automatically load
   - Non-editors should see it in read-only mode

## Features

✅ Reveal/Hide button in dashboard
✅ Status badge showing "Revealed" or "Hidden"
✅ Revealed routines visible to all teachers and students
✅ Read-only access for non-editors
✅ Automatic loading of most recent revealed routine
