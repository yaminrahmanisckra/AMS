#!/usr/bin/env python3
"""
Database Migration Script for cPanel
Run this script to apply database migrations
"""

import os
import sys
from flask import Flask
from flask_migrate import upgrade

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import your app
from app import app

def run_migration():
    """Run database migrations"""
    try:
        with app.app_context():
            print("Starting database migration...")
            upgrade()
            print("✅ Database migration completed successfully!")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1) 