"""Script to fix database schema - add missing columns to match models"""
import sqlite3
import os

def fix_database(db_path):
    """Add missing columns to database tables"""
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n=== Fixing {db_path} ===\n")
    
    # Fix class_session table
    print("Checking class_session table...")
    cursor.execute('PRAGMA table_info(class_session)')
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    columns_to_add = {
        'course_scope': 'VARCHAR(10) DEFAULT "full"',
        'split_group_id': 'VARCHAR(36)',
    }
    
    for col_name, col_def in columns_to_add.items():
        if col_name not in existing_cols:
            try:
                cursor.execute(f'ALTER TABLE class_session ADD COLUMN {col_name} {col_def}')
                print(f"  ✓ Added {col_name}")
            except Exception as e:
                print(f"  ✗ Error adding {col_name}: {e}")
        else:
            print(f"  - {col_name} already exists")
    
    # Fix class_student table
    print("\nChecking class_student table...")
    cursor.execute('PRAGMA table_info(class_student)')
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    if 'assessment_absent' not in existing_cols:
        try:
            cursor.execute('ALTER TABLE class_student ADD COLUMN assessment_absent TEXT')
            print(f"  ✓ Added assessment_absent")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print(f"  - assessment_absent already exists")
    
    # Fix course_outline table
    print("\nChecking course_outline table...")
    try:
        cursor.execute('PRAGMA table_info(course_outline)')
        existing_cols = [row[1] for row in cursor.fetchall()]
        
        columns_to_add = {
            'course_content_summary': 'TEXT',
            'clo_plo_mapping': 'TEXT',
            'evaluation_policy': 'TEXT',
            'cie_breakdown': 'TEXT',
            'smee_breakdown': 'TEXT',
            'course_file_components': 'TEXT',
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_cols:
                try:
                    cursor.execute(f'ALTER TABLE course_outline ADD COLUMN {col_name} {col_type}')
                    print(f"  ✓ Added {col_name}")
                except Exception as e:
                    print(f"  ✗ Error adding {col_name}: {e}")
            else:
                print(f"  - {col_name} already exists")
    except Exception as e:
        print(f"  Note: course_outline table might not exist: {e}")
    
    conn.commit()
    conn.close()
    print(f"\n✓ Database {db_path} fixed!\n")

if __name__ == '__main__':
    # Fix both databases
    fix_database('instance/academic_management.db')
    fix_database('instance/dev.sqlite')


