#!/usr/bin/env python3
"""
Fix script for duty assignment API
Applies fix to handle empty strings for course_id, teacher_id, student_id
"""

import re
import shutil
from datetime import datetime

def apply_fix():
    app_file = 'app.py'
    backup_file = f'app.py.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    print("=" * 60)
    print("Duty Assignment Fix Script")
    print("=" * 60)
    print()
    
    # Step 1: Backup
    print(f"Step 1: Creating backup...")
    try:
        shutil.copy2(app_file, backup_file)
        print(f"✓ Backup created: {backup_file}")
    except Exception as e:
        print(f"✗ Backup failed: {e}")
        return False
    print()
    
    # Step 2: Read file
    print("Step 2: Reading app.py...")
    try:
        with open(app_file, 'r', encoding='utf-8') as f:
            content = f.read()
        print("✓ File read successfully")
    except Exception as e:
        print(f"✗ Failed to read file: {e}")
        return False
    print()
    
    original_content = content
    
    # Step 3: Apply fix 1 - course_id
    print("Step 3: Applying fix for course_id...")
    pattern1 = r"(course_id = data\.get\('course_id'\))\n\s+if course_id:"
    replacement1 = r"\1\n        if course_id == '' or course_id is None:\n            course_id = None\n        else:"
    content = re.sub(pattern1, replacement1, content)
    if content != original_content:
        print("✓ Fix 1 applied (course_id)")
    else:
        print("⚠ Fix 1 not applied (pattern not found or already applied)")
    original_content = content
    print()
    
    # Step 4: Apply fix 2 - teacher_id
    print("Step 4: Applying fix for teacher_id...")
    # Find the pattern: teacher_id = data.get('teacher_id') followed by remarks
    pattern2 = r"(teacher_id = data\.get\('teacher_id'\))\n(\s+)remarks = data\.get\('remarks'"
    replacement2 = r"\1\n\2if teacher_id == '' or teacher_id is None:\n\2    teacher_id = None\n\2else:\n\2    try:\n\2        teacher_id = int(teacher_id)\n\2    except (TypeError, ValueError):\n\2        teacher_id = None\n\2\n\2remarks = data\.get\('remarks'"
    content = re.sub(pattern2, replacement2, content)
    if content != original_content:
        print("✓ Fix 2 applied (teacher_id)")
    else:
        print("⚠ Fix 2 not applied (pattern not found or already applied)")
    original_content = content
    print()
    
    # Step 5: Apply fix 3 - student_id
    print("Step 5: Applying fix for student_id...")
    pattern3 = r"(student_id = data\.get\('student_id'\))\n(\s+)remarks = data\.get\('remarks'"
    replacement3 = r"\1\n\2if student_id == '' or student_id is None:\n\2    student_id = None\n\2else:\n\2    try:\n\2        student_id = int(student_id)\n\2    except (TypeError, ValueError):\n\2        student_id = None\n\2\n\2remarks = data\.get\('remarks'"
    content = re.sub(pattern3, replacement3, content)
    if content != original_content:
        print("✓ Fix 3 applied (student_id)")
    else:
        print("⚠ Fix 3 not applied (pattern not found or already applied)")
    print()
    
    # Step 6: Write file
    print("Step 6: Writing changes to app.py...")
    try:
        with open(app_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print("✓ File written successfully")
    except Exception as e:
        print(f"✗ Failed to write file: {e}")
        print(f"Restoring from backup...")
        shutil.copy2(backup_file, app_file)
        return False
    print()
    
    # Step 7: Validate syntax
    print("Step 7: Validating Python syntax...")
    try:
        import py_compile
        py_compile.compile(app_file, doraise=True)
        print("✓ Syntax validation passed")
    except py_compile.PyCompileError as e:
        print(f"✗ Syntax error detected: {e}")
        print(f"Restoring from backup...")
        shutil.copy2(backup_file, app_file)
        return False
    except Exception as e:
        print(f"⚠ Could not validate syntax: {e}")
        print("Please test the application manually")
    print()
    
    # Summary
    print("=" * 60)
    print("Fix Applied Successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Restart the application: touch passenger_wsgi.py")
    print("2. Test duty assignment in the browser")
    print(f"3. If issues occur, restore backup: cp {backup_file} app.py")
    print()
    
    return True

if __name__ == '__main__':
    try:
        success = apply_fix()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)




