#!/usr/bin/env python3
"""
Quick script to add designation and institute columns to teacher table
Run this if you want to manually add the columns without using migrations
"""

import sqlite3
import os
import sys

def add_columns():
    """Add designation and institute columns to teacher table"""
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'academic_management.db')
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(teacher)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'designation' not in columns:
            print("Adding 'designation' column...")
            cursor.execute("ALTER TABLE teacher ADD COLUMN designation VARCHAR(50)")
            print("✅ Added 'designation' column")
        else:
            print("⚠️  'designation' column already exists")
        
        if 'institute' not in columns:
            print("Adding 'institute' column...")
            cursor.execute("ALTER TABLE teacher ADD COLUMN institute VARCHAR(100) DEFAULT 'Law Discipline, KU'")
            print("✅ Added 'institute' column")
        else:
            print("⚠️  'institute' column already exists")
        
        conn.commit()
        conn.close()
        
        print("✅ Database columns added successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = add_columns()
    sys.exit(0 if success else 1)

