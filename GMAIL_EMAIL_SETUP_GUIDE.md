# Gmail Email Setup Guide for cPanel

## 📧 **Gmail SMTP Configuration for Forgot Password**

### **Step 1: Gmail Account Setup**

#### **1.1 Enable 2-Step Verification**
1. **Gmail এ যান:** https://myaccount.google.com/
2. **Security এ ক্লিক করুন**
3. **2-Step Verification enable করুন**
4. **Phone number verify করুন**

#### **1.2 Generate App Password**
1. **App passwords এ যান:** https://myaccount.google.com/apppasswords
2. **"Select app" dropdown থেকে "Other (Custom name)" বেছে নিন**
3. **Name দিন:** `Academic Management System`
4. **Generate বাটনে ক্লিক করুন**
5. **16-character password কপি করে রাখুন** (যেমন: `abcd efgh ijkl mnop`)

### **Step 2: Environment Configuration**

#### **2.1 .env ফাইল তৈরি করুন**
```bash
# .env file
SECRET_KEY=your-secret-key-here
FLASK_ENV=production

# Database Configuration
DATABASE_URL=sqlite:///academic_management.db

# Email Configuration (Gmail SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-character-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Environment Variables
CPANEL=1
RENDER=0
```

#### **2.2 cPanel Environment Variables**
cPanel এ Python app এর environment variables set করুন:

1. **cPanel এ যান**
2. **Python Apps এ ক্লিক করুন**
3. **আপনার app এ ক্লিক করুন**
4. **Environment Variables এ যান**
5. **নিচের variables যোগ করুন:**

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-character-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

### **Step 3: Dependencies Installation**

#### **3.1 requirements.txt আপডেট**
```bash
# requirements.txt এ যোগ করুন:
Flask-Mail==0.9.1
```

#### **3.2 cPanel এ Install**
```bash
# cPanel Terminal এ:
pip3 install Flask-Mail==0.9.1
```

### **Step 4: Test Email Configuration**

#### **4.1 Test Script চালান**
```bash
python3 test_email_config.py
```

#### **4.2 Expected Output**
```
✅ EMAIL CONFIGURATION SUCCESSFUL!
Your Gmail SMTP is working correctly.
Forgot password emails will now work properly.
```

### **Step 5: Forgot Password Testing**

#### **5.1 Test Forgot Password**
1. **Login page এ যান**
2. **"Forgot Password?" লিংক ক্লিক করুন**
3. **Email address দিন**
4. **Submit করুন**
5. **Gmail inbox চেক করুন**

#### **5.2 Expected Email**
```
Subject: Password Reset Request - Academic Management System

Hello,

You have requested to reset your password for the Academic Management System.

Click the link below to reset your password:
[Reset Password Button]

Or copy and paste this URL in your browser:
https://yourdomain.com/reset-password/token

This link will expire in 1 hour.

Best regards,
Academic Management System Team
```

## 🔧 **Troubleshooting**

### **Common Issues:**

#### **1. "Authentication failed" Error**
**সমাধান:**
- Gmail App Password সঠিক কিনা চেক করুন
- 2-Step Verification enabled কিনা দেখুন
- Regular Gmail password ব্যবহার করবেন না

#### **2. "Connection refused" Error**
**সমাধান:**
- SMTP settings সঠিক কিনা চেক করুন:
  - Server: `smtp.gmail.com`
  - Port: `587`
  - TLS: `True`

#### **3. "Username and Password not accepted"**
**সমাধান:**
- Gmail App Password regenerate করুন
- Username সঠিক কিনা চেক করুন
- .env file এ spaces নেই কিনা দেখুন

#### **4. cPanel এ Email কাজ করছে না**
**সমাধান:**
- cPanel Python app restart করুন
- Environment variables সঠিকভাবে set করা আছে কিনা দেখুন
- Error logs চেক করুন

### **Security Best Practices:**

1. **App Password Secure রাখুন**
   - কাউকে share করবেন না
   - .env file public repository এ push করবেন না

2. **Regular Password ব্যবহার করবেন না**
   - শুধু App Password ব্যবহার করুন
   - Regular password security risk

3. **App Passwords Revoke করুন**
   - যদি compromise হয়
   - Gmail Security settings থেকে revoke করুন

## 📋 **Complete Setup Checklist**

### **✅ Gmail Setup:**
- [ ] 2-Step Verification enabled
- [ ] App Password generated
- [ ] App Password saved securely

### **✅ Environment Configuration:**
- [ ] .env file created
- [ ] Email variables set
- [ ] cPanel environment variables configured

### **✅ Dependencies:**
- [ ] Flask-Mail installed
- [ ] requirements.txt updated

### **✅ Testing:**
- [ ] Email configuration test passed
- [ ] Test email received
- [ ] Forgot password functionality tested

### **✅ Security:**
- [ ] App Password secured
- [ ] .env file not in public repo
- [ ] Regular password not used

## 🚀 **Deployment Steps**

### **1. Local Testing:**
```bash
# 1. .env file তৈরি করুন
# 2. Test script চালান
python3 test_email_config.py
# 3. Forgot password test করুন
```

### **2. cPanel Deployment:**
```bash
# 1. ফাইল আপলোড করুন
# 2. Environment variables set করুন
# 3. Python app restart করুন
# 4. Test করুন
```

### **3. Verification:**
```bash
# 1. Forgot password page এ যান
# 2. Email submit করুন
# 3. Gmail inbox চেক করুন
# 4. Reset link test করুন
```

## 📞 **Support**

### **যদি সমস্যা থাকে:**

1. **Gmail Support:**
   - https://support.google.com/mail/
   - App Password issues

2. **cPanel Support:**
   - Hosting provider contact করুন
   - SMTP configuration issues

3. **Application Support:**
   - Error logs চেক করুন
   - Test script output দেখুন

---

**Last Updated:** 2025-01-05
**Status:** Gmail SMTP configuration ready for deployment 