"""
Migration script to add custom entry columns to routine table.
Run this script to add is_custom and custom_course_name columns.

Usage:
    python add_custom_entry_columns.py
"""

import os
import sys

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def add_columns():
    """Add is_custom and custom_course_name columns to routine table"""
    from app import create_app
    from extensions import db
    from sqlalchemy import text, inspect
    
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('routine')]
            
            print(f"Current columns in routine table: {columns}")
            
            # Add is_custom column if it doesn't exist
            if 'is_custom' not in columns:
                print("Adding is_custom column...")
                try:
                    db.session.execute(text("""
                        ALTER TABLE routine ADD COLUMN is_custom BOOLEAN DEFAULT 0
                    """))
                    db.session.commit()
                    print("✓ is_custom column added successfully")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error adding is_custom column: {e}")
                    # Try MySQL syntax
                    try:
                        db.session.execute(text("""
                            ALTER TABLE routine ADD COLUMN is_custom TINYINT(1) DEFAULT 0
                        """))
                        db.session.commit()
                        print("✓ is_custom column added successfully (MySQL syntax)")
                    except Exception as e2:
                        db.session.rollback()
                        print(f"Error with MySQL syntax: {e2}")
            else:
                print("✓ is_custom column already exists")
            
            # Add custom_course_name column if it doesn't exist
            if 'custom_course_name' not in columns:
                print("Adding custom_course_name column...")
                try:
                    db.session.execute(text("""
                        ALTER TABLE routine ADD COLUMN custom_course_name VARCHAR(200)
                    """))
                    db.session.commit()
                    print("✓ custom_course_name column added successfully")
                except Exception as e:
                    db.session.rollback()
                    print(f"Error adding custom_course_name column: {e}")
            else:
                print("✓ custom_course_name column already exists")
            
            # Verify columns were added
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('routine')]
            print(f"\nFinal columns in routine table: {columns}")
            
            if 'is_custom' in columns and 'custom_course_name' in columns:
                print("\n✅ Migration completed successfully!")
            else:
                print("\n⚠️ Some columns may not have been added. Please check manually.")
            
        except Exception as e:
            print(f"Error during migration: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    add_columns()
