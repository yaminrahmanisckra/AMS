#!/usr/bin/env python3
"""Create admin user account for Academic Management System"""

from app import create_app
from extensions import db
from user_models import User
from werkzeug.security import generate_password_hash

def create_admin():
    """Creates a new admin user"""
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("Admin Account Creation")
        print("=" * 50)
        
        # Check if admin already exists
        existing_admin = User.query.filter_by(role='admin').first()
        if existing_admin:
            print(f"\n⚠️  Admin user already exists: {existing_admin.username}")
            response = input("Do you want to create another admin? (y/n): ").lower()
            if response != 'y':
                print("Admin creation cancelled.")
                return
        
        # Get user input
        username = input("\nEnter username for admin: ").strip()
        if not username:
            print("❌ Username is required!")
            return
        
        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"\n⚠️  User '{username}' already exists.")
            if existing_user.role == 'admin':
                print(f"User '{username}' is already an admin.")
                return
            else:
                promote = input(f"Do you want to promote '{username}' to admin? (y/n): ").lower()
                if promote == 'y':
                    existing_user.role = 'admin'
                    db.session.commit()
                    print(f"✅ User '{username}' has been promoted to admin.")
                    return
                else:
                    print("Admin creation cancelled.")
                    return
        
        email = input("Enter admin email: ").strip()
        if not email:
            print("❌ Email is required!")
            return
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            print(f"❌ Email '{email}' is already registered to user '{existing_email.username}'")
            return
        
        full_name = input("Enter admin's full name: ").strip()
        if not full_name:
            print("❌ Full name is required!")
            return
        
        import getpass
        password = getpass.getpass("Enter admin password: ").strip()
        if not password:
            print("❌ Password is required!")
            return
        
        password_confirm = getpass.getpass("Confirm admin password: ").strip()
        if password != password_confirm:
            print("❌ Passwords do not match!")
            return
        
        try:
            # Create admin user
            admin = User(
                username=username,
                email=email,
                full_name=full_name,
                role='admin'
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            
            print("\n" + "=" * 50)
            print("✅ Admin account created successfully!")
            print("=" * 50)
            print(f"Username: {username}")
            print(f"Email: {email}")
            print(f"Full Name: {full_name}")
            print(f"Role: admin")
            print("=" * 50)
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error creating admin account: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    create_admin()
