#!/usr/bin/env python3
"""
Fix missing columns in result_session table
Adds batch and curriculum_id columns if they don't exist
"""

import sqlite3
import os
from pathlib import Path

def fix_result_session_columns():
    """Add missing columns to result_session table"""
    
    # Get database path
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'academic_management.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    print(f"📁 Database path: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current columns
        cursor.execute("PRAGMA table_info(result_session)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Current columns: {', '.join(columns)}")
        
        # Add batch column if missing
        if 'batch' not in columns:
            print("➕ Adding 'batch' column...")
            cursor.execute("ALTER TABLE result_session ADD COLUMN batch VARCHAR(50)")
            print("✅ Added 'batch' column")
        else:
            print("✓ 'batch' column already exists")
        
        # Add curriculum_id column if missing
        if 'curriculum_id' not in columns:
            print("➕ Adding 'curriculum_id' column...")
            cursor.execute("ALTER TABLE result_session ADD COLUMN curriculum_id INTEGER")
            print("✅ Added 'curriculum_id' column")
        else:
            print("✓ 'curriculum_id' column already exists")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Successfully fixed result_session table!")
        return True
        
    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("🔧 Fixing result_session table columns...\n")
    success = fix_result_session_columns()
    if success:
        print("\n✨ Done! You can now access Result Management.")
    else:
        print("\n❌ Failed to fix columns. Please check the error messages above.")
