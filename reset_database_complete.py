#!/usr/bin/env python3
"""
Complete Database Reset Script
This script will:
1. Backup the current database
2. Delete the database file
3. Create a fresh database with all tables
4. Optionally create admin user
"""
import os
import shutil
import sys
from datetime import datetime
from flask import Flask
from extensions import db
from app import create_app

def reset_database():
    """Reset database completely"""
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'academic_management.db')
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Create backup if database exists
        if os.path.exists(db_path):
            backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"Creating backup: {backup_path}")
            shutil.copy2(db_path, backup_path)
            print("✓ Backup created")
            
            # Close any existing connections
            db.session.close()
            
            # Delete the database file
            print(f"\nDeleting database: {db_path}")
            os.remove(db_path)
            print("✓ Database deleted")
        
        # Create fresh database
        print("\n=== Creating fresh database ===")
        try:
            # Create all tables
            db.create_all()
            print("✓ All tables created successfully")
            
            # Create admin user if needed
            print("\n=== Creating admin user ===")
            from user_models import User
            from werkzeug.security import generate_password_hash
            
            # Check if admin already exists
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    password=generate_password_hash('admin123'),
                    full_name='System Administrator',
                    email='admin@example.com',
                    role='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print("✓ Admin user created (username: admin, password: admin123)")
            else:
                print("✓ Admin user already exists")
            
            print("\n✓ Database reset complete!")
            if os.path.exists(db_path):
                print(f"Fresh database created at: {db_path}")
            
        except Exception as e:
            print(f"\n✗ Error creating database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    print("=== Complete Database Reset Script ===\n")
    
    # Check if --yes flag is provided for non-interactive mode
    if '--yes' in sys.argv or '-y' in sys.argv:
        print("Non-interactive mode: Proceeding with reset...\n")
        success = reset_database()
        if success:
            print("\n✓ Reset successful! You can now start the application.")
        else:
            print("\n✗ Reset failed. Check the error messages above.")
    else:
        print("WARNING: This will DELETE all data and create a fresh database!")
        print("A backup will be created before deletion.\n")
        response = input("Continue? (yes/no): ")
        if response.lower() == 'yes':
            success = reset_database()
            if success:
                print("\n✓ Reset successful! You can now start the application.")
            else:
                print("\n✗ Reset failed. Check the error messages above.")
        else:
            print("Cancelled.")

