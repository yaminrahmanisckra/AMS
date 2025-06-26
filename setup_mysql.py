#!/usr/bin/env python3
"""
MySQL Database Setup Script for Academic Management System
এই স্ক্রিপ্টটি MySQL ডাটাবেস সেটআপ করতে সাহায্য করে
"""

import os
import sys
import pymysql
from dotenv import load_dotenv

load_dotenv()

def create_mysql_database():
    """MySQL ডাটাবেস এবং ইউজার তৈরি করে"""
    
    print("🚀 MySQL Database Setup Script")
    print("=" * 40)
    
    # Get MySQL credentials
    mysql_host = input("MySQL Host (default: localhost): ").strip() or 'localhost'
    mysql_port = input("MySQL Port (default: 3306): ").strip() or '3306'
    mysql_root_user = input("MySQL Root Username (default: root): ").strip() or 'root'
    mysql_root_password = input("MySQL Root Password: ").strip()
    
    # Database details
    database_name = input("Database Name (default: academic_management): ").strip() or 'academic_management'
    database_user = input("Database Username (default: ams_user): ").strip() or 'ams_user'
    database_password = input("Database Password: ").strip()
    
    try:
        # Connect to MySQL as root
        print(f"\n🔗 Connecting to MySQL at {mysql_host}:{mysql_port}...")
        connection = pymysql.connect(
            host=mysql_host,
            port=int(mysql_port),
            user=mysql_root_user,
            password=mysql_root_password
        )
        
        cursor = connection.cursor()
        
        # Create database
        print(f"📁 Creating database: {database_name}")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        
        # Create user
        print(f"👤 Creating user: {database_user}")
        cursor.execute(f"CREATE USER IF NOT EXISTS '{database_user}'@'%' IDENTIFIED BY '{database_password}'")
        
        # Grant privileges
        print(f"🔐 Granting privileges to {database_user} on {database_name}")
        cursor.execute(f"GRANT ALL PRIVILEGES ON `{database_name}`.* TO '{database_user}'@'%'")
        cursor.execute("FLUSH PRIVILEGES")
        
        # Test connection with new user
        print(f"🧪 Testing connection with new user...")
        test_connection = pymysql.connect(
            host=mysql_host,
            port=int(mysql_port),
            user=database_user,
            password=database_password,
            database=database_name
        )
        test_connection.close()
        
        print("✅ Database and user created successfully!")
        
        # Create .env file
        create_env_file(mysql_host, mysql_port, database_user, database_password, database_name)
        
        connection.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def create_env_file(host, port, user, password, database):
    """Environment variables ফাইল তৈরি করে"""
    
    env_content = f"""# MySQL Database Configuration
MYSQL_HOST={host}
MYSQL_PORT={port}
MYSQL_USER={user}
MYSQL_PASSWORD={password}
MYSQL_DATABASE={database}

# Application Configuration
SECRET_KEY=your_secret_key_here_change_this_in_production
FLASK_ENV=development

# Enable MySQL
MYSQL=1
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ .env file created with MySQL configuration")
    print(f"📝 Database URL: mysql+pymysql://{user}:***@{host}:{port}/{database}")

def test_mysql_connection():
    """MySQL কানেকশন টেস্ট করে"""
    
    print("\n🧪 Testing MySQL Connection...")
    
    try:
        import pymysql
        from dotenv import load_dotenv
        
        load_dotenv()
        
        mysql_host = os.getenv('MYSQL_HOST', 'localhost')
        mysql_port = os.getenv('MYSQL_PORT', '3306')
        mysql_user = os.getenv('MYSQL_USER', 'root')
        mysql_password = os.getenv('MYSQL_PASSWORD', '')
        mysql_database = os.getenv('MYSQL_DATABASE', 'academic_management')
        
        connection = pymysql.connect(
            host=mysql_host,
            port=int(mysql_port),
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        print(f"✅ MySQL connection successful!")
        print(f"📊 MySQL Version: {version[0]}")
        print(f"🗄️ Database: {mysql_database}")
        
        connection.close()
        return True
        
    except Exception as e:
        print(f"❌ MySQL connection failed: {e}")
        return False

def install_dependencies():
    """MySQL dependencies ইনস্টল করে"""
    
    print("\n📦 Installing MySQL dependencies...")
    
    try:
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyMySQL', 'cryptography'])
        print("✅ MySQL dependencies installed successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def main():
    """মূল ফাংশন"""
    
    print("🎓 Academic Management System - MySQL Setup")
    print("=" * 50)
    
    # Check if dependencies are installed
    try:
        import pymysql
        print("✅ PyMySQL already installed")
    except ImportError:
        print("⚠️ PyMySQL not found. Installing...")
        if not install_dependencies():
            print("❌ Failed to install dependencies. Please install manually:")
            print("pip install PyMySQL cryptography")
            sys.exit(1)
    
    # Ask user what they want to do
    print("\nWhat would you like to do?")
    print("1. Create new MySQL database and user")
    print("2. Test existing MySQL connection")
    print("3. Create .env file with manual configuration")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == '1':
        create_mysql_database()
    elif choice == '2':
        test_mysql_connection()
    elif choice == '3':
        print("\n📝 Manual .env Configuration")
        host = input("MySQL Host: ").strip()
        port = input("MySQL Port: ").strip()
        user = input("MySQL User: ").strip()
        password = input("MySQL Password: ").strip()
        database = input("Database Name: ").strip()
        create_env_file(host, port, user, password, database)
    else:
        print("❌ Invalid choice")
        sys.exit(1)
    
    print("\n🎉 MySQL setup completed!")
    print("\n📋 Next steps:")
    print("1. Run: python app.py")
    print("2. Create admin user: python create_admin.py")
    print("3. Access the application at: http://localhost:5001")

if __name__ == '__main__':
    main() 