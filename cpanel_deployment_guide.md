# Cpanel এ Academic Management System ডিপ্লয় করার গাইড

## প্রয়োজনীয় ফাইলগুলি
আপনার প্রজেক্টে নিম্নলিখিত ফাইলগুলি থাকতে হবে:
- `passenger_wsgi.py` (মূল ফাইল)
- `requirements_cpanel.txt` (প্যাকেজ লিস্ট)
- `app.py` (আপনার Flask অ্যাপ্লিকেশন)

## ধাপ ১: Cpanel এ লগইন করুন
1. আপনার Cpanel অ্যাকাউন্টে লগইন করুন
2. "Software" সেকশনে যান
3. "Setup Python App" ক্লিক করুন

## ধাপ ২: Python অ্যাপ্লিকেশন সেটআপ করুন
1. **App root**: আপনার ডোমেইন/সাবডোমেইন সিলেক্ট করুন (যেমন: `yourdomain.com` বা `app.yourdomain.com`)
2. **Python version**: Python 3.8 বা তার উপরে সিলেক্ট করুন
3. **Application startup file**: `passenger_wsgi.py` লিখুন
4. **Application Entry point**: `application` লিখুন
5. **Application URL**: আপনার ডোমেইন URL দিন
6. **Passenger log file**: খালি রাখুন (অপশনাল)

## ধাপ ৩: ফাইল আপলোড করুন
1. Cpanel এর File Manager খুলুন
2. আপনার ডোমেইনের রুট ডিরেক্টরিতে যান
3. নিম্নলিখিত ফাইলগুলি আপলোড করুন:
   - `app.py`
   - `passenger_wsgi.py`
   - `requirements_cpanel.txt`
   - `models.py`
   - `user_models.py`
   - `extensions.py`
   - `blueprints/` ফোল্ডার (সম্পূর্ণ)
   - `templates/` ফোল্ডার (সম্পূর্ণ)
   - `static/` ফোল্ডার (সম্পূর্ণ)
   - `migrations/` ফোল্ডার (সম্পূর্ণ)

## ধাপ ৪: ডিপেন্ডেন্সি ইনস্টল করুন
1. "Software" সেকশনে "Terminal" খুলুন
2. নিম্নলিখিত কমান্ডগুলি রান করুন:
```bash
cd /home/username/public_html
pip3 install -r requirements_cpanel.txt
```

## ধাপ ৫: ডাটাবেস সেটআপ করুন
1. Cpanel এর "MySQL Databases" সেকশনে যান
2. একটি নতুন ডাটাবেস তৈরি করুন
3. একটি নতুন ইউজার তৈরি করুন এবং ডাটাবেসে অ্যাসাইন করুন
4. আপনার `app.py` ফাইলে DATABASE_URL এনভায়রনমেন্ট ভ্যারিয়েবল সেট করুন

## ধাপ ৬: এনভায়রনমেন্ট ভ্যারিয়েবল সেট করুন
1. "Software" সেকশনে "Environment Variables" খুলুন
2. নিম্নলিখিত ভ্যারিয়েবলগুলি যোগ করুন:
   - `CPANEL=1`
   - `SECRET_KEY=your_secret_key_here`
   - `DATABASE_URL=mysql://username:password@localhost/database_name`

## ধাপ ৭: অ্যাপ্লিকেশন রিস্টার্ট করুন
1. "Software" সেকশনে "Setup Python App" এ যান
2. আপনার অ্যাপ্লিকেশন খুঁজুন
3. "Restart" বাটন ক্লিক করুন

## সমস্যা সমাধান

### যদি অ্যাপ্লিকেশন লোড না হয়:
1. Error logs চেক করুন
2. `passenger_wsgi.py` ফাইলের পারমিশন 644 করুন
3. সব ফাইলের পারমিশন সঠিক কিনা চেক করুন

### যদি ডাটাবেস কানেকশন এরর হয়:
1. MySQL credentials সঠিক কিনা চেক করুন
2. ডাটাবেস ইউজারকে সঠিক পারমিশন দেওয়া আছে কিনা দেখুন

### যদি স্ট্যাটিক ফাইল লোড না হয়:
1. `static/` ফোল্ডারের পারমিশন 755 করুন
2. CSS/JS ফাইলগুলির পারমিশন 644 করুন

## গুরুত্বপূর্ণ নোট
- প্রথমবার অ্যাপ্লিকেশন চালু করার সময় ডাটাবেস টেবিলগুলি অটোমেটিক তৈরি হবে
- অ্যাডমিন ইউজার তৈরি করতে `create_admin.py` স্ক্রিপ্ট ব্যবহার করুন
- নিয়মিত ব্যাকআপ নিন
- সিকিউরিটি আপডেট রাখুন 