#!/usr/bin/env python3
"""
Test script to identify where the app startup is hanging
"""
import sys
import time
import traceback

def test_step(step_name, func):
    """Test a step and report timing"""
    print(f"Testing: {step_name}...", end=" ", flush=True)
    start = time.time()
    try:
        result = func()
        elapsed = time.time() - start
        print(f"✓ ({elapsed:.2f}s)")
        return result
    except Exception as e:
        elapsed = time.time() - start
        print(f"✗ Failed after {elapsed:.2f}s")
        print(f"  Error: {e}")
        traceback.print_exc()
        return None

print("=" * 60)
print("Testing App Startup Steps")
print("=" * 60)
print()

# Step 1: Basic imports
test_step("Basic Python imports", lambda: __import__('os'))
test_step("Platform check", lambda: __import__('platform').system())

# Step 2: WeasyPrint setup
print("\n--- WeasyPrint Setup ---")
def setup_weasyprint():
    import os
    import platform
    if platform.system() == 'Darwin':
        homebrew_lib_path = '/opt/homebrew/lib'
        if os.path.exists(homebrew_lib_path):
            os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{homebrew_lib_path}:{os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')}"
            import ctypes
            from ctypes import util as ctypes_util
            # ... setup code ...
    return True

test_step("WeasyPrint environment setup", setup_weasyprint)

# Step 3: Flask imports
print("\n--- Flask Imports ---")
test_step("Flask import", lambda: __import__('flask'))
test_step("Flask-SQLAlchemy import", lambda: __import__('flask_sqlalchemy'))
test_step("Flask-Login import", lambda: __import__('flask_login'))

# Step 4: App imports
print("\n--- App Module Imports ---")
test_step("Extensions import", lambda: __import__('extensions'))
test_step("User models import", lambda: __import__('user_models'))
test_step("Role utils import", lambda: __import__('role_utils'))

# Step 5: Blueprint imports
print("\n--- Blueprint Imports ---")
test_step("Class management import", lambda: __import__('blueprints.class_management.routes'))
test_step("Auth routes import", lambda: __import__('blueprints.auth.routes'))

# Step 6: App creation
print("\n--- App Creation ---")
def create_test_app():
    import app
    return app.create_app()

app_instance = test_step("Create Flask app", create_test_app)

# Step 7: Database
if app_instance:
    print("\n--- Database Operations ---")
    with app_instance.app_context():
        from extensions import db
        test_step("Database create_all", lambda: db.create_all())

# Step 8: Socket test
print("\n--- Network Operations ---")
def test_socket():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        s.close()
        return "Failed (expected if no internet)"

test_step("Get local IP", test_socket)

print("\n" + "=" * 60)
print("Startup test complete!")
print("=" * 60)
