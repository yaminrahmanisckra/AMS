# 🚀 GitHub থেকে Cpanel এ অটোমেটিক ডিপ্লয়

## 📋 প্রয়োজনীয়তা
- GitHub অ্যাকাউন্ট
- Cpanel হোস্টিং (SSH access সহ)
- Python 3.8+ support

## 🔧 ধাপ ১: GitHub Repository সেটআপ

### ১.১. GitHub এ প্রজেক্ট আপলোড করুন
```bash
# আপনার প্রজেক্ট ফোল্ডারে
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/academic-management-system.git
git push -u origin main
```

### ১.২. GitHub Secrets সেট করুন
1. আপনার GitHub repository তে যান
2. Settings → Secrets and variables → Actions
3. "New repository secret" ক্লিক করুন
4. নিম্নলিখিত secrets যোগ করুন:

```
CPANEL_HOST=your-cpanel-server.com
CPANEL_USERNAME=your-cpanel-username
CPANEL_PASSWORD=your-cpanel-password
CPANEL_PORT=22
```

## 🔧 ধাপ ২: Cpanel এ SSH Access সেটআপ

### ২.১. SSH Access এনাবল করুন
1. Cpanel → Security → SSH Access
2. "Enable SSH" ক্লিক করুন
3. SSH key generate করুন অথবা password ব্যবহার করুন

### ২.২. Python App সেটআপ করুন
1. Cpanel → Software → Setup Python App
2. নিম্নলিখিত তথ্য দিন:
   - **Python version**: 3.8+
   - **Application startup file**: `passenger_wsgi.py`
   - **Application entry point**: `application`
   - **Application URL**: আপনার ডোমেইন

## 🔧 ধাপ ৩: ডাটাবেস সেটআপ

### ৩.১. MySQL ডাটাবেস তৈরি করুন
1. Cpanel → MySQL Databases
2. একটি নতুন ডাটাবেস তৈরি করুন
3. একটি নতুন ইউজার তৈরি করুন
4. ইউজারকে ডাটাবেসে অ্যাসাইন করুন

### ৩.২. Environment Variables সেট করুন
1. Cpanel → Software → Environment Variables
2. নিম্নলিখিত ভ্যারিয়েবলগুলি যোগ করুন:
```
CPANEL=1
SECRET_KEY=your_secret_key_here
DATABASE_URL=mysql://username:password@localhost/database_name
```

## 🚀 ধাপ ৪: অটোমেটিক ডিপ্লয়

### ৪.১. GitHub Actions Workflow
আপনার প্রজেক্টে `.github/workflows/deploy-cpanel.yml` ফাইলটি আছে। এটি অটোমেটিকভাবে:

1. **Code চেকআউট** করে
2. **Dependencies ইনস্টল** করে
3. **Deployment package** তৈরি করে
4. **Cpanel এ ফাইল আপলোড** করে
5. **Dependencies ইনস্টল** করে
6. **File permissions** সেট করে

### ৪.২. ডিপ্লয় ট্রিগার
- **Automatic**: `main` বা `master` branch এ push করলে
- **Manual**: GitHub Actions → Deploy to cPanel → Run workflow

## 📝 ধাপ ৫: প্রথম ডিপ্লয়

### ৫.১. GitHub এ Push করুন
```bash
git add .
git commit -m "Setup GitHub Actions deployment"
git push origin main
```

### ৫.২. GitHub Actions চেক করুন
1. GitHub repository তে যান
2. Actions ট্যাব ক্লিক করুন
3. "Deploy to cPanel" workflow দেখুন
4. Status চেক করুন

### ৫.৩. Cpanel এ চেক করুন
1. File Manager খুলুন
2. `public_html` ফোল্ডারে যান
3. ফাইলগুলি আপলোড হয়েছে কিনা দেখুন

## 🔧 ধাপ ৬: অ্যাডমিন ইউজার তৈরি

### ৬.১. SSH এর মাধ্যমে
```bash
ssh username@your-cpanel-server.com
cd public_html
python3 create_admin.py
```

### ৬.২. Cpanel Terminal এর মাধ্যমে
1. Cpanel → Terminal
2. নিম্নলিখিত কমান্ডগুলি রান করুন:
```bash
cd public_html
python3 create_admin.py
```

## 🔧 ধাপ ৭: অ্যাপ্লিকেশন রিস্টার্ট

### ৭.১. Manual Restart
1. Cpanel → Software → Setup Python App
2. আপনার অ্যাপ্লিকেশন খুঁজুন
3. "Restart" বাটন ক্লিক করুন

### ৭.২. Automatic Restart (Optional)
আপনি cPanel API ব্যবহার করে automatic restart করতে পারেন।

## 🔍 ট্রাবলশুটিং

### যদি GitHub Actions Fail হয়:
1. **Secrets সঠিক কিনা** চেক করুন
2. **SSH access** এনাবল আছে কিনা দেখুন
3. **Cpanel credentials** সঠিক কিনা চেক করুন

### যদি অ্যাপ্লিকেশন লোড না হয়:
1. **Error logs** চেক করুন
2. **File permissions** সঠিক কিনা দেখুন
3. **Environment variables** সেট আছে কিনা চেক করুন

### যদি ডাটাবেস এরর হয়:
1. **MySQL credentials** সঠিক কিনা চেক করুন
2. **Database exists** কিনা দেখুন
3. **User permissions** সঠিক কিনা চেক করুন

## 📊 GitHub Actions Workflow Details

### Workflow Steps:
1. **Checkout code** - GitHub থেকে কোড ডাউনলোড
2. **Setup Python** - Python environment সেটআপ
3. **Install dependencies** - Local dependencies ইনস্টল
4. **Create deployment package** - Cpanel এর জন্য ফাইল প্রস্তুত
5. **Deploy to cPanel** - SCP এর মাধ্যমে ফাইল আপলোড
6. **Install dependencies on cPanel** - Server এ dependencies ইনস্টল
7. **Set file permissions** - সঠিক file permissions সেট
8. **Restart Python App** - অ্যাপ্লিকেশন রিস্টার্ট

### Benefits:
- ✅ **Automatic deployment** - Code push করলেই ডিপ্লয়
- ✅ **Version control** - সব changes track করা যায়
- ✅ **Rollback** - আগের version এ ফিরে যাওয়া যায়
- ✅ **Collaboration** - Team members একসাথে কাজ করতে পারে
- ✅ **Backup** - GitHub এ সব code backup থাকে

## 🎯 পরবর্তী ধাপগুলি

### Development Workflow:
1. **Local development** - আপনার কম্পিউটারে কাজ করুন
2. **Test locally** - সব ঠিক আছে কিনা চেক করুন
3. **Commit & Push** - GitHub এ আপলোড করুন
4. **Automatic deployment** - GitHub Actions অটোমেটিক ডিপ্লয় করবে
5. **Test live** - Live site এ চেক করুন

### Best Practices:
- ✅ **Small commits** - ছোট ছোট changes commit করুন
- ✅ **Meaningful commit messages** - স্পষ্ট commit messages লিখুন
- ✅ **Test before push** - Push করার আগে test করুন
- ✅ **Monitor deployments** - GitHub Actions monitor করুন
- ✅ **Keep secrets secure** - GitHub secrets সুরক্ষিত রাখুন

## 🚀 সফল ডিপ্লয়ের পর

আপনার Academic Management System এখন GitHub থেকে অটোমেটিকভাবে Cpanel এ ডিপ্লয় হবে! 

**ফিচারগুলি:**
- ✅ **Automatic deployment** - Code push করলেই ডিপ্লয়
- ✅ **Version control** - সব changes track করা যায়
- ✅ **Easy rollback** - সমস্যা হলে আগের version এ ফিরে যাওয়া যায়
- ✅ **Team collaboration** - একাধিক developer একসাথে কাজ করতে পারে
- ✅ **Secure deployment** - GitHub secrets ব্যবহার করে secure

**আপনার workflow:**
1. Code edit করুন
2. `git add . && git commit -m "message" && git push`
3. GitHub Actions অটোমেটিক ডিপ্লয় করবে
4. Live site এ changes দেখুন

🎉 আপনার Academic Management System এখন GitHub-powered! 🚀 