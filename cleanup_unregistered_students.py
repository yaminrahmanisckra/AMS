#!/usr/bin/env python3
"""Cleanup unregistered students from Class Management sessions"""

from app import create_app
from extensions import db
from blueprints.class_management.models import Session, ClassStudent
from blueprints.course_management.models import StudentCourseRegistration
from blueprints.student_management.models import Student

def cleanup_unregistered_students():
    """Remove students from Class Management sessions who are not registered for the course"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Cleaning up unregistered students from Class Management")
        print("=" * 60)
        
        if not StudentCourseRegistration or not Student:
            print("❌ StudentCourseRegistration or Student model not available")
            return
        
        # Get all sessions
        sessions = Session.query.filter_by(archived=False).all()
        print(f"\nFound {len(sessions)} active sessions")
        
        total_removed = 0
        total_checked = 0
        
        for session in sessions:
            if not session.course_code or not session.academic_session or not session.year or not session.term:
                continue
            
            # Get all students in this session
            class_students = ClassStudent.query.filter_by(session_id=session.id).all()
            
            if not class_students:
                continue
            
            print(f"\n📚 Session: {session.course_code} - {session.course_name}")
            print(f"   Year: {session.year}, Term: {session.term}, Session: {session.academic_session}")
            print(f"   Students in session: {len(class_students)}")
            
            removed_from_session = 0
            
            for class_student in class_students:
                total_checked += 1
                
                # Get student record
                student = Student.query.filter_by(student_id=class_student.student_id).first()
                if not student:
                    print(f"   ⚠️  Student {class_student.student_id} not found in Students Management, skipping...")
                    continue
                
                # Check if student is registered for this course
                registration = StudentCourseRegistration.query.filter_by(
                    student_id=student.id,
                    course_code=session.course_code,
                    academic_session=session.academic_session,
                    year=session.year,
                    term=session.term,
                    status='finalized'
                ).first()
                
                if not registration:
                    print(f"   ❌ Removing unregistered student: {class_student.student_id} ({class_student.name})")
                    db.session.delete(class_student)
                    removed_from_session += 1
                    total_removed += 1
                else:
                    print(f"   ✅ Registered: {class_student.student_id} ({class_student.name})")
            
            if removed_from_session > 0:
                print(f"   🗑️  Removed {removed_from_session} unregistered student(s) from this session")
        
        if total_removed > 0:
            db.session.commit()
            print("\n" + "=" * 60)
            print(f"✅ Cleanup completed!")
            print(f"   Total students checked: {total_checked}")
            print(f"   Total unregistered students removed: {total_removed}")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("✅ No unregistered students found. All students are properly registered.")
            print("=" * 60)

if __name__ == '__main__':
    cleanup_unregistered_students()

