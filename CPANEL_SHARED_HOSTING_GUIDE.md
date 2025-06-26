# 🚀 Shared Hosting cPanel ডিপ্লয়মেন্ট গাইড
## GitHub Actions এর মাধ্যমে SSH/Terminal ছাড়াই ডিপ্লয়

### 📋 প্রাথমিক প্রয়োজনীয়তা

1. **cPanel অ্যাক্সেস** - আপনার shared hosting এর cPanel
2. **Python 3.9.22** - আপনার cPanel এ available
3. **GitHub Repository** - কোড push করার জন্য
4. **cPanel API Access** - GitHub Actions এর জন্য

### 🔧 GitHub Repository Setup

#### 1. GitHub Secrets সেটআপ

আপনার GitHub repository তে গিয়ে **Settings → Secrets and variables → Actions** এ নিচের secrets যোগ করুন:

```
CPANEL_HOST = your-domain.com
CPANEL_USERNAME = your-cpanel-username
CPANEL_PASSWORD = your-cpanel-password
CPANEL_PORT = 2083
```

#### 2. Repository তে কোড Push করুন

```bash
git add .
git commit -m "Add cPanel shared hosting deployment"
git push origin main
```

### 🎯 cPanel এ Manual Setup

#### 1. Python App সেটআপ

1. **cPanel → Software → Setup Python App** এ যান
2. **Create Application** ক্লিক করুন
3. নিচের তথ্য দিন:
   - **Python version**: 3.9.22
   - **Application startup file**: `passenger_wsgi.py`
   - **Application entry point**: `application`
   - **Application URL**: আপনার domain
   - **Application root**: `/public_html`

#### 2. Dependencies ইনস্টল

1. **cPanel → Terminal** এ যান
2. নিচের কমান্ড রান করুন:

```bash
cd public_html
pip3 install -r requirements_cpanel.txt
```

#### 3. Environment Variables সেটআপ

1. **cPanel → Software → Environment Variables** এ যান
2. নিচের variables যোগ করুন:

```
CPANEL=1
SECRET_KEY=your-secret-key-here
DATABASE_URL=mysql://username:password@localhost/database_name
FLASK_ENV=production
```

#### 4. Database সেটআপ

**MySQL Database তৈরি:**

1. **cPanel → Databases → MySQL Databases** এ যান
2. নতুন database তৈরি করুন
3. নতুন user তৈরি করুন
4. User কে database এ assign করুন
5. **phpMyAdmin** এ গিয়ে tables তৈরি করুন

**Database Tables তৈরি:**

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add more tables as needed for your application
```

#### 5. Admin User তৈরি

1. **cPanel → Terminal** এ যান
2. নিচের কমান্ড রান করুন:

```bash
cd public_html
python3 create_admin.py
```

### 🔄 GitHub Actions Workflow

আপনার repository তে `.github/workflows/deploy-cpanel-shared.yml` ফাইল থাকবে যা:

1. **Code Package** তৈরি করে
2. **ZIP file** তৈরি করে
3. **cPanel API** এর মাধ্যমে upload করে
4. **File permissions** set করে
5. **Deployment instructions** তৈরি করে

### 📁 File Structure

```
public_html/
├── app.py                 # Main Flask application
├── passenger_wsgi.py      # cPanel WSGI entry point
├── requirements_cpanel.txt # Python dependencies
├── .htaccess             # Apache configuration
├── models.py             # Database models
├── user_models.py        # User models
├── extensions.py         # Flask extensions
├── create_admin.py       # Admin creation script
├── blueprints/           # Flask blueprints
├── templates/            # HTML templates
├── static/               # CSS, JS, images
├── migrations/           # Database migrations
├── instance/             # Instance folder
└── uploads/              # File uploads
```

### 🛠️ Troubleshooting

#### সাধারণ সমস্যা ও সমাধান:

1. **500 Internal Server Error**
   - Check error logs in cPanel → Errors
   - Verify file permissions (644 for files, 755 for directories)
   - Check Python app configuration

2. **Module Not Found Error**
   - Run `pip3 install -r requirements_cpanel.txt` again
   - Check if all packages are installed: `pip3 list`

3. **Database Connection Error**
   - Verify DATABASE_URL in environment variables
   - Check database credentials
   - Ensure database exists and user has permissions

4. **Static Files Not Loading**
   - Check .htaccess file
   - Verify static folder permissions
   - Clear browser cache

#### Error Logs চেক করা:

1. **cPanel → Errors** এ যান
2. **Error Log** ক্লিক করুন
3. **Latest Error** দেখুন

### 🔒 Security Considerations

1. **Environment Variables** - Sensitive data environment variables এ রাখুন
2. **File Permissions** - Sensitive files (py, env, db) কে protect করুন
3. **HTTPS** - SSL certificate enable করুন
4. **Regular Updates** - Dependencies regularly update করুন

### 📞 Support

যদি কোন সমস্যা হয়:

1. **cPanel Error Logs** চেক করুন
2. **GitHub Actions Logs** দেখুন
3. **File Permissions** verify করুন
4. **Database Connection** test করুন

### 🎉 Success!

আপনার application এখন live হবে:
**https://your-domain.com**

### 📝 Notes

- **Python 3.9.22** compatible packages ব্যবহার করা হয়েছে
- **Shared hosting** limitations মাথায় রেখে configuration করা হয়েছে
- **Security best practices** follow করা হয়েছে
- **Performance optimization** করা হয়েছে

---

**Happy Deployment! 🚀** 