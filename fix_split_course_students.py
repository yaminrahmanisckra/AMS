#!/usr/bin/env python3
"""Fix missing students in split course peer sessions"""

from app import create_app
from extensions import db
from blueprints.class_management.models import Session, ClassStudent
from blueprints.course_management.models import StudentCourseRegistration
from blueprints.student_management.models import Student

def fix_split_course_students():
    """Replicate students to peer sessions in split courses"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Fixing missing students in split course peer sessions")
        print("=" * 60)
        
        # Get all sessions with split_group_id
        split_sessions = Session.query.filter(
            Session.split_group_id.isnot(None),
            Session.archived == False
        ).all()
        
        if not split_sessions:
            print("No split courses found.")
            return
        
        # Group sessions by split_group_id
        split_groups = {}
        for session in split_sessions:
            if session.split_group_id not in split_groups:
                split_groups[session.split_group_id] = []
            split_groups[session.split_group_id].append(session)
        
        print(f"\nFound {len(split_groups)} split course group(s)")
        
        total_fixed = 0
        
        for split_group_id, sessions in split_groups.items():
            print(f"\n📚 Split Course Group: {split_group_id}")
            print(f"   Sessions: {len(sessions)}")
            
            # Get all students from all sessions in this split group
            all_students_in_group = {}
            for session in sessions:
                students = ClassStudent.query.filter_by(session_id=session.id).all()
                for student in students:
                    if student.student_id not in all_students_in_group:
                        all_students_in_group[student.student_id] = {
                            'name': student.name,
                            'sessions': set()
                        }
                    all_students_in_group[student.student_id]['sessions'].add(session.id)
            
            print(f"   Total unique students: {len(all_students_in_group)}")
            
            # For each student, ensure they exist in all sessions
            for student_id, student_data in all_students_in_group.items():
                for session in sessions:
                    if session.id in student_data['sessions']:
                        continue  # Student already in this session
                    
                    # Check if student should be in this session (registered)
                    if StudentCourseRegistration and session.course_code and session.academic_session and session.year and session.term:
                        student_record = Student.query.filter_by(student_id=student_id).first()
                        if student_record:
                            registration = StudentCourseRegistration.query.filter_by(
                                student_id=student_record.id,
                                course_code=session.course_code,
                                academic_session=session.academic_session,
                                year=session.year,
                                term=session.term,
                                status='finalized'
                            ).first()
                            
                            if not registration:
                                continue  # Student not registered, skip
                    
                    # Add student to missing session
                    print(f"   ➕ Adding {student_id} ({student_data['name']}) to session {session.id} ({session.course_scope or 'Full'})")
                    class_student = ClassStudent(
                        student_id=student_id,
                        name=student_data['name'],
                        session_id=session.id,
                        teacher_id=session.teacher_id
                    )
                    db.session.add(class_student)
                    total_fixed += 1
        
        if total_fixed > 0:
            db.session.commit()
            print("\n" + "=" * 60)
            print(f"✅ Fixed {total_fixed} missing student(s) in split course peer sessions")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("✅ All split course students are properly replicated to peer sessions")
            print("=" * 60)

if __name__ == '__main__':
    fix_split_course_students()

