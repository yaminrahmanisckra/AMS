import getpass
from app import app, db, User
from werkzeug.security import generate_password_hash

def create_admin():
    """Creates a new admin user or updates an existing user to be an admin."""
    with app.app_context():
        print("Admin setup...")
        
        username = input("Enter username for admin access: ")
        user = User.query.filter_by(username=username).first()

        if user:
            print(f"User '{username}' already exists.")
            if user.role == 'admin':
                print(f"User '{username}' is already an admin.")
                return
            else:
                promote = input(f"Do you want to promote '{username}' to admin? (y/n): ").lower()
                if promote == 'y':
                    user.role = 'admin'
                    db.session.commit()
                    print(f"User '{username}' has been promoted to admin.")
                else:
                    print("Admin setup cancelled.")
                    return
        else:
            print(f"User '{username}' not found. Creating a new admin user.")
            email = input("Enter admin email: ")
            full_name = input("Enter admin's full name: ")
            password = getpass.getpass("Enter admin password: ")
            
            if not all([email, full_name, password]):
                print("Email, full name, and password are required.")
                return

            admin = User(
                username=username,
                email=email,
                full_name=full_name,
                password_hash=generate_password_hash(password),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            
            print(f"Admin user '{username}' created successfully!")

if __name__ == '__main__':
    create_admin() 