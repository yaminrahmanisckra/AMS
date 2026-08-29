# cPanel Deployment Guide for Academic Management System

## Overview
This guide helps you deploy the Academic Management System on cPanel and troubleshoot PDF/Excel download issues.

## Prerequisites
- cPanel hosting with Python support
- Python 3.7+ enabled
- Access to cPanel File Manager and Terminal

## Deployment Steps

### 1. Upload Files
1. Upload all project files to your cPanel `public_html` directory
2. Ensure the following files are in the root directory:
   - `app.py`
   - `passenger_wsgi.py`
   - `.htaccess`
   - `requirements.txt`
   - `error_handler.py`

### 2. Install Dependencies
1. Open cPanel Terminal
2. Navigate to your project directory:
   ```bash
   cd public_html
   ```
3. Create a virtual environment (if supported):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Configure Database
1. Create a MySQL database in cPanel
2. Set up environment variables in `.env` file:
   ```
   DATABASE_URL=mysql://username:password@localhost/database_name
   SECRET_KEY=your_secret_key_here
   CPANEL=1
   ```

### 4. Initialize Database
1. Run database migrations:
   ```bash
   python app.py
   ```
2. Create admin user using `create_admin.py`

## Troubleshooting PDF/Excel Download Issues

### Common Issues and Solutions

#### 1. Internal Server Error (500)
**Symptoms**: PDF/Excel downloads show "Internal Server Error"

**Diagnosis Steps**:
1. Review error logs in `logs/app_errors.log`
2. Check `logs/detailed_errors.log` for specific error details
3. Check cPanel error logs (cPanel → Logs)

**Common Causes**:
- Missing Python dependencies
- File permission issues
- Memory limitations
- Database connection problems

#### 2. Missing Dependencies
**Solution**:
1. Check if all required packages are installed:
   ```bash
   pip list | grep -E "(pandas|openpyxl|reportlab|python-docx|Pillow)"
   ```
2. Install missing packages:
   ```bash
   pip install pandas openpyxl reportlab python-docx Pillow
   ```

#### 3. File Permission Issues
**Solution**:
1. Set proper permissions:
   ```bash
   chmod 755 public_html
   chmod 644 *.py
   chmod 755 logs
   chmod 755 uploads
   chmod 755 instance
   ```

#### 4. Memory Limitations
**Symptoms**: Large PDF generation fails

**Solutions**:
1. Increase PHP memory limit in `.htaccess`:
   ```apache
   php_value memory_limit 512M
   ```
2. Optimize PDF generation for smaller files
3. Use streaming for large files

#### 5. Database Connection Issues
**Symptoms**: "Database connection failed" errors

**Solutions**:
1. Verify database credentials in `.env`
2. Check database server status
3. Ensure database user has proper permissions

### Debugging Tools

#### Error Logs
Check these log files:
- `logs/app_errors.log` - General application errors
- `logs/detailed_errors.log` - Detailed error information
- cPanel error logs (in cPanel > Logs)

#### Manual Testing
Test each component separately:
1. **Class Management PDF**: Try downloading attendance PDF
2. **Class Management Excel**: Try downloading attendance Excel
3. **Result Management PDF**: Try downloading course/student results
4. **Result Management Excel**: Try downloading assessment Excel

### Specific Error Solutions

#### ImportError: No module named 'pandas'
```bash
pip install pandas
```

#### ImportError: No module named 'openpyxl'
```bash
pip install openpyxl
```

#### ImportError: No module named 'reportlab'
```bash
pip install reportlab
```

#### Permission Denied Errors
```bash
chmod -R 755 public_html
chmod 644 *.py
```

#### Memory Exhausted Errors
1. Add to `.htaccess`:
   ```apache
   php_value memory_limit 512M
   php_value max_execution_time 300
   ```
2. Optimize PDF generation code

### Performance Optimization

#### 1. Enable Caching
Add to `.htaccess`:
```apache
<IfModule mod_expires.c>
    ExpiresActive On
    ExpiresByType text/css "access plus 1 year"
    ExpiresByType application/javascript "access plus 1 year"
    ExpiresByType image/png "access plus 1 year"
    ExpiresByType image/jpg "access plus 1 year"
</IfModule>
```

#### 2. Compress Files
Add to `.htaccess`:
```apache
<IfModule mod_deflate.c>
    AddOutputFilterByType DEFLATE text/plain
    AddOutputFilterByType DEFLATE text/html
    AddOutputFilterByType DEFLATE text/xml
    AddOutputFilterByType DEFLATE text/css
    AddOutputFilterByType DEFLATE application/xml
    AddOutputFilterByType DEFLATE application/xhtml+xml
    AddOutputFilterByType DEFLATE application/rss+xml
    AddOutputFilterByType DEFLATE application/javascript
    AddOutputFilterByType DEFLATE application/x-javascript
</IfModule>
```

### Security Considerations

#### 1. Protect Sensitive Files
Ensure `.htaccess` blocks access to:
- `.env` files
- Database files
- Log files
- Python cache files

#### 2. Use HTTPS
Enable SSL certificate in cPanel for secure connections

#### 3. Regular Updates
Keep dependencies updated:
```bash
pip install --upgrade -r requirements.txt
```

## Support

If you continue to experience issues:

1. **Check Error Logs**: Review `logs/detailed_errors.log`
2. **Contact Hosting Provider**: Some issues may be hosting-specific
3. **Check cPanel Logs**: Review cPanel error logs

## File Structure After Deployment
```
public_html/
├── app.py
├── passenger_wsgi.py
├── .htaccess
├── requirements.txt
├── error_handler.py
├── .env
├── logs/
│   ├── app_errors.log
│   └── detailed_errors.log
├── uploads/
├── instance/
├── static/
├── templates/
└── blueprints/
```

## Testing Checklist
- [ ] Application loads without errors
- [ ] User authentication works
- [ ] Database operations work
- [ ] Class Management PDF download works
- [ ] Class Management Excel download works
- [ ] Result Management PDF download works
- [ ] Result Management Excel download works
- [ ] Routine Management PDF download works
- [ ] Debug endpoint shows all dependencies available
- [ ] Error logs are being created 