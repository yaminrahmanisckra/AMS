#!/usr/bin/env python3
"""
Database Reset Script
This script will:
1. Backup the current database
2. Delete all course_outline records that have invalid session_id
3. Reset foreign key constraints
"""
import sqlite3
import os
import shutil
from datetime import datetime

def reset_database():
    """Reset database to fix course_outline deletion issues"""
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'instance', 'academic_management.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    # Create backup
    backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n=== Fixing course_outline table ===")
    
    # 1. Find and delete orphaned course_outline records
    cursor.execute('''
        SELECT co.id, co.session_id 
        FROM course_outline co 
        LEFT JOIN class_session cs ON co.session_id = cs.id 
        WHERE cs.id IS NULL
    ''')
    orphaned = cursor.fetchall()
    if orphaned:
        print(f"Found {len(orphaned)} orphaned course_outline records")
        for o in orphaned:
            cursor.execute('DELETE FROM course_outline WHERE id = ?', (o[0],))
            print(f"  Deleted orphaned outline ID {o[0]} (session_id={o[1]})")
    else:
        print("✓ No orphaned records")
    
    # 2. Check foreign key constraints
    cursor.execute('PRAGMA foreign_key_list(course_outline)')
    fks = cursor.fetchall()
    print(f"\nCurrent foreign keys: {len(fks)}")
    
    # 3. Verify all course_outline records have valid sessions
    cursor.execute('''
        SELECT COUNT(*) 
        FROM course_outline co 
        INNER JOIN class_session cs ON co.session_id = cs.id
    ''')
    valid_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM course_outline')
    total_count = cursor.fetchone()[0]
    print(f"Valid course_outline records: {valid_count}/{total_count}")
    
    conn.commit()
    conn.close()
    
    print("\n✓ Database reset complete!")
    print(f"Backup saved at: {backup_path}")

if __name__ == '__main__':
    print("=== Database Reset Script ===\n")
    response = input("This will backup and clean the database. Continue? (yes/no): ")
    if response.lower() == 'yes':
        reset_database()
    else:
        print("Cancelled.")


