# cPanel Deployment Checklist

## ✅ Pre-Deployment
- [ ] Backup your current project
- [ ] Test application locally
- [ ] Ensure all dependencies are in requirements_cpanel.txt

## ✅ cPanel Setup
- [ ] Login to cPanel
- [ ] Go to "Setup Python App"
- [ ] Create new Python application
- [ ] Set Python version to 3.8+
- [ ] Set application root to your project folder
- [ ] Set application URL to your domain

## ✅ File Upload
- [ ] Upload all project files to public_html
- [ ] Exclude venv/, __pycache__/, .git/ folders
- [ ] Ensure passenger_wsgi.py is in root directory
- [ ] Ensure .htaccess is in root directory

## ✅ Database Setup
- [ ] Create MySQL/PostgreSQL database in cPanel
- [ ] Create database user with full privileges
- [ ] Note down database credentials

## ✅ Environment Configuration
- [ ] Create .env file with:
  - SECRET_KEY (random string)
  - DATABASE_URL (your database connection string)
  - CPANEL=1
  - FLASK_ENV=production

## ✅ Dependencies Installation
- [ ] Access Terminal/SSH in cPanel
- [ ] Navigate to project directory
- [ ] Run: `python3 -m venv venv`
- [ ] Run: `source venv/bin/activate`
- [ ] Run: `pip install -r requirements_cpanel.txt`

## ✅ Database Initialization
- [ ] Run: `python -c "from app import app, db; app.app_context().push(); db.create_all()"`
- [ ] Run: `python create_admin.py` (creates admin user)

## ✅ File Permissions
- [ ] Set instance/ directory to 755
- [ ] Set uploads/ directory to 755
- [ ] Set all .py files to 644
- [ ] Set .htaccess to 644

## ✅ Final Steps
- [ ] Restart Python app in cPanel
- [ ] Test application at your domain
- [ ] Login with admin credentials
- [ ] Test all major features

## ✅ Post-Deployment
- [ ] Change default admin password
- [ ] Set up SSL certificate
- [ ] Configure backups
- [ ] Monitor error logs

## 🔧 Troubleshooting Commands
```bash
# Check Python version
python3 --version

# Check installed packages
pip list

# Check application logs
tail -f error_log

# Test database connection
python -c "from app import app, db; print('Database OK')"

# Restart application
# Go to cPanel → Setup Python App → Restart
```

## 📞 Support
- cPanel Error Logs: cPanel → Error Logs
- Python App Logs: cPanel → Setup Python App → Logs
- File Permissions: cPanel → File Manager → Right-click → Change Permissions 