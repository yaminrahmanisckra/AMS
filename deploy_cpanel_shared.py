#!/usr/bin/env python3
"""
Academic Management System - cPanel Shared Hosting Deployment Helper
This script helps set up the application for shared hosting cPanel deployment.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_banner():
    """Print deployment banner"""
    print("=" * 60)
    print("🚀 Academic Management System - cPanel Deployment Helper")
    print("=" * 60)
    print()

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    print(f"🐍 Python Version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 9:
        print("✅ Python version is compatible with cPanel 3.9.22")
        return True
    else:
        print("⚠️  Warning: Python version might not be compatible with cPanel 3.9.22")
        return False

def create_deployment_package():
    """Create deployment package for cPanel"""
    print("\n📦 Creating deployment package...")
    
    # Create deployment directory
    deploy_dir = Path("cpanel_deploy")
    if deploy_dir.exists():
        shutil.rmtree(deploy_dir)
    deploy_dir.mkdir()
    
    # Files to copy
    files_to_copy = [
        "app.py",
        "passenger_wsgi.py", 
        "requirements_cpanel.txt",
        "models.py",
        "user_models.py",
        "extensions.py",
        "create_admin.py",
        ".htaccess"
    ]
    
    # Copy files
    for file in files_to_copy:
        if Path(file).exists():
            shutil.copy2(file, deploy_dir)
            print(f"✅ Copied {file}")
        else:
            print(f"⚠️  Warning: {file} not found")
    
    # Directories to copy
    dirs_to_copy = [
        "blueprints",
        "templates", 
        "static",
        "migrations"
    ]
    
    # Copy directories
    for dir_name in dirs_to_copy:
        if Path(dir_name).exists():
            shutil.copytree(dir_name, deploy_dir / dir_name)
            print(f"✅ Copied {dir_name}/")
        else:
            print(f"⚠️  Warning: {dir_name}/ not found")
    
    # Create necessary directories
    (deploy_dir / "instance").mkdir(exist_ok=True)
    (deploy_dir / "uploads").mkdir(exist_ok=True)
    
    # Create deployment info
    deploy_info = deploy_dir / "DEPLOY_INFO.txt"
    with open(deploy_info, 'w') as f:
        f.write("Academic Management System - cPanel Deployment\n")
        f.write("=" * 50 + "\n")
        f.write(f"Deployed: {os.popen('date').read().strip()}\n")
        f.write(f"Python Version: 3.9.22\n")
        f.write("Deployment Method: GitHub Actions + cPanel API\n")
    
    print("✅ Deployment package created successfully!")
    return deploy_dir

def create_zip_package(deploy_dir):
    """Create ZIP package for upload"""
    print("\n🗜️  Creating ZIP package...")
    
    zip_name = "ams_cpanel_deployment.zip"
    if os.path.exists(zip_name):
        os.remove(zip_name)
    
    # Create ZIP file
    shutil.make_archive("ams_cpanel_deployment", 'zip', deploy_dir)
    
    # Get file size
    size = os.path.getsize(zip_name)
    size_mb = size / (1024 * 1024)
    
    print(f"✅ ZIP package created: {zip_name}")
    print(f"📊 Package size: {size_mb:.2f} MB")
    
    return zip_name

def check_requirements():
    """Check if all required files exist"""
    print("\n🔍 Checking requirements...")
    
    required_files = [
        "app.py",
        "passenger_wsgi.py",
        "requirements_cpanel.txt",
        ".htaccess"
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
        else:
            print(f"✅ {file}")
    
    if missing_files:
        print(f"\n❌ Missing files: {', '.join(missing_files)}")
        return False
    
    print("✅ All required files found!")
    return True

def generate_setup_instructions():
    """Generate setup instructions"""
    print("\n📋 Generating setup instructions...")
    
    instructions = """
# 🚀 cPanel Setup Instructions

## 1. Upload Files
- Upload the ZIP file to your cPanel File Manager
- Extract it in the public_html directory

## 2. Python App Setup
1. Go to cPanel → Software → Setup Python App
2. Create new application:
   - Python version: 3.9.22
   - Application startup file: passenger_wsgi.py
   - Application entry point: application
   - Application URL: your domain
   - Application root: /public_html

## 3. Install Dependencies
1. Go to cPanel → Terminal
2. Run: cd public_html && pip3 install -r requirements_cpanel.txt

## 4. Environment Variables
1. Go to cPanel → Software → Environment Variables
2. Add these variables:
   - CPANEL=1
   - SECRET_KEY=your-secret-key
   - DATABASE_URL=mysql://username:password@localhost/database_name
   - FLASK_ENV=production

## 5. Database Setup
1. Create MySQL database in cPanel
2. Import database schema
3. Update DATABASE_URL with correct credentials

## 6. Create Admin User
1. Go to cPanel → Terminal
2. Run: cd public_html && python3 create_admin.py

## 7. Restart Application
1. Go back to Setup Python App
2. Click "Restart" button

## 8. Test Application
Visit your domain to test the application
"""
    
    with open("CPANEL_SETUP_INSTRUCTIONS.txt", 'w') as f:
        f.write(instructions)
    
    print("✅ Setup instructions generated: CPANEL_SETUP_INSTRUCTIONS.txt")

def main():
    """Main deployment function"""
    print_banner()
    
    # Check Python version
    check_python_version()
    
    # Check requirements
    if not check_requirements():
        print("\n❌ Deployment cannot proceed due to missing files.")
        return
    
    # Create deployment package
    deploy_dir = create_deployment_package()
    
    # Create ZIP package
    zip_file = create_zip_package(deploy_dir)
    
    # Generate instructions
    generate_setup_instructions()
    
    print("\n" + "=" * 60)
    print("🎉 Deployment package ready!")
    print("=" * 60)
    print(f"📦 ZIP file: {zip_file}")
    print("📋 Instructions: CPANEL_SETUP_INSTRUCTIONS.txt")
    print("\n📤 Next steps:")
    print("1. Upload the ZIP file to your cPanel")
    print("2. Follow the setup instructions")
    print("3. Configure your database")
    print("4. Test your application")
    print("\n🚀 Happy deployment!")

if __name__ == "__main__":
    main() 