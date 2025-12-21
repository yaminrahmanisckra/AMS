#!/usr/bin/env python3
"""
Database Clear Script
This script will clear all data from the database by dropping all tables and recreating them.
WARNING: This will delete ALL data from the database!
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db

def clear_database(confirm=False):
    """Clear all data from database"""
    app = create_app()
    
    with app.app_context():
        # Warning message
        print("=" * 60)
        print("WARNING: This will DELETE ALL DATA from the database!")
        print("=" * 60)
        
        if not confirm:
            try:
                response = input("\nAre you sure you want to clear the database? Type 'YES' to confirm: ")
            except EOFError:
                # Non-interactive environment - require command line flag
                print("\n⚠️  Cannot read input in non-interactive mode.")
                print("To clear database without confirmation, run:")
                print("  python3 clear_database.py --yes")
                return
            
            if response != 'YES':
                print("\nDatabase clear cancelled.")
                return
        else:
            print("\n⚠️  Auto-confirmation enabled. Proceeding with database clear...")
        
        print("\nClearing database...")
        
        try:
            # Drop all tables
            print("Dropping all tables...")
            db.drop_all()
            print("✓ All tables dropped")
            
            # Recreate all tables
            print("Recreating all tables...")
            db.create_all()
            print("✓ All tables recreated")
            
            print("\n" + "=" * 60)
            print("✓ Database cleared successfully!")
            print("=" * 60)
            print("\nAll tables have been dropped and recreated.")
            print("You can now start fresh with the application.")
            
        except Exception as e:
            print(f"\n✗ Error clearing database: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    import sys
    # Check for --yes flag
    confirm = '--yes' in sys.argv or '-y' in sys.argv
    clear_database(confirm=confirm)
