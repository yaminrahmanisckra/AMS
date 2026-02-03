# cPanel Bulk Download Deployment - Required Files

## 📋 Bulk Download Feature-এর জন্য প্রয়োজনীয় ফাইলসমূহ

### 1. Core Application Files (অবশ্যই আপলোড করতে হবে)

```
app.py                          ⚠️ CRITICAL - Bulk download routes এবং logic আছে
```

**app.py-তে যা আছে:**
- `remuneration_bulk_download()` - Bulk PDF generation route
- `remuneration_get_teachers()` - Teacher filtering API
- `_build_jobs_from_statement()` - Statement data থেকে jobs data তৈরি
- `_number_to_words_bengali()` - সংখ্যাকে বাংলা কথায় রূপান্তর
- `_is_postgraduate_course()` - PG/UG course detection
- `_matches_teacher_name()` - Teacher name matching

### 2. Template Files (অবশ্যই আপলোড করতে হবে)

```
templates/
├── remuneration_placeholder.html    ⚠️ CRITICAL - Frontend form এবং JavaScript
└── remuneration_pdf_template.html   ⚠️ CRITICAL - PDF template
```

**remuneration_placeholder.html-তে যা আছে:**
- Bulk download modal UI
- `startBulkDownload()` JavaScript function
- `loadDataForRow15()` - Coding/Decoding data loading
- `numberToBengaliWords()` - Client-side number conversion

**remuneration_pdf_template.html-তে যা আছে:**
- PDF structure এবং formatting
- Jobs data display
- Total amount in words display

### 3. Static Files (অবশ্যই আপলোড করতে হবে)

```
static/
├── Images/
│   └── KU_logo_2.png              ⚠️ CRITICAL - PDF-তে logo দেখানোর জন্য
└── Fonts/
    └── kalpurush.ttf               ⚠️ CRITICAL - PDF-তে বাংলা font
```

**মনে রাখবেন:**
- Logo path: `static/Images/KU_logo_2.png`
- Font path: `static/Fonts/kalpurush.ttf`
- এই paths app.py-তে hardcoded আছে

### 4. Supporting Files (যদি না থাকে তাহলে আপলোড করুন)

```
extensions.py                      (Database extensions)
models.py                          (Database models)
role_utils.py                      (Role utilities)
utils/
├── __init__.py
└── semester_utils.py              (Semester utilities)
```

### 5. Configuration Files

```
.htaccess                          (Apache configuration)
passenger_wsgi.py                  (cPanel Python app entry point)
requirements.txt                   (Python dependencies)
```

---

## 📦 Step-by-Step Upload Process

### Step 1: Backup Current Files (প্রথমে backup নিন)

```bash
# cPanel Terminal বা SSH-তে
cd /home/username/domain.com
cp -r templates templates_backup_$(date +%Y%m%d)
cp app.py app.py.backup_$(date +%Y%m%d)
```

### Step 2: Upload Critical Files

**Method 1: cPanel File Manager (Recommended)**

1. **Login to cPanel**
2. **File Manager** খুলুন
3. **Domain directory**-তে যান (যেমন: `/home/gronthon/kulawams.xyz/`)

4. **app.py upload করুন:**
   - Existing `app.py` select করুন
   - **Upload** button click করুন
   - নতুন `app.py` select করুন
   - **Replace** confirm করুন

5. **Templates upload করুন:**
   - `templates/remuneration_placeholder.html` upload করুন
   - `templates/remuneration_pdf_template.html` upload করুন
   - Existing files replace করুন

6. **Static files upload করুন:**
   - `static/Images/KU_logo_2.png` upload করুন (folder structure maintain করুন)
   - `static/Fonts/kalpurush.ttf` upload করুন (folder structure maintain করুন)

**Method 2: FTP/SFTP**

```bash
# Local machine থেকে
cd "/Users/isckra/Documents/App Projects/Academic Management System"

# app.py upload
scp app.py username@server:/home/username/domain.com/app.py

# Templates upload
scp templates/remuneration_placeholder.html username@server:/home/username/domain.com/templates/
scp templates/remuneration_pdf_template.html username@server:/home/username/domain.com/templates/

# Static files upload
scp static/Images/KU_logo_2.png username@server:/home/username/domain.com/static/Images/
scp static/Fonts/kalpurush.ttf username@server:/home/username/domain.com/static/Fonts/
```

### Step 3: Set File Permissions

```bash
# cPanel Terminal বা SSH-তে
cd /home/username/domain.com

# File permissions
chmod 644 app.py
chmod 644 templates/remuneration_placeholder.html
chmod 644 templates/remuneration_pdf_template.html
chmod 644 static/Images/KU_logo_2.png
chmod 644 static/Fonts/kalpurush.ttf

# Directory permissions
chmod 755 templates
chmod 755 static
chmod 755 static/Images
chmod 755 static/Fonts
```

### Step 4: Verify Dependencies

```bash
# Check if required Python packages are installed
pip list | grep -E "(weasyprint|flask|sqlalchemy)"

# If missing, install:
pip install weasyprint flask sqlalchemy
```

### Step 5: Restart Application

**Method 1: Touch passenger_wsgi.py (Recommended)**

```bash
cd /home/username/domain.com
touch passenger_wsgi.py
# Wait 15-20 seconds for restart
sleep 20
```

**Method 2: cPanel Python App Manager**

1. cPanel → **Applications** → **Python App Manager**
2. আপনার app select করুন
3. **Restart** button click করুন
4. 15-20 seconds wait করুন

### Step 6: Test Bulk Download

1. **Login করুন** application-এ
2. **Remuneration** section-এ যান
3. **Bulk Download** button click করুন
4. **Session, Year, Term** select করুন
5. **Teachers** select করুন
6. **Download** click করুন
7. **Verify:**
   - PDF generate হচ্ছে কিনা
   - Row 15 (কোডিং/ডিকোডিং) data আছে কিনা
   - Course codes শুধু দেখাচ্ছে (course names নেই)
   - Row 3 rate সঠিক দেখাচ্ছে
   - Total amount বাংলা কথায় দেখাচ্ছে

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] `app.py` uploaded successfully
- [ ] `templates/remuneration_placeholder.html` uploaded
- [ ] `templates/remuneration_pdf_template.html` uploaded
- [ ] `static/Images/KU_logo_2.png` exists
- [ ] `static/Fonts/kalpurush.ttf` exists
- [ ] File permissions set correctly (644 for files, 755 for directories)
- [ ] Application restarted successfully
- [ ] Bulk download modal opens
- [ ] Teachers list loads correctly
- [ ] PDF generates without errors
- [ ] Row 15 data appears in PDF
- [ ] Course codes only (no course names)
- [ ] Row 3 rate correct
- [ ] Total amount in Bengali words

---

## 🚨 Important Notes

### 1. File Paths (খুবই গুরুত্বপূর্ণ)

**Logo Path:**
- Must be: `static/Images/KU_logo_2.png`
- Case-sensitive: `Images` (capital I), not `images`

**Font Path:**
- Must be: `static/Fonts/kalpurush.ttf`
- Case-sensitive: `Fonts` (capital F), not `fonts`

### 2. Dependencies

Ensure these Python packages are installed:
```
weasyprint>=60.0    (PDF generation)
flask>=2.0.0        (Web framework)
sqlalchemy>=1.4.0   (Database ORM)
```

### 3. Memory Requirements

Bulk download can use significant memory:
- For 10-20 teachers: ~100-200MB
- For 50+ teachers: May need 512MB+ memory
- Check cPanel memory limits

### 4. Error Handling

If bulk download fails:
1. Check cPanel error logs
2. Check application logs: `logs/app_errors.log`
3. Verify all static files exist
4. Check file permissions
5. Verify Python dependencies

---

## 🔍 Troubleshooting

### Issue: "Failed to fetch" error

**Possible Causes:**
- Application not restarted
- Route not found
- Server error

**Solution:**
```bash
# Restart application
touch passenger_wsgi.py
sleep 20

# Check error logs
tail -50 logs/app_errors.log
```

### Issue: PDF generation fails

**Possible Causes:**
- Missing WeasyPrint
- Missing font file
- Missing logo file
- Memory limit exceeded

**Solution:**
```bash
# Install WeasyPrint
pip install weasyprint

# Verify files exist
ls -la static/Images/KU_logo_2.png
ls -la static/Fonts/kalpurush.ttf

# Check memory
free -h
```

### Issue: Row 15 data not showing

**Possible Causes:**
- `coding_decoding` data not in statement
- Teacher name mismatch
- Statement data not loaded

**Solution:**
- Verify statement data has `coding_decoding` section
- Check teacher name matching in logs
- Verify `remuneration_get_teachers()` includes `coding_decoding` in sections_to_check

### Issue: Course names showing instead of codes

**Possible Causes:**
- Old version of `app.py`
- Course data format issue

**Solution:**
- Verify `app.py` has course code extraction logic:
  ```python
  if ' - ' in course:
      course = course.split(' - ')[0].strip()
  ```

### Issue: Total amount showing numbers instead of words

**Possible Causes:**
- `_number_to_words_bengali()` function not working
- Old version of `app.py`

**Solution:**
- Verify `app.py` has complete `_number_to_words_bengali()` implementation
- Test function manually:
  ```python
  from app import _number_to_words_bengali
  print(_number_to_words_bengali(102699))
  # Should output: "এক লক্ষ দুই হাজার ছয় শত নিরানব্বই টাকা"
  ```

---

## 📝 Quick Upload Summary

**Minimum Required Files:**
1. ✅ `app.py`
2. ✅ `templates/remuneration_placeholder.html`
3. ✅ `templates/remuneration_pdf_template.html`
4. ✅ `static/Images/KU_logo_2.png`
5. ✅ `static/Fonts/kalpurush.ttf`

**After Upload:**
1. ✅ Set permissions (644 for files, 755 for directories)
2. ✅ Restart application (`touch passenger_wsgi.py`)
3. ✅ Test bulk download feature
4. ✅ Verify all features work

---

**Last Updated:** 2026-01-14
**Feature:** Bulk Remuneration PDF Download
**Version:** 2.0.0
