# Bulk Download System - cPanel Upload Guide

## 📋 ফাইল আপলোড করার তালিকা

### ⚠️ **অত্যাবশ্যক ফাইল (Must Upload)**

#### 1. Core Application File
```
app.py                    ⚠️ CRITICAL - Contains bulk download routes and logic
```

**পরিবর্তনসমূহ:**
- `remuneration_bulk_download()` - Bulk PDF generation route
- `remuneration_get_teachers()` - Teacher filtering API
- `_build_jobs_from_statement()` - Statement data processing
- `_number_to_words_bengali()` - Bengali number to words conversion
- `_is_postgraduate_course()` - PG/UG course detection
- `_matches_teacher_name()` - Teacher name matching
- Course code extraction (removing course names)
- Row 15 (কোডিং/ডিকোডিং) processing

#### 2. PDF Template
```
templates/remuneration_pdf_template.html    ⚠️ CRITICAL - PDF template
```

**পরিবর্তনসমূহ:**
- Font sizes increased (7pt → 9pt, 6pt → 8pt, etc.)
- Stamp box size: 2.5cm x 2cm
- All font sizes updated for better readability

#### 3. Frontend Template (Optional - if updated)
```
templates/remuneration_placeholder.html     ⚠️ Check if updated
```

**যাচাই করুন:**
- Bulk download button/UI
- JavaScript for bulk download trigger
- Error handling messages

---

## 📦 সম্পূর্ণ আপলোড প্রক্রিয়া

### Step 1: Backup করুন
```bash
# cPanel Terminal বা SSH-এ
cd /home/username/yourdomain.com
cp app.py app.py.backup
cp templates/remuneration_pdf_template.html templates/remuneration_pdf_template.html.backup
```

### Step 2: ফাইল আপলোড করুন

#### Method 1: cPanel File Manager
1. **Login to cPanel**
2. **File Manager** খুলুন
3. আপনার domain directory-তে যান (সাধারণত `public_html` বা domain-specific folder)
4. নিচের ফাইলগুলো আপলোড করুন:

**প্রধান ফাইল:**
- `app.py` → Replace existing file
- `templates/remuneration_pdf_template.html` → Replace existing file

**যদি `remuneration_placeholder.html` আপডেট হয়ে থাকে:**
- `templates/remuneration_placeholder.html` → Replace existing file

#### Method 2: FTP/SFTP
```bash
# FileZilla বা অন্য FTP client ব্যবহার করুন
# Upload these files:
app.py
templates/remuneration_pdf_template.html
templates/remuneration_placeholder.html (if updated)
```

#### Method 3: Terminal/SSH (rsync)
```bash
# Local machine থেকে
cd "/Users/isckra/Documents/App Projects/Academic Management System"

# Upload app.py
scp app.py username@your-server:/home/username/yourdomain.com/app.py

# Upload template
scp templates/remuneration_pdf_template.html username@your-server:/home/username/yourdomain.com/templates/remuneration_pdf_template.html
```

### Step 3: File Permissions সেট করুন
```bash
# cPanel Terminal বা SSH-এ
cd /home/username/yourdomain.com

# Set permissions
chmod 644 app.py
chmod 644 templates/remuneration_pdf_template.html
chmod 644 templates/remuneration_placeholder.html

# Directory permissions
chmod 755 templates/
```

### Step 4: Application Restart করুন

#### Option A: Passenger (cPanel Python App)
1. cPanel → **Python App Manager** খুলুন
2. আপনার app খুঁজুন
3. **Restart** button ক্লিক করুন
4. 15-20 সেকেন্ড অপেক্ষা করুন

#### Option B: Terminal (touch method)
```bash
cd /home/username/yourdomain.com
touch passenger_wsgi.py
sleep 20
```

#### Option C: cPanel Terminal
```bash
# If using Passenger
touch passenger_wsgi.py

# If using systemd
sudo systemctl restart your-app-name

# Wait for restart
sleep 20
```

---

## ✅ Verification (যাচাই)

### 1. Check Application Status
```bash
# Check if app is running
curl -I https://yourdomain.com/ 2>&1 | grep -E "HTTP/"

# Should return: HTTP/2 200 or HTTP/2 302
```

### 2. Test Bulk Download Feature
1. Browser-এ login করুন
2. **Remuneration** section-এ যান
3. **Bulk Download** button খুঁজুন
4. Teachers select করুন
5. PDF download test করুন

### 3. Check Error Logs
```bash
# Check application logs
tail -50 /home/username/yourdomain.com/passenger_wsgi.log | tail -20

# Check for errors
grep -i "error\|exception" /home/username/yourdomain.com/passenger_wsgi.log | tail -10
```

### 4. Verify PDF Generation
- Single PDF download test করুন
- Bulk PDF download test করুন
- Font sizes check করুন (বড় হওয়া উচিত)
- Stamp box size check করুন (2.5cm x 2cm)
- Bengali words conversion check করুন (সংখ্যা কথায়)

---

## 🔍 Troubleshooting

### Issue: 500 Error after upload
**Solution:**
```bash
# Check syntax
python3 -m py_compile app.py

# Check logs
tail -50 passenger_wsgi.log

# Clear cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -r {} + 2>/dev/null
touch passenger_wsgi.py
```

### Issue: Bulk download not working
**Solution:**
1. Check browser console for JavaScript errors
2. Check server logs for Python errors
3. Verify `remuneration_placeholder.html` is uploaded
4. Check if WeasyPrint is installed: `pip list | grep weasyprint`

### Issue: Font sizes not updated
**Solution:**
1. Clear browser cache
2. Check if `remuneration_pdf_template.html` is correctly uploaded
3. Verify CSS in template file

### Issue: Bengali words not converting
**Solution:**
1. Check `_number_to_words_bengali()` function in `app.py`
2. Verify function is being called correctly
3. Check logs for conversion errors

---

## 📝 Quick Checklist

- [ ] `app.py` uploaded
- [ ] `templates/remuneration_pdf_template.html` uploaded
- [ ] `templates/remuneration_placeholder.html` uploaded (if updated)
- [ ] File permissions set (644 for files, 755 for directories)
- [ ] Application restarted
- [ ] Tested single PDF download
- [ ] Tested bulk PDF download
- [ ] Verified font sizes are larger
- [ ] Verified stamp box is 2.5cm x 2cm
- [ ] Verified Bengali number to words conversion
- [ ] Checked error logs (no errors)

---

## 🎯 Key Features in This Update

1. ✅ **Bulk PDF Download** - Download multiple remuneration PDFs at once
2. ✅ **Teacher Filtering** - Only shows teachers with statement data
3. ✅ **Row 15 Support** - কোডিং/ডিকোডিং data processing
4. ✅ **Course Code Only** - Removed course names from course number column
5. ✅ **Rate Display Fix** - Shows actual rate instead of "80/100/160"
6. ✅ **Bengali Words** - Number to words conversion (102699 → "এক লক্ষ দুই হাজার...")
7. ✅ **Larger Fonts** - All font sizes increased for better readability
8. ✅ **Stamp Box Size** - 2.5cm x 2cm

---

## 📞 Support

যদি কোনো সমস্যা হয়:
1. Error logs check করুন
2. Browser console check করুন
3. Server logs check করুন
4. File permissions verify করুন

---

**Last Updated:** 2026-01-14  
**Version:** Bulk Download System v1.0
