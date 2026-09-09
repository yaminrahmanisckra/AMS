#!/usr/bin/env python3
"""
Complete Database Reset Script (local/dev only).

This script will:
1. Backup the current SQLite database
2. Delete the database file
3. Create a fresh database with all tables
4. Optionally create an admin user (password from getpass / env — never hard-coded)
"""
import getpass
import os
import shutil
import sys
from datetime import datetime

from extensions import db
from utils.security_config import refuse_destructive_in_production


def _bootstrap_admin_password():
    env_pw = (os.getenv('AMS_BOOTSTRAP_ADMIN_PASSWORD') or '').strip()
    if env_pw:
        return env_pw
    password = getpass.getpass('New admin password: ').strip()
    if not password:
        print('Password is required.')
        return None
    confirm = getpass.getpass('Confirm admin password: ').strip()
    if password != confirm:
        print('Passwords do not match.')
        return None
    return password


def reset_database(create_admin=False):
    """Reset database completely"""
    refuse_destructive_in_production(__file__)
    from app import create_app

    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'academic_management.db')

    app = create_app()

    with app.app_context():
        if os.path.exists(db_path):
            backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"Creating backup: {backup_path}")
            shutil.copy2(db_path, backup_path)
            print("✓ Backup created")

            db.session.close()

            print(f"\nDeleting database: {db_path}")
            os.remove(db_path)
            print("✓ Database deleted")

        print("\n=== Creating fresh database ===")
        try:
            db.create_all()
            print("✓ All tables created successfully")

            if create_admin:
                from user_models import User

                username = (os.getenv('AMS_BOOTSTRAP_ADMIN_USER') or '').strip()
                email = (os.getenv('AMS_BOOTSTRAP_ADMIN_EMAIL') or '').strip()
                full_name = (os.getenv('AMS_BOOTSTRAP_ADMIN_NAME') or 'System Administrator').strip()
                if not username:
                    username = input('Admin username: ').strip()
                if not email:
                    email = input('Admin email: ').strip()
                if not username or not email:
                    print('Skipping admin: username and email are required.')
                elif User.query.filter_by(username=username).first():
                    print(f"✓ User '{username}' already exists")
                else:
                    password = _bootstrap_admin_password()
                    if password:
                        admin = User(
                            username=username,
                            full_name=full_name,
                            email=email,
                            role='admin',
                        )
                        admin.set_password(password)
                        db.session.add(admin)
                        db.session.commit()
                        print(f"✓ Admin user created (username: {username})")

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
    refuse_destructive_in_production(__file__)
    print("=== Complete Database Reset Script (local/dev) ===\n")
    create_admin = '--create-admin' in sys.argv

    if '--yes' in sys.argv or '-y' in sys.argv:
        print("Non-interactive mode: Proceeding with reset...\n")
        success = reset_database(create_admin=create_admin)
        if success:
            print("\n✓ Reset successful! You can now start the application.")
        else:
            print("\n✗ Reset failed. Check the error messages above.")
    else:
        print("WARNING: This will DELETE all data and create a fresh database!")
        print("A backup will be created before deletion.\n")
        response = input("Continue? (yes/no): ")
        if response.lower() == 'yes':
            success = reset_database(create_admin=create_admin)
            if success:
                print("\n✓ Reset successful! You can now start the application.")
            else:
                print("\n✗ Reset failed. Check the error messages above.")
        else:
            print("Cancelled.")

