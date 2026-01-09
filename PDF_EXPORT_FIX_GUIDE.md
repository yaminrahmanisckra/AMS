# PDF Export Error Fix Guide - Remuneration

## Problem
- **Error**: "Failed to generate PDF document"
- **Location**: `/remuneration/export-pdf` route
- **Symptom**: PDF export fails with generic error message

## Fixes Applied

### 1. Improved Error Handling
- Added WeasyPrint import check with detailed error messages
- Enhanced exception handling to provide specific error details
- Better error messages for common issues (WeasyPrint, Template, Permission)

### 2. Files Changed
- `app.py` - Enhanced error handling in `remuneration_export_pdf()` function

## Server-Side Diagnosis

### Check 1: Verify WeasyPrint Installation

```bash
# SSH into server
ssh gronthon@your-server-ip

# Activate virtual environment
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate  # or aqpub.com

# Check if WeasyPrint is installed
python3 -c "from weasyprint import HTML, CSS; print('✅ WeasyPrint installed')" 2>&1
```

**Expected Output:**
- ✅ `WeasyPrint installed` - WeasyPrint is working
- ❌ ImportError or other error - WeasyPrint needs to be installed or dependencies are missing

### Check 2: Install WeasyPrint (if missing)

```bash
# Make sure virtual environment is activated
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Install WeasyPrint
pip install weasyprint

# Verify installation
python3 -c "from weasyprint import HTML, CSS; print('✅ WeasyPrint installed successfully')"
```

### Check 3: Install WeasyPrint System Dependencies (if needed)

WeasyPrint requires system libraries. On cPanel/LiteSpeed servers, these might be missing:

```bash
# On CentOS/RHEL/CloudLinux (cPanel typically uses these)
# These commands require root access or may need hosting support

# For Ubuntu/Debian:
# sudo apt-get install python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0

# Note: On cPanel shared hosting, system dependencies are usually managed by the hosting provider
# If installation fails, contact hosting support
```

### Check 4: Check Application Logs

```bash
# Check for detailed error logs
tail -50 /home/gronthon/kulawams.xyz/passenger_wsgi.log | grep -i "pdf\|weasyprint\|error" | tail -20

# Check startup errors
cat /home/gronthon/kulawams.xyz/startup_error.log 2>/dev/null | grep -i "weasyprint\|pdf" | tail -10
```

### Check 5: Test PDF Generation Directly

```bash
cd /home/gronthon/kulawams.xyz
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate

# Test WeasyPrint import and basic functionality
python3 << 'PYTHON_TEST'
try:
    from weasyprint import HTML, CSS
    from io import BytesIO
    
    # Create a simple test HTML
    html_content = "<html><body><h1>Test PDF</h1></body></html>"
    pdf_buffer = BytesIO()
    
    # Try to generate PDF
    html = HTML(string=html_content)
    html.write_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    if len(pdf_buffer.getvalue()) > 0:
        print("✅ WeasyPrint is working correctly")
    else:
        print("❌ WeasyPrint generated empty PDF")
except ImportError as e:
    print(f"❌ WeasyPrint import error: {e}")
except Exception as e:
    print(f"❌ WeasyPrint error: {type(e).__name__}: {e}")
PYTHON_TEST

deactivate
```

## Common Issues and Solutions

### Issue 1: WeasyPrint Not Installed

**Symptom**: ImportError when importing WeasyPrint

**Solution**:
```bash
source /home/gronthon/virtualenv/kulawams.xyz/3.12/bin/activate
pip install weasyprint
deactivate
```

### Issue 2: System Dependencies Missing

**Symptom**: WeasyPrint imports but fails when generating PDF with errors about cairo, pango, etc.

**Solution**: Contact hosting support to install system dependencies:
- `cairo`
- `pango`
- `gdk-pixbuf`
- `libffi`

### Issue 3: Template File Missing

**Symptom**: TemplateNotFoundError

**Solution**: Verify template exists:
```bash
ls -la /home/gronthon/kulawams.xyz/templates/remuneration_pdf_template.html
```

If missing, ensure all template files are uploaded to server.

### Issue 4: Memory Issues

**Symptom**: PDF generation works sometimes but fails with large data

**Solution**: The code already includes memory cleanup in `finally` block. If issues persist:
- Increase server memory limits
- Optimize PDF template to reduce memory usage

### Issue 5: Font File Missing

**Symptom**: Font-related errors in PDF generation

**Solution**: Verify Kalpurush font exists:
```bash
ls -la /home/gronthon/kulawams.xyz/static/fonts/kalpurush.ttf
# or
ls -la /home/gronthon/kulawams.xyz/static/Fonts/kalpurush.ttf
```

## After Applying Fix - Testing

### 1. Upload Fixed app.py

Follow the cPanel upload guide to upload the fixed `app.py` file.

### 2. Restart Application

```bash
touch /home/gronthon/kulawams.xyz/passenger_wsgi.py
sleep 20
```

### 3. Test PDF Export

**Via Browser:**
1. Go to Remuneration page
2. Fill out the form
3. Click "Export PDF" button
4. Check browser console (F12) for detailed error messages if it fails

**Via Terminal (if possible):**
```bash
# Test the route directly (this requires form data, so browser test is better)
curl -X POST https://kulawams.xyz/remuneration/export-pdf \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "voucher_no=TEST&applicant_name=Test" \
  2>&1 | head -20
```

### 4. Check Error Response

The improved error handling will now return JSON with detailed error information:
```json
{
  "error": "Failed to generate PDF document",
  "message": "Detailed error message here",
  "type": "ErrorType"
}
```

Check browser console (F12 → Network → Response) to see the detailed error message.

## Verification Checklist

- [ ] WeasyPrint is installed: `pip list | grep -i weasyprint`
- [ ] WeasyPrint can be imported: Python test passes
- [ ] Template file exists: `remuneration_pdf_template.html`
- [ ] Font file exists: `static/fonts/kalpurush.ttf` or `static/Fonts/kalpurush.ttf`
- [ ] Fixed `app.py` is uploaded to server
- [ ] Application is restarted
- [ ] Test PDF export in browser
- [ ] Check browser console for detailed error if it fails
- [ ] Check server logs for detailed error messages

## Next Steps if Issue Persists

1. **Check server logs** for the actual error (now with improved logging)
2. **Check browser console** for detailed error response
3. **Run diagnostic tests** above to identify specific issue
4. **Contact hosting support** if system dependencies are missing
5. **Share error details** from logs/console for further debugging

---

**Last Updated**: 2026-01-09
**Fixed**: Improved error handling for PDF export failures
**Files Changed**: `app.py`
