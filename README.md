# 🎓 Academic Management System

একটি সম্পূর্ণ Academic Management System যা Flask এবং Python দিয়ে তৈরি করা হয়েছে। এই সিস্টেমটি শিক্ষাপ্রতিষ্ঠানের জন্য ক্লাস ম্যানেজমেন্ট, রেজাল্ট ম্যানেজমেন্ট এবং রুটিন ম্যানেজমেন্ট এর সুবিধা প্রদান করে।

## 🚀 Quick Start for cPanel Deployment

If you're experiencing PDF/Excel download issues on cPanel, follow these steps:

### 1. Run the Fix Script
```bash
python fix_cpanel_issues.py
```

### 2. Check Error Logs
- `logs/app_errors.log` - General errors
- `logs/detailed_errors.log` - Detailed error information

### 3. Common Issues & Solutions

#### Internal Server Error (500)
- **Cause**: Missing dependencies or permission issues
- **Solution**: Run `fix_cpanel_issues.py` and check error logs

#### Missing Dependencies
- **Cause**: Python packages not installed
- **Solution**: Install missing packages via cPanel Terminal

#### Memory Issues
- **Cause**: Large PDF generation requires more memory
- **Solution**: Already configured in `.htaccess` (512M limit)

For detailed troubleshooting, see [CPANEL_DEPLOYMENT_GUIDE.md](CPANEL_DEPLOYMENT_GUIDE.md)

## ✨ ফিচারগুলি

### 🔐 ইউজার ম্যানেজমেন্ট
- **অ্যাডমিন প্যানেল** - সম্পূর্ণ সিস্টেম কন্ট্রোল
- **ইউজার অথেনটিকেশন** - সুরক্ষিত লগইন সিস্টেম
- **রোল-বেসড অ্যাক্সেস** - অ্যাডমিন এবং সাধারণ ইউজার
- **পাসওয়ার্ড রিসেট** - ইমেইল ভিত্তিক পাসওয়ার্ড রিকভারি

### 📚 ক্লাস ম্যানেজমেন্ট
- **স্টুডেন্ট রেজিস্ট্রেশন** - নতুন স্টুডেন্ট যোগ করা
- **অ্যাটেনডেন্স ট্র্যাকিং** - দৈনিক উপস্থিতি রেকর্ড
- **অ্যাসেসমেন্ট ম্যানেজমেন্ট** - পরীক্ষার ফলাফল ট্র্যাক
- **আর্কাইভ সিস্টেম** - পুরানো ডেটা সংরক্ষণ

### 📊 রেজাল্ট ম্যানেজমেন্ট
- **সেশন ম্যানেজমেন্ট** - একাডেমিক সেশন তৈরি
- **সাবজেক্ট ম্যানেজমেন্ট** - কোর্স এবং বিষয় যোগ করা
- **মার্কস এন্ট্রি** - পরীক্ষার ফলাফল ইনপুট
- **রেজাল্ট ভিউ** - স্টুডেন্ট এবং কোর্স-ওয়াইজ ফলাফল
- **রেজাল্ট আর্কাইভ** - পুরানো ফলাফল সংরক্ষণ

### 📅 রুটিন ম্যানেজমেন্ট
- **টিচার ম্যানেজমেন্ট** - শিক্ষকদের তথ্য
- **রুম ম্যানেজমেন্ট** - ক্লাসরুম অ্যাসাইনমেন্ট
- **কোর্স অ্যাসাইনমেন্ট** - শিক্ষক-কোর্স ম্যাপিং
- **রুটিন জেনারেশন** - অটোমেটিক রুটিন তৈরি

## 🚀 Render-এ ডিপ্লয়মেন্ট

### ১. Render Dashboard-এ যান
- [render.com](https://render.com) এ লগইন করুন
- "New +" বাটনে ক্লিক করুন
- "Web Service" সিলেক্ট করুন

### ২. GitHub Repository কানেক্ট করুন
- "Connect a repository" সেকশনে আপনার GitHub repository সিলেক্ট করুন
- Repository: `yaminrahmanisckra/AMS`

### ৩. কনফিগারেশন সেট করুন
- **Name**: `academic-management-system` (বা আপনার পছন্দের নাম)
- **Environment**: `Docker`
- **Region**: আপনার নিকটবর্তী region
- **Branch**: `main`

### ৪. Environment Variables সেট করুন
Render Dashboard > Environment > Environment Variables-এ নিচের ভ্যারিয়েবলগুলো যোগ করুন:

```env
SECRET_KEY=your_very_secret_key_here
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
RENDER=True
```

### ৫. ডাটাবেস সেটআপ (ঐচ্ছিক)
- Render Dashboard-এ "New +" > "PostgreSQL"
- নতুন ডাটাবেস তৈরি করুন
- Internal Database URL কপি করে Environment Variables-এ `DATABASE_URL` হিসেবে যোগ করুন

### ৬. ডিপ্লয় করুন
- "Create Web Service" বাটনে ক্লিক করুন
- Render অটোমেটিকভাবে আপনার অ্যাপ ডিপ্লয় করবে

## 📁 প্রজেক্ট স্ট্রাকচার

```
academic-management-system/
├── app.py                          # মূল Flask অ্যাপ্লিকেশন
├── models.py                       # ডাটাবেস মডেল
├── user_models.py                  # ইউজার মডেল
├── extensions.py                   # Flask এক্সটেনশন
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker configuration
├── create_admin.py                # অ্যাডমিন ইউজার স্ক্রিপ্ট
├── blueprints/                    # Flask blueprints
│   ├── auth/                      # অথেনটিকেশন
│   ├── class_management/          # ক্লাস ম্যানেজমেন্ট
│   ├── result_management/         # রেজাল্ট ম্যানেজমেন্ট
│   └── routine_management/        # রুটিন ম্যানেজমেন্ট
├── templates/                     # HTML templates
├── static/                        # CSS, JS, Images
├── migrations/                    # Database migrations
├── instance/                      # Instance-specific files
└── uploads/                       # Uploaded files
```

## 🔧 স্থানীয় ডেভেলপমেন্ট

### ১. Repository ক্লোন করুন
```bash
git clone https://github.com/yaminrahmanisckra/AMS.git
cd AMS
```

### ২. Virtual Environment তৈরি করুন
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# অথবা
venv\Scripts\activate  # Windows
```

### ৩. Dependencies ইনস্টল করুন
```bash
pip install -r requirements.txt
```

### ৪. Environment Variables সেট করুন
```bash
# .env ফাইল তৈরি করুন
SECRET_KEY=your_secret_key_here
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your_email@gmail.com
```

### ৫. ডাটাবেস ইনিশিয়ালাইজ করুন
```bash
flask db upgrade
```

### ৬. অ্যাডমিন ইউজার তৈরি করুন
```bash
python create_admin.py
```

### ৭. অ্যাপ্লিকেশন চালু করুন
```bash
python app.py
```

## 🔒 সিকিউরিটি

- **Password Hashing** - bcrypt ব্যবহার
- **Session Management** - Flask-Login
- **CSRF Protection** - Flask-WTF
- **Input Validation** - Form validation
- **SQL Injection Protection** - SQLAlchemy ORM
- **Email Verification** - SMTP integration

## 📈 পারফরম্যান্স

- **Database Optimization** - Indexed queries
- **Static File Caching** - Browser caching
- **Template Caching** - Jinja2 optimization
- **Database Connection Pooling** - Production ready
- **Gunicorn WSGI Server** - High performance

## 🤝 কন্ট্রিবিউশন

1. **Fork করুন** এই repository
2. **Feature branch** তৈরি করুন (`git checkout -b feature/AmazingFeature`)
3. **Commit করুন** আপনার changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push করুন** branch এ (`git push origin feature/AmazingFeature`)
5. **Pull Request** তৈরি করুন

## 📝 লাইসেন্স

এই প্রজেক্টটি MIT লাইসেন্সের অধীনে প্রকাশিত হয়েছে। বিস্তারিত জানতে `LICENSE` ফাইল দেখুন।

## 📞 সাপোর্ট

কোনো সমস্যা বা প্রশ্ন থাকলে GitHub Issues-এ জানাবেন।