#!/bin/bash

# Cpanel Deployment Script for Academic Management System
# এই স্ক্রিপ্টটি আপনার প্রজেক্টকে Cpanel এর জন্য প্রস্তুত করে

echo "🚀 Cpanel Deployment Script শুরু হচ্ছে..."

# Create deployment directory
DEPLOY_DIR="cpanel_deploy"
echo "📁 Deployment ডিরেক্টরি তৈরি করা হচ্ছে: $DEPLOY_DIR"

# Remove existing deployment directory
rm -rf $DEPLOY_DIR
mkdir $DEPLOY_DIR

# Copy necessary files
echo "📋 প্রয়োজনীয় ফাইলগুলি কপি করা হচ্ছে..."

# Main application files
cp app.py $DEPLOY_DIR/
cp passenger_wsgi.py $DEPLOY_DIR/
cp requirements_cpanel.txt $DEPLOY_DIR/
cp models.py $DEPLOY_DIR/
cp user_models.py $DEPLOY_DIR/
cp extensions.py $DEPLOY_DIR/
cp create_admin.py $DEPLOY_DIR/

# Copy directories
cp -r blueprints $DEPLOY_DIR/
cp -r templates $DEPLOY_DIR/
cp -r static $DEPLOY_DIR/
cp -r migrations $DEPLOY_DIR/

# Create necessary directories
mkdir -p $DEPLOY_DIR/instance
mkdir -p $DEPLOY_DIR/uploads

# Create .htaccess file for static files
cat > $DEPLOY_DIR/.htaccess << 'EOF'
RewriteEngine On

# Handle static files
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^static/(.*)$ static/$1 [L]

# Handle all other requests through passenger_wsgi.py
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ passenger_wsgi.py/$1 [L]
EOF

# Create deployment checklist
cat > $DEPLOY_DIR/CPANEL_CHECKLIST.md << 'EOF'
# Cpanel Deployment Checklist

## ✅ ফাইল আপলোড
- [ ] সব ফাইল public_html ফোল্ডারে আপলোড করুন
- [ ] ফাইল পারমিশন সেট করুন (644 for files, 755 for folders)

## ✅ Python App Setup
- [ ] Cpanel → Software → Setup Python App
- [ ] Python version: 3.8+
- [ ] Application startup file: passenger_wsgi.py
- [ ] Application entry point: application
- [ ] Application URL: your domain

## ✅ Database Setup
- [ ] Cpanel → MySQL Databases
- [ ] Create database
- [ ] Create database user
- [ ] Assign user to database
- [ ] Set DATABASE_URL environment variable

## ✅ Environment Variables
- [ ] CPANEL=1
- [ ] SECRET_KEY=your_secret_key
- [ ] DATABASE_URL=mysql://user:pass@localhost/dbname

## ✅ Dependencies
- [ ] Terminal → cd public_html
- [ ] pip3 install -r requirements_cpanel.txt

## ✅ Final Steps
- [ ] Restart Python App
- [ ] Test application
- [ ] Create admin user

## 🔧 Troubleshooting
- Check error logs in Cpanel
- Verify file permissions
- Test database connection
EOF

# Create a simple deployment guide
cat > $DEPLOY_DIR/QUICK_DEPLOY.md << 'EOF'
# দ্রুত ডিপ্লয় গাইড

## ১. ফাইল আপলোড
- সব ফাইল public_html ফোল্ডারে আপলোড করুন

## ২. Python App তৈরি করুন
- Cpanel → Software → Setup Python App
- Python version: 3.8+
- Startup file: passenger_wsgi.py
- Entry point: application

## ৩. ডাটাবেস তৈরি করুন
- Cpanel → MySQL Databases
- Database এবং User তৈরি করুন

## ৪. Environment Variables সেট করুন
- CPANEL=1
- SECRET_KEY=your_secret_key
- DATABASE_URL=mysql://user:pass@localhost/dbname

## ৫. Dependencies ইনস্টল করুন
- Terminal → pip3 install -r requirements_cpanel.txt

## ৬. অ্যাপ্লিকেশন রিস্টার্ট করুন
- Setup Python App → Restart

## ৭. টেস্ট করুন
- আপনার ডোমেইন ভিজিট করুন
EOF

echo "✅ Deployment ফাইলগুলি তৈরি হয়েছে!"
echo ""
echo "📦 পরবর্তী ধাপগুলি:"
echo "1. $DEPLOY_DIR ফোল্ডারটি ZIP করুন"
echo "2. Cpanel এর File Manager এ আপলোড করুন"
echo "3. public_html ফোল্ডারে এক্সট্রাক্ট করুন"
echo "4. CPANEL_CHECKLIST.md অনুসরণ করুন"
echo ""
echo "🎯 সহায়তা:"
echo "- QUICK_DEPLOY.md ফাইলটি দেখুন দ্রুত গাইডের জন্য"
echo "- CPANEL_CHECKLIST.md ফাইলটি দেখুন বিস্তারিত চেকলিস্টের জন্য"
echo ""
echo "🚀 আপনার Academic Management System Cpanel এ ডিপ্লয় করার জন্য প্রস্তুত!" 