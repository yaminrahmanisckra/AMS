#!/usr/bin/env python3
"""
Deployment Health Check Script for Academic Management System
This script checks if the application is properly deployed and configured.
"""

import sys
import os
import traceback
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{RESET} {text}")

def print_info(text):
    print(f"{BLUE}ℹ{RESET} {text}")

def check_python_version():
    """Check Python version"""
    print_header("Checking Python Version")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print_info(f"Python version: {version_str}")
    print_info(f"Python executable: {sys.executable}")
    
    # Check if we're in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print_info("Running in virtual environment")
    else:
        print_warning("Not running in virtual environment")
        print_info("On cPanel, ensure you're using the Python app's environment")
    
    if version.major == 3 and version.minor >= 7:
        print_success(f"Python {version_str} is compatible (requires 3.7+)")
        return True
    else:
        print_error(f"Python {version_str} is not compatible (requires 3.7+)")
        print_warning("On cPanel Python apps, use the app's Python, not system Python")
        print_info("Check cPanel → Software → Setup Python App for correct Python version")
        return False

def check_required_files():
    """Check if required files exist"""
    print_header("Checking Required Files")
    required_files = [
        'app.py',
        'passenger_wsgi.py',
        'requirements.txt',
        'extensions.py',
        '.env',
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print_success(f"{file} exists")
        else:
            print_error(f"{file} is missing")
            all_exist = False
    
    return all_exist

def check_directories():
    """Check if required directories exist"""
    print_header("Checking Required Directories")
    required_dirs = [
        'blueprints',
        'templates',
        'static',
        'logs',
        'instance',
    ]
    
    all_exist = True
    for directory in required_dirs:
        if os.path.exists(directory) and os.path.isdir(directory):
            print_success(f"{directory}/ exists")
        else:
            print_warning(f"{directory}/ is missing (will be created if needed)")
            if directory in ['logs', 'instance']:
                try:
                    os.makedirs(directory, exist_ok=True)
                    print_success(f"Created {directory}/ directory")
                except Exception as e:
                    print_error(f"Could not create {directory}/: {e}")
                    all_exist = False
    
    return all_exist

def check_file_permissions():
    """Check file permissions"""
    print_header("Checking File Permissions")
    
    issues = []
    files_to_check = ['app.py', 'passenger_wsgi.py']
    
    for file in files_to_check:
        if os.path.exists(file):
            stat = os.stat(file)
            mode = oct(stat.st_mode)[-3:]
            if mode >= '644':
                print_success(f"{file} permissions: {mode}")
            else:
                print_warning(f"{file} permissions: {mode} (should be 644 or 755)")
    
    return True

def check_dependencies():
    """Check if required Python packages are installed"""
    print_header("Checking Dependencies")
    print_info(f"Using Python: {sys.executable}")
    
    required_packages = [
        'flask',
        'flask_sqlalchemy',
        'flask_login',
        'flask_migrate',
        'flask_mail',
        'werkzeug',
        'sqlalchemy',
        'pymysql',
        'weasyprint',
        'reportlab',
        'pandas',
        'openpyxl',
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            # Try different import names
            import_name = package.replace('-', '_')
            if package == 'flask_sqlalchemy':
                import_name = 'flask_sqlalchemy'
            elif package == 'flask_login':
                import_name = 'flask_login'
            elif package == 'flask_migrate':
                import_name = 'flask_migrate'
            elif package == 'flask_mail':
                import_name = 'flask_mail'
            
            __import__(import_name)
            print_success(f"{package} is installed")
        except ImportError:
            print_error(f"{package} is NOT installed")
            missing_packages.append(package)
        except Exception as e:
            print_warning(f"{package} import error: {e}")
    
    if missing_packages:
        print_error(f"Missing packages: {', '.join(missing_packages)}")
        print_warning("IMPORTANT: On cPanel, packages must be installed in the Python app's virtual environment")
        print_info("To install:")
        print_info("1. Go to cPanel → Software → Setup Python App")
        print_info("2. Select your app → Click 'Install App' or check 'Install Dependencies'")
        print_info("3. Or use the app's Python: /home/USER/virtualenv/APP/version/bin/pip install package_name")
        print_info("4. Or run: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_python_syntax():
    """Check Python syntax of main files"""
    print_header("Checking Python Syntax")
    
    files_to_check = [
        'app.py',
        'extensions.py',
        'passenger_wsgi.py',
    ]
    
    syntax_errors = []
    for file in files_to_check:
        if os.path.exists(file):
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    code = f.read()
                compile(code, file, 'exec')
                print_success(f"{file} syntax is valid")
            except SyntaxError as e:
                print_error(f"{file} has syntax error: {e}")
                syntax_errors.append((file, e))
            except Exception as e:
                print_warning(f"{file} check error: {e}")
    
    return len(syntax_errors) == 0

def check_imports():
    """Check if main modules can be imported"""
    print_header("Checking Module Imports")
    
    try:
        # Add current directory to path
        sys.path.insert(0, os.getcwd())
        
        # Test extensions import
        try:
            import extensions
            print_success("extensions module imports successfully")
        except Exception as e:
            print_error(f"extensions import failed: {e}")
            return False
        
        # Test app import (this is the critical test)
        try:
            from app import create_app
            print_success("app module imports successfully")
            
            # Try to create app instance
            try:
                app = create_app()
                print_success("Application instance created successfully")
                
                # Check if app has required attributes
                if hasattr(app, 'config'):
                    print_success("Application has config")
                else:
                    print_error("Application missing config")
                    return False
                
                return True
            except Exception as e:
                print_error(f"Failed to create application instance: {e}")
                print_error(f"Traceback:\n{traceback.format_exc()}")
                return False
                
        except Exception as e:
            print_error(f"app import failed: {e}")
            print_error(f"Traceback:\n{traceback.format_exc()}")
            return False
            
    except Exception as e:
        print_error(f"Import check failed: {e}")
        print_error(f"Traceback:\n{traceback.format_exc()}")
        return False

def check_blueprints_import():
    """Check if blueprints can be imported"""
    print_header("Checking Blueprint Imports")
    
    blueprint_modules = [
        'blueprints.class_management.routes',
        'blueprints.auth.routes',
    ]
    
    import_errors = []
    for module in blueprint_modules:
        try:
            __import__(module)
            print_success(f"{module} imports successfully")
        except SyntaxError as e:
            print_error(f"{module} has syntax error: {e}")
            import_errors.append((module, e))
        except ImportError as e:
            print_error(f"{module} import failed: {e}")
            import_errors.append((module, e))
        except Exception as e:
            print_warning(f"{module} import warning: {e}")
    
    return len(import_errors) == 0

def check_database_config():
    """Check database configuration"""
    print_header("Checking Database Configuration")
    
    try:
        # Check if .env exists
        if not os.path.exists('.env'):
            print_warning(".env file not found (using environment variables or defaults)")
            return True
        
        # Try to load .env (if python-dotenv is available)
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print_success(".env file loaded")
        except ImportError:
            print_warning("python-dotenv not installed, skipping .env check")
        except Exception as e:
            print_warning(f"Error loading .env: {e}")
        
        # Check DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            print_success("DATABASE_URL is set")
            if 'mysql' in database_url.lower():
                print_info("Using MySQL database")
            elif 'sqlite' in database_url.lower():
                print_info("Using SQLite database")
        else:
            print_warning("DATABASE_URL not set (will use SQLite fallback)")
        
        return True
    except Exception as e:
        print_error(f"Database config check failed: {e}")
        return False

def check_environment_variables():
    """Check critical environment variables"""
    print_header("Checking Environment Variables")
    
    critical_vars = ['SECRET_KEY']
    optional_vars = ['DATABASE_URL', 'MAIL_SERVER', 'MAIL_USERNAME']
    
    all_critical = True
    for var in critical_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var} is set")
        else:
            print_error(f"{var} is NOT set (required)")
            all_critical = False
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print_success(f"{var} is set")
        else:
            print_warning(f"{var} is not set (optional)")
    
    return all_critical

def run_full_check():
    """Run all checks"""
    print(f"\n{BOLD}{GREEN}Academic Management System - Deployment Health Check{RESET}\n")
    print(f"Working directory: {os.getcwd()}\n")
    
    # Check if this looks like cPanel environment
    if os.path.exists('/home') and 'virtualenv' in os.getcwd() or os.path.exists('passenger_wsgi.py'):
        print_info("Detected cPanel Python app environment")
        print_warning("NOTE: This script should be run with the Python app's Python, not system Python")
        print_info("The Python app uses its own virtual environment with packages installed separately")
        print()
    
    results = {}
    
    # Run all checks
    results['python_version'] = check_python_version()
    results['required_files'] = check_required_files()
    results['directories'] = check_directories()
    results['file_permissions'] = check_file_permissions()
    results['dependencies'] = check_dependencies()
    results['python_syntax'] = check_python_syntax()
    results['blueprints_import'] = check_blueprints_import()
    results['database_config'] = check_database_config()
    results['environment_variables'] = check_environment_variables()
    results['app_import'] = check_imports()
    
    # Summary
    print_header("Summary")
    
    critical_checks = [
        'python_version',
        'python_syntax',
        'app_import',
    ]
    
    warnings = []
    errors = []
    
    for check, result in results.items():
        if check in critical_checks:
            if not result:
                errors.append(check)
        elif not result:
            warnings.append(check)
    
    if errors:
        print_error(f"Critical issues found: {', '.join(errors)}")
        print_error("Application will NOT work correctly!")
    else:
        print_success("All critical checks passed!")
    
    if warnings:
        print_warning(f"Warnings: {', '.join(warnings)}")
        print_warning("Application may have issues, but should start")
    
    if not errors and not warnings:
        print_success("All checks passed! Application should work correctly.")
    
    # Return exit code
    return 0 if not errors else 1

if __name__ == '__main__':
    try:
        exit_code = run_full_check()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nCheck interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        print_error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)

