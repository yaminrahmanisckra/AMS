#!/bin/bash

# GitHub Repository Setup Script for Academic Management System
# এই স্ক্রিপ্টটি GitHub repository সেটআপ করতে সাহায্য করে

echo "🚀 GitHub Repository Setup Script শুরু হচ্ছে..."

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git ইনস্টল করা নেই। প্রথমে Git ইনস্টল করুন।"
    exit 1
fi

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "📁 Git repository ইনিশিয়ালাইজ করা হচ্ছে..."
    git init
    echo "✅ Git repository ইনিশিয়ালাইজ হয়েছে"
else
    echo "✅ Git repository ইতিমধ্যে ইনিশিয়ালাইজ করা আছে"
fi

# Add all files
echo "📋 ফাইলগুলি Git এ যোগ করা হচ্ছে..."
git add .

# Initial commit
echo "💾 প্রথম commit তৈরি করা হচ্ছে..."
git commit -m "Initial commit: Academic Management System with cPanel deployment"

# Set main branch
echo "🌿 Main branch সেট করা হচ্ছে..."
git branch -M main

# Ask for GitHub repository URL
echo ""
echo "🔗 GitHub repository URL দিন (যেমন: https://github.com/username/academic-management-system.git):"
read -p "Repository URL: " repo_url

if [ -z "$repo_url" ]; then
    echo "❌ Repository URL দেওয়া হয়নি। স্ক্রিপ্ট বন্ধ হচ্ছে।"
    exit 1
fi

# Add remote origin
echo "🔗 Remote origin যোগ করা হচ্ছে..."
git remote add origin "$repo_url"

# Push to GitHub
echo "📤 GitHub এ push করা হচ্ছে..."
git push -u origin main

echo ""
echo "✅ GitHub repository সেটআপ সম্পন্ন হয়েছে!"
echo ""
echo "📋 পরবর্তী ধাপগুলি:"
echo "1. GitHub repository তে যান: $repo_url"
echo "2. Settings → Secrets and variables → Actions"
echo "3. নিম্নলিখিত secrets যোগ করুন:"
echo "   - CPANEL_HOST=your-cpanel-server.com"
echo "   - CPANEL_USERNAME=your-cpanel-username"
echo "   - CPANEL_PASSWORD=your-cpanel-password"
echo "   - CPANEL_PORT=22"
echo ""
echo "4. Cpanel এ SSH access এনাবল করুন"
echo "5. Python app সেটআপ করুন"
echo "6. Database তৈরি করুন"
echo "7. Environment variables সেট করুন"
echo ""
echo "🎯 সহায়তা:"
echo "- GITHUB_CPANEL_DEPLOYMENT.md ফাইলটি দেখুন বিস্তারিত গাইডের জন্য"
echo "- README.md ফাইলটি দেখুন প্রজেক্ট সম্পর্কে জানার জন্য"
echo ""
echo "🚀 আপনার Academic Management System এখন GitHub-powered!" 