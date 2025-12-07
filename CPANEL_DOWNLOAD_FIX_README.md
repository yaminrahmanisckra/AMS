# cPanel PDF/Excel Download Fix Guide

## সমস্যা (Problem)
আপনার Academic Management System এ cPanel deployment এ PDF এবং Excel downloads কাজ করছে না। লগে দেখাচ্ছে PDF তৈরি হচ্ছে কিন্তু ডাউনলোড হচ্ছে না এবং সার্ভার এরর (500) দেখাচ্ছে।

## সমাধান (Solution)
এই সমস্যা সমাধানের জন্য আমরা নিম্নলিখিত পরিবর্তনগুলি করেছি:

### 1. Flask Response পরিবর্তন
`send_file` এর পরিবর্তে `Response` ব্যবহার করা হয়েছে cPanel compatibility এর জন্য:

**পূর্বে:**
```python
return send_file(
    buffer, 
    as_attachment=True, 
    download_name=filename, 
    mimetype='application/pdf'
)
```

**পরবর্তে:**
```python
return Response(
    buffer.getvalue(),
    mimetype='application/pdf',
    headers={
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Content-Length': str(len(buffer.getvalue()))
    }
)
```

### 2. .htaccess ফাইল আপডেট
নতুন `.htaccess` ফাইল তৈরি করা হয়েছে যা:
- PDF/Excel downloads এর জন্য proper headers set করে
- mod_security rules disable করে download endpoints এর জন্য
- Memory এবং execution limits বাড়ায়
- CORS headers যোগ করে

### 3. পরিবর্তিত ফাইলগুলি
- `blueprints/class_management/routes.py` - PDF/Excel download functions
- `blueprints/result_management/routes.py` - PDF download functions  
- `.htaccess` - Server configuration

## ইনস্টলেশন (Installation)

### Step 1: ফাইলগুলি আপলোড করুন
সব পরিবর্তিত ফাইলগুলি cPanel এ আপলোড করুন।

### Step 2: Permissions সেট করুন
```bash
# Directories
chmod 755 uploads/
chmod 755 logs/
chmod 755 static/

# Files
chmod 644 .htaccess
chmod 644 *.py
```

### Step 3: Python Application Restart
cPanel এ Python application restart করুন।

### Step 4: Test করুন
`test_downloads_fixed.py` script run করে test করুন।

## টেস্টিং (Testing)

### Automated Test
```bash
python test_downloads_fixed.py
```

### Manual Test
1. Class Management → View Attendance → Download PDF
2. Result Management → Course Result → Download PDF
3. Routine Management → Generate Routine → Download PDF

## Troubleshooting

### যদি এখনও কাজ না করে:

#### 1. cPanel Error Logs চেক করুন
- cPanel → Logs → Error Logs
- `logs/app_errors.log` এবং `logs/detailed_errors.log` দেখুন

#### 2. Hosting Support কে Contact করুন
নিম্নলিখিত বিষয়গুলি mention করুন:
- PDF/Excel downloads কাজ করছে না
- mod_security rules whitelist করুন
- Download endpoints disable করুন:
  - `/class-management/download*`
  - `/result-management/download*`
  - `/routine-management/download*`

#### 3. Alternative Solutions
- BitNinja/cPGuard এ whitelist করুন
- ModSecurity rules disable করুন
- Python 3.8+ verify করুন

## ফাইল স্ট্রাকচার (File Structure)

```
Academic Management System/
├── blueprints/
│   ├── class_management/
│   │   └── routes.py (modified)
│   └── result_management/
│       └── routes.py (modified)
├── .htaccess (new)
├── test_downloads_fixed.py (new)
├── fix_download_issues_complete.py (new)
└── CPANEL_DOWNLOAD_FIX_README.md (this file)
```

## Technical Details

### পরিবর্তনগুলি:
1. **Flask Response**: `send_file` → `Response`
2. **Headers**: Proper Content-Disposition এবং Content-Length
3. **Server Config**: .htaccess এ download endpoints এর জন্য special rules
4. **Security**: mod_security disable for downloads
5. **Memory**: Increased limits for PDF generation

### Supported Formats:
- PDF (application/pdf)
- Excel (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
- Word (application/vnd.openxmlformats-officedocument.wordprocessingml.document)

## Support

যদি সমস্যা persists:
1. cPanel error logs share করুন
2. Hosting provider এর support team কে contact করুন
3. Alternative hosting provider consider করুন

## Success Indicators

সফল fix এর লক্ষণ:
- ✅ PDF downloads start automatically
- ✅ Excel files open in spreadsheet software
- ✅ No 500 errors in logs
- ✅ Proper file names in downloads
- ✅ Correct file sizes

---

**Last Updated**: 2025-01-05
**Version**: 1.0
**Status**: Ready for deployment 