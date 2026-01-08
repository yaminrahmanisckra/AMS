# MySQL Connection Fix - cPanel Deployment Guide

## সমস্যা
"MySQL server has gone away" error - মাঝে মাঝেই connection timeout হচ্ছে

## সমাধান
Database connection pooling এবং health check যোগ করা হয়েছে

## cPanel-এ Deploy করার ধাপসমূহ

### 1. File Upload (cPanel File Manager)

cPanel-এ যান এবং নিচের files upload করুন:

#### Files to Upload:
1. **`app.py`** - Database connection pooling settings যোগ করা হয়েছে
2. **`extensions.py`** - Connection health check listener যোগ করা হয়েছে

#### Upload Method:
- cPanel → File Manager → `public_html` (বা আপনার app directory)
- Upload করে existing files replace করুন

### 2. File Permissions Check

Ensure these files have correct permissions:
```bash
app.py: 644 or 755
extensions.py: 644 or 755
```

### 3. Restart Application (Important!)

#### Option A: Using Passenger (Recommended)
- cPanel → Applications → আপনার app select করুন
- "Restart" button click করুন

#### Option B: Using Terminal/SSH (if available)
```bash
touch ~/tmp/restart.txt
```

#### Option C: Using .htaccess (if Passenger)
Create or update `.htaccess` file:
```apache
PassengerEnabled On
PassengerAppRoot /home/username/public_html
PassengerBaseURI /
PassengerPython /home/username/virtualenv/public_html/3.9/bin/python
```

Then restart:
```bash
touch ~/tmp/restart.txt
```

### 4. Verify Changes

1. Browser-এ app open করুন
2. Logs check করুন:
   - cPanel → Errors (Error Log)
   - Look for any MySQL connection errors

### 5. Test Application

1. Login করুন
2. Remuneration page open করুন (`/remuneration`)
3. Check করুন error আসছে কিনা
4. কয়েকটি page navigate করুন
5. Database operations test করুন

## কী পরিবর্তন হয়েছে?

### app.py
- `SQLALCHEMY_ENGINE_OPTIONS` যোগ করা হয়েছে:
  - `pool_pre_ping=True`: Connection check করে stale connection auto-reconnect করে
  - `pool_recycle=3600`: 1 hour পর connections recycle করে
  - Connection timeout settings যোগ করা হয়েছে

### extensions.py
- Connection health check listener যোগ করা হয়েছে
- প্রতিবার connection use করার আগে ping করে check করে

## যদি সমস্যা থাকে

### Check Logs:
```bash
# Error logs
tail -f ~/logs/app_errors.log

# Access logs
tail -f ~/logs/access.log
```

### Common Issues:

1. **Permission Error**:
   - Files-এর permission 644 বা 755 করুন

2. **Still Getting Errors**:
   - MySQL server-এর `wait_timeout` check করুন
   - cPanel → MySQL → phpMyAdmin → Variables → `wait_timeout`
   - যদি 3600 এর কম হয়, MySQL admin-কে contact করুন

3. **Import Error**:
   - Ensure `sqlalchemy` package installed
   - SSH-তে check করুন: `pip list | grep SQLAlchemy`

## Additional Notes

- এই changes MySQL connections-কে more reliable করে তোলে
- Connection timeout errors significantly কমে যাবে
- Long-running queries-এর জন্য extra protection আছে

## Support

যদি deploy করার পরও সমস্যা থাকে:
1. Error logs share করুন
2. Browser console errors check করুন
3. MySQL connection status verify করুন



