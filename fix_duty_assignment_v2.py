#!/usr/bin/env python3
"""
Fix script for duty assignment API - Version 2
Applies fix to handle empty strings for course_id, teacher_id, student_id
"""

import shutil
from datetime import datetime

def apply_fix():
    app_file = 'app.py'
    backup_file = f'app.py.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    
    print("=" * 60)
    print("Duty Assignment Fix Script v2")
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
            lines = f.readlines()
        print(f"✓ File read successfully ({len(lines)} lines)")
    except Exception as e:
        print(f"✗ Failed to read file: {e}")
        return False
    print()
    
    # Step 3: Find and fix course_id
    print("Step 3: Applying fix for course_id...")
    fixed = False
    for i, line in enumerate(lines):
        if "course_id = data.get('course_id')" in line and i + 1 < len(lines):
            if "if course_id:" in lines[i + 1]:
                # Replace the if statement
                lines[i + 1] = "        if course_id == '' or course_id is None:\n"
                lines.insert(i + 2, "            course_id = None\n")
                lines.insert(i + 3, "        else:\n")
                fixed = True
                print(f"✓ Fix 1 applied at line {i + 2}")
                break
    
    if not fixed:
        print("⚠ Fix 1 not applied (pattern not found or already applied)")
    print()
    
    # Step 4: Find and fix teacher_id
    print("Step 4: Applying fix for teacher_id...")
    fixed = False
    for i, line in enumerate(lines):
        if "teacher_id = data.get('teacher_id')" in line:
            # Check if fix already applied
            if i + 1 < len(lines) and "if teacher_id == ''" in lines[i + 1]:
                print("⚠ Fix 2 already applied")
                break
            # Find where remarks line is
            for j in range(i + 1, min(i + 10, len(lines))):
                if "remarks = data.get('remarks'" in lines[j]:
                    # Insert fix before remarks
                    fix_lines = [
                        "        if teacher_id == '' or teacher_id is None:\n",
                        "            teacher_id = None\n",
                        "        else:\n",
                        "            try:\n",
                        "                teacher_id = int(teacher_id)\n",
                        "            except (TypeError, ValueError):\n",
                        "                teacher_id = None\n",
                        "\n"
                    ]
                    lines[j:j] = fix_lines
                    fixed = True
                    print(f"✓ Fix 2 applied at line {i + 2}")
                    break
            break
    
    if not fixed:
        print("⚠ Fix 2 not applied (pattern not found or already applied)")
    print()
    
    # Step 5: Find and fix student_id
    print("Step 5: Applying fix for student_id...")
    fixed = False
    for i, line in enumerate(lines):
        if "student_id = data.get('student_id')" in line:
            # Check if fix already applied
            if i + 1 < len(lines) and "if student_id == ''" in lines[i + 1]:
                print("⚠ Fix 3 already applied")
                break
            # Find where remarks line is (or next assignment)
            for j in range(i + 1, min(i + 10, len(lines))):
                if "remarks = data.get('remarks'" in lines[j]:
                    # Insert fix before remarks
                    fix_lines = [
                        "        if student_id == '' or student_id is None:\n",
                        "            student_id = None\n",
                        "        else:\n",
                        "            try:\n",
                        "                student_id = int(student_id)\n",
                        "            except (TypeError, ValueError):\n",
                        "                student_id = None\n",
                        "\n"
                    ]
                    lines[j:j] = fix_lines
                    fixed = True
                    print(f"✓ Fix 3 applied at line {i + 2}")
                    break
            break
    
    if not fixed:
        print("⚠ Fix 3 not applied (pattern not found or already applied)")
    print()
    
    # Step 6: Write file
    print("Step 6: Writing changes to app.py...")
    try:
        with open(app_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
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




