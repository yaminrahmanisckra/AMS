from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, send_file
from flask_login import login_required, current_user
from extensions import db
from sqlalchemy import func
from .models import Teacher, Room, AssignedCourse, Routine
from blueprints.course_management.models import Course, DutyAssignment
from .forms import TeacherForm, RoomForm, AssignCourseForm
from role_utils import parse_roles
from datetime import datetime
from collections import defaultdict
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
import sys
import random

routine_management_bp = Blueprint('routine_management', __name__,
                                  template_folder='templates',
                                  static_folder='static')

# Main dashboard for routine management
@routine_management_bp.route('/')
@login_required
def index():
    can_edit = can_edit_routine()
    # If user doesn't have Routine Maker assignment, redirect to view routine
    if not can_edit:
        return redirect(url_for('routine_management.view_routine'))
    return render_template('routine_management/index.html', can_edit=can_edit)

# Teacher Management
@routine_management_bp.route('/teachers', methods=['GET', 'POST'])
def manage_teachers():
    form = TeacherForm()
    if form.validate_on_submit():
        new_teacher = Teacher(name=form.name.data, short_name=form.short_name.data)
        db.session.add(new_teacher)
        db.session.commit()
        flash('Teacher added successfully!', 'success')
        return redirect(url_for('routine_management.manage_teachers'))
    # Get teachers excluding Head, Teaching Assistants, and Admin users
    from role_utils import get_teachers_excluding_head
    teachers = get_teachers_excluding_head()
    return render_template('routine_management/teachers.html', form=form, teachers=teachers)

@routine_management_bp.route('/teacher/edit/<int:id>', methods=['POST'])
def edit_teacher(id):
    from user_models import User
    
    teacher = Teacher.query.get_or_404(id)
    old_name = teacher.name  # Store old name for User lookup
    
    # Manually get data from the modal form
    new_name = request.form.get('name')
    new_short_name = request.form.get('short_name')

    if not new_name or not new_short_name:
        flash('Both name and short name are required.', 'danger')
        return redirect(url_for('routine_management.manage_teachers'))

    # Check for uniqueness
    existing_teacher = Teacher.query.filter(Teacher.short_name == new_short_name, Teacher.id != id).first()
    if existing_teacher:
        flash(f'The short name "{new_short_name}" is already taken.', 'danger')
        return redirect(url_for('routine_management.manage_teachers'))
    
    # Update teacher name and short_name
    teacher.name = new_name
    teacher.short_name = new_short_name
    
    # Update related User's full_name if name changed
    if old_name != new_name:
        # Find User by old name (exact match first)
        user = User.query.filter_by(full_name=old_name).first()
        if not user:
            # Try case-insensitive match
            user = User.query.filter(func.lower(User.full_name) == func.lower(old_name)).first()
        
        if user:
            user.full_name = new_name
            db.session.add(user)
        else:
            # If no user found, try to find by teacher name pattern
            # This handles cases where user might have been created differently
            pass
    
    db.session.commit()
    flash('Teacher updated successfully!', 'success')
    return redirect(url_for('routine_management.manage_teachers'))

@routine_management_bp.route('/teacher/delete/<int:id>', methods=['POST'])
@login_required
def delete_teacher(id):
    """Delete a teacher and all related data"""
    teacher = Teacher.query.get_or_404(id)
    
    try:
        # Import necessary models
        from blueprints.class_management.models import (
            Session, ClassStudent, ClassAttendance, CourseReview, 
            EvaluationInvite, EvaluationSubmission, StudentFeedbackLink, 
            StudentFeedbackResponse, ClassSplitInvite, CourseOutline
        )
        try:
            from blueprints.academic_calendar.models import BatchCustomEvent
        except ImportError:
            BatchCustomEvent = None
        
        # Delete assigned courses
        AssignedCourse.query.filter_by(teacher_id=id).delete(synchronize_session=False)
        
        # Delete routine entries
        Routine.query.filter_by(teacher_id=id).delete(synchronize_session=False)
        
        # Delete class sessions and their related data
        sessions = Session.query.filter_by(teacher_id=id).all()
        for session in sessions:
            session_id = session.id
            
            # Delete all related records for this session
            # 1. Delete student feedback responses first
            feedback_link_ids = [link.id for link in StudentFeedbackLink.query.filter_by(session_id=session_id).all()]
            if feedback_link_ids:
                StudentFeedbackResponse.query.filter(
                    StudentFeedbackResponse.feedback_link_id.in_(feedback_link_ids)
                ).delete(synchronize_session=False)
            
            # 2. Delete student feedback links
            StudentFeedbackLink.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 3. Delete batch custom events (if model exists)
            if BatchCustomEvent:
                BatchCustomEvent.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 4. Delete course outline
            CourseOutline.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 5. Delete evaluation submissions
            EvaluationSubmission.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 6. Delete evaluation invites
            EvaluationInvite.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 7. Delete course reviews
            CourseReview.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 8. Delete split course invites (where this session is the inviter)
            ClassSplitInvite.query.filter_by(inviter_session_id=session_id).delete(synchronize_session=False)
            
            # 9. Delete attendance records
            ClassAttendance.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 10. Delete student records
            ClassStudent.query.filter_by(session_id=session_id).delete(synchronize_session=False)
            
            # 11. Delete the session
            db.session.delete(session)
        
        # Now delete the teacher
        db.session.delete(teacher)
        db.session.commit()
        flash('Teacher and all related data deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting teacher {id}: {e}', exc_info=True)
        flash(f'Error deleting teacher: {str(e)}', 'danger')
    
    return redirect(url_for('routine_management.manage_teachers'))

# Course Management routes removed - now handled by course_management blueprint

# Room Management
@routine_management_bp.route('/rooms', methods=['GET', 'POST'])
def manage_rooms():
    form = RoomForm()
    if form.validate_on_submit():
        new_room = Room(room_number=form.room_number.data)
        db.session.add(new_room)
        db.session.commit()
        flash('Room added successfully!', 'success')
        return redirect(url_for('routine_management.manage_rooms'))
    rooms = Room.query.order_by('room_number').all()
    return render_template('routine_management/rooms.html', form=form, rooms=rooms)

@routine_management_bp.route('/room/delete/<int:id>', methods=['POST'])
@login_required
def delete_room(id):
    """Delete a room"""
    try:
        room = Room.query.get_or_404(id)
        room_number = room.room_number
        db.session.delete(room)
        db.session.commit()
        flash(f'Room {room_number} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting room {id}: {e}', exc_info=True)
        flash(f'Error deleting room: {str(e)}', 'danger')
    return redirect(url_for('routine_management.manage_rooms'))

# Course Assignment
@routine_management_bp.route('/assign_course', methods=['GET', 'POST'])
def assign_course():
    form = AssignCourseForm()
    from role_utils import get_teachers_excluding_head
    form.teacher.choices = [(t.id, f"{t.name} ({t.short_name})") for t in get_teachers_excluding_head()]

    # Centralized logic to get available courses
    all_assignments = AssignedCourse.query.all()
    assigned_parts_by_course = defaultdict(set)
    for a in all_assignments:
        assigned_parts_by_course[a.course_id].add(a.part)

    fully_assigned_course_ids = {
        cid for cid, parts in assigned_parts_by_course.items()
        if 'Full' in parts or {'Part A', 'Part B'}.issubset(parts)
    }
    
    available_courses = Course.query.filter(Course.id.notin_(fully_assigned_course_ids)).order_by('course_code').all()
    form.course.choices = [(c.id, f"{c.course_code} - {c.course_name}") for c in available_courses]
    form.part.choices = [('Full', 'Full Course'), ('Part A', 'Part A'), ('Part B', 'Part B')]

    if form.validate_on_submit():
        course_id = form.course.data
        part = form.part.data

        # Re-check availability before committing
        current_parts = assigned_parts_by_course.get(course_id, set())
        
        # Check if the selected part is already taken
        if part in current_parts:
            flash(f'Error: "{part}" of this course is already assigned.', 'danger')
            return redirect(url_for('routine_management.assign_course'))

        # Check if trying to assign a part when 'Full' is taken
        if 'Full' in current_parts:
            flash('Error: This course is already assigned as "Full".', 'danger')
            return redirect(url_for('routine_management.assign_course'))

        # Check if trying to assign 'Full' when parts are taken
        if part == 'Full' and len(current_parts) > 0:
            flash('Error: Cannot assign as "Full" because parts are already assigned.', 'danger')
            return redirect(url_for('routine_management.assign_course'))
        
        assignment = AssignedCourse(
            teacher_id=form.teacher.data,
            course_id=course_id,
            part=part
        )
        db.session.add(assignment)
        db.session.commit()
        flash('Course assigned successfully!', 'success')
        return redirect(url_for('routine_management.assign_course'))

    # Logic to display existing assignments
    assignments_by_teacher = defaultdict(lambda: {'assignments': [], 'total_credit': 0.0})
    all_assignments_sorted = AssignedCourse.query.join(Teacher).order_by(Teacher.name, AssignedCourse.id.desc()).all()

    for assignment in all_assignments_sorted:
        teacher_id = assignment.teacher.id
        teacher_info = f"{assignment.teacher.name} ({assignment.teacher.short_name})"
        
        credit = float(assignment.course.credit)
        if assignment.part in ['Part A', 'Part B']:
            credit /= 2.0

        assignments_by_teacher[teacher_id]['teacher_info'] = teacher_info
        assignments_by_teacher[teacher_id]['assignments'].append({
            'assignment_obj': assignment,
            'credit': credit
        })
        assignments_by_teacher[teacher_id]['total_credit'] += credit

    assignments_grouped = dict(assignments_by_teacher)
    return render_template('routine_management/assign_course.html', form=form, assignments_grouped=assignments_grouped)


@routine_management_bp.route('/assignment/edit/<int:id>', methods=['GET', 'POST'])
def edit_assignment(id):
    assignment = AssignedCourse.query.get_or_404(id)
    form = AssignCourseForm(obj=assignment)
    from role_utils import get_teachers_excluding_head
    form.teacher.choices = [(t.id, f"{t.name} ({t.short_name})") for t in get_teachers_excluding_head()]
    form.course.choices = [(assignment.course.id, f"{assignment.course.course_code} - {assignment.course.course_name}")]

    other_assignments = AssignedCourse.query.filter(
        AssignedCourse.course_id == assignment.course_id,
        AssignedCourse.id != assignment.id
    ).all()
    other_assigned_parts = {a.part for a in other_assignments}

    available_parts = {'Full', 'Part A', 'Part B'}
    if 'Full' in other_assigned_parts:
        available_parts = set()
    elif 'Part A' in other_assigned_parts:
        available_parts.discard('Full')
        available_parts.discard('Part A')
    elif 'Part B' in other_assigned_parts:
        available_parts.discard('Full')
        available_parts.discard('Part B')

    available_parts.add(assignment.part)
    form.part.choices = sorted(list(available_parts))
    
    if form.validate_on_submit():
        new_part = form.part.data
        if new_part != assignment.part and new_part in other_assigned_parts:
            flash(f'The selected part "{new_part}" is already assigned.', 'danger')
            return render_template('routine_management/edit_assignment.html', form=form, assignment_id=id)
        
        assignment.teacher_id = form.teacher.data
        assignment.part = new_part
        db.session.commit()
        flash('Assignment updated successfully!', 'success')
        return redirect(url_for('routine_management.assign_course'))

    form.teacher.data = assignment.teacher_id
    form.course.data = assignment.course_id
    form.part.data = assignment.part
    return render_template('routine_management/edit_assignment.html', form=form, assignment_id=id)

@routine_management_bp.route('/assignment/delete/<int:id>', methods=['POST'])
@login_required
def delete_assignment(id):
    """Delete a course assignment"""
    try:
        assignment = AssignedCourse.query.get_or_404(id)
        course_code = assignment.course.course_code if assignment.course else 'Unknown'
        teacher_name = assignment.teacher.name if assignment.teacher else 'Unknown'
        db.session.delete(assignment)
        db.session.commit()
        flash(f'Course assignment ({course_code} - {teacher_name}) deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting assignment {id}: {e}', exc_info=True)
        flash(f'Error deleting assignment: {str(e)}', 'danger')
    return redirect(url_for('routine_management.assign_course'))

def can_edit_routine():
    """Check if current user can edit routine - Only Routine Maker assignment holders can edit. Others can only view and download."""
    if not current_user.is_authenticated:
        return False
    
    # Check if user has Routine Maker assignment
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if teacher:
        from blueprints.course_management.models import DutyAssignment
        routine_maker = DutyAssignment.query.filter_by(
            assigned_teacher_id=teacher.id,
            duty_type='routine_maker',
            status='active'
        ).first()
        if routine_maker:
            return True
    
    # No Routine Maker assignment - user can only view, not edit
    return False

@routine_management_bp.route('/api/check-edit-permission')
@login_required
def check_edit_permission():
    """Debug endpoint to check routine edit permission"""
    from blueprints.class_management.models import Teacher
    from user_models import User
    
    result = {
        'user': current_user.full_name,
        'username': current_user.username,
        'roles': parse_roles(current_user.role),
        'can_edit': can_edit_routine(),
        'teacher_found': False,
        'teacher_id': None,
        'teacher_name': None,
        'routine_maker_assignment': None,
        'discipline_head_assignment': None
    }
    
    try:
        teacher = Teacher.query.filter_by(name=current_user.full_name).first()
        if not teacher:
            teacher = Teacher.query.filter(
                func.lower(Teacher.name) == func.lower(current_user.full_name.strip())
            ).first()
        if not teacher:
            teacher = Teacher.query.filter(
                Teacher.name.like(f"%{current_user.full_name.strip()}%")
            ).first()
        
        if teacher:
            result['teacher_found'] = True
            result['teacher_id'] = teacher.id
            result['teacher_name'] = teacher.name
            
            # Check routine_maker assignment
            routine_maker = DutyAssignment.query.filter(
                DutyAssignment.assigned_teacher_id == teacher.id,
                DutyAssignment.duty_type == 'routine_maker',
                DutyAssignment.status == 'active'
            ).first()
            
            if routine_maker:
                result['routine_maker_assignment'] = {
                    'id': routine_maker.id,
                    'assigned_by_id': routine_maker.assigned_by_id,
                    'status': routine_maker.status,
                    'created_at': routine_maker.created_at.isoformat() if routine_maker.created_at else None
                }
            
            # Check discipline head assignment
            discipline_head = DutyAssignment.query.filter(
                DutyAssignment.assigned_teacher_id == teacher.id,
                DutyAssignment.status == 'active',
                DutyAssignment.assigned_by_id.isnot(None)
            ).first()
            
            if discipline_head:
                result['discipline_head_assignment'] = {
                    'id': discipline_head.id,
                    'duty_type': discipline_head.duty_type,
                    'assigned_by_id': discipline_head.assigned_by_id,
                    'status': discipline_head.status
                }
    except Exception as e:
        result['error'] = str(e)
    
    return jsonify(result)

# View Routine (for students and view-only access)
@routine_management_bp.route('/view_routine')
@login_required
def view_routine():
    """View routine - accessible to all users, but only teachers/TAs can edit"""
    from role_utils import get_teachers_excluding_head
    from blueprints.course_management.models import CourseSessionAssignment, Curriculum
    
    # Get all teachers (for display purposes)
    teachers_list = get_teachers_excluding_head()
    teachers = [{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in teachers_list]
    
    # Get all curricula for selection
    curricula = Curriculum.query.order_by(Curriculum.name.desc()).all()
    
    rooms = Room.query.order_by('room_number').all()
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]
    can_edit = can_edit_routine()
    return render_template('routine_management/routine_new.html', 
                           teachers=teachers, rooms=rooms, days=days, 
                           time_slots=time_slots, curricula=curricula,
                           can_edit=can_edit)

# Generate Routine
@routine_management_bp.route('/generate_routine')
@login_required
def generate_routine():
    from role_utils import get_teachers_excluding_head
    from blueprints.course_management.models import CourseSessionAssignment, Curriculum
    
    # Get all teachers
    teachers_list = get_teachers_excluding_head()
    teachers = [{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in teachers_list]
    
    # Get all curricula for selection
    curricula = Curriculum.query.order_by(Curriculum.name.desc()).all()
    
    rooms = Room.query.order_by('room_number').all()
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]
    can_edit = can_edit_routine()
    return render_template('routine_management/routine_new.html', 
                           teachers=teachers, rooms=rooms, days=days, 
                           time_slots=time_slots, curricula=curricula,
                           can_edit=can_edit)

# --- API Endpoints for Routine ---

@routine_management_bp.route('/api/teacher_courses/<int:teacher_id>')
@login_required
def teacher_courses(teacher_id):
    """Get courses assigned to teacher from curriculum (CourseSessionAssignment) - Simplified version"""
    from blueprints.course_management.models import CourseSessionAssignment
    from blueprints.class_management.models import Teacher
    
    courses_data = []

    try:
        # Verify teacher exists
        teacher = Teacher.query.get(teacher_id)
        if not teacher:
            return jsonify([])
        
        # Get all CourseSessionAssignment for this teacher (no filters for now)
        assignments = CourseSessionAssignment.query.filter_by(teacher_id=teacher_id).all()
        
        for assignment in assignments:
            # Skip if assignment or course is missing
            if not assignment or not hasattr(assignment, 'course') or not assignment.course:
                continue
            
            # Get basic course info
            course = assignment.course
            course_code = getattr(course, 'course_code', '') or ''
            course_name = getattr(course, 'course_name', '') or ''
            course_type = getattr(course, 'course_type', 'Theory') or 'Theory'
            course_credit = float(getattr(course, 'credit', 0) or 0)
            
            # Get section info
            section = getattr(assignment, 'section', None)
            if section not in ['A', 'B']:
                section = 'Full'
            
            part_display = f'Part {section}' if section in ['A', 'B'] else 'Full'
            
            # Get teacher info
            teacher_obj = assignment.teacher if hasattr(assignment, 'teacher') else teacher
            teacher_short = getattr(teacher_obj, 'call_sign', None) or getattr(teacher_obj, 'short_name', '') or ''
            teacher_name = getattr(teacher_obj, 'name', '') or ''
            teacher_id_val = getattr(teacher_obj, 'id', None)
            
            # Calculate classes per week
            if course_type == 'Sessional':
                total_classes = int(course_credit * 2)
            else:
                total_classes = int(course_credit)
            
            if section in ['A', 'B']:
                classes_per_week = (total_classes + 1) // 2
            else:
                classes_per_week = total_classes
            
            # Get year and term from assignment
            year = getattr(assignment, 'year', '') or ''
            term = getattr(assignment, 'term', '') or ''
            
            # Create course entry
            course_entry = {
                'assigned_id': str(assignment.id),
                'course_code': course_code,
                'course_name': course_name,
                'course_type': course_type,
                'credit': course_credit,
                'part': part_display,
                'classes_per_week': classes_per_week,
                'is_shared_slot': False,
                'teacher_id': teacher_id_val,
                'year': year,
                'term': term,
                'teachers': [{
                    'id': teacher_id_val,
                    'name': teacher_name,
                    'short_name': teacher_short
                }]
            }
            
            courses_data.append(course_entry)

            # Handle shared courses (3-credit courses with Part A and Part B)
            if course_credit == 3.0 and section == 'A':
                # Check if there's a Part B assignment for the same course
                other_assignment = CourseSessionAssignment.query.filter(
                    CourseSessionAssignment.course_id == assignment.course_id,
                    CourseSessionAssignment.section == 'B',
                    CourseSessionAssignment.curriculum_id == assignment.curriculum_id,
                    CourseSessionAssignment.academic_session == assignment.academic_session
                ).first()

                if other_assignment and hasattr(other_assignment, 'teacher') and other_assignment.teacher:
                    other_teacher = other_assignment.teacher
                    other_teacher_short = getattr(other_teacher, 'call_sign', None) or getattr(other_teacher, 'short_name', '') or ''
                    other_teacher_name = getattr(other_teacher, 'name', '') or ''
                    other_teacher_id = getattr(other_teacher, 'id', None)
                    
                    # Get year and term for shared entry
                    year = getattr(assignment, 'year', '') or ''
                    term = getattr(assignment, 'term', '') or ''
                    
                    # Add shared course entry
                    shared_entry = {
                        'assigned_id': str(assignment.id),
                        'course_code': course_code,
                        'course_name': f"{course_name} (Shared)",
                        'course_type': course_type,
                        'credit': course_credit,
                        'part': 'Shared',
                        'classes_per_week': 1,
                        'is_shared_slot': True,
                        'teacher_id': teacher_id_val,
                        'year': year,
                        'term': term,
                        'teachers': [
                            {
                                'id': teacher_id_val,
                                'name': teacher_name,
                                'short_name': teacher_short
                            },
                            {
                                'id': other_teacher_id,
                                'name': other_teacher_name,
                                'short_name': other_teacher_short
                            }
                        ]
                    }
                    courses_data.append(shared_entry)
        
        return jsonify(courses_data)
        
    except Exception as e:
        # Log error
        try:
            from flask import current_app
            current_app.logger.error(f'Error in teacher_courses API for teacher_id {teacher_id}: {e}', exc_info=True)
        except:
            pass
        # Return empty array on any error
        return jsonify([])

@routine_management_bp.route('/api/get_teachers')
def get_teachers():
    from role_utils import get_teachers_excluding_head
    teachers_list = get_teachers_excluding_head()
    return jsonify([{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in teachers_list])

@routine_management_bp.route('/api/routine/save', methods=['POST'])
@login_required
def save_routine():
    if not can_edit_routine():
        return jsonify({'message': 'You do not have permission to edit routine.'}), 403
    
    data = request.get_json()
    
    Routine.query.delete()
    
    routine_entries = data.get('routine', [])
    for entry in routine_entries:
        # Find room number from room_id
        room = Room.query.get(entry.get('room_id'))
        if not room:
            continue # Or handle error

        new_entry = Routine(
            day=entry.get('day'),
            time_slot=entry.get('slot'), # Corrected: slot -> time_slot
            room_number=room.room_number, # Save room_number, not id
            course_code=entry.get('course_code'),
            teacher_short_name=entry.get('teacher_short_name'),
            part=entry.get('part'),
            is_shared=entry.get('is_shared', False),
            shared_with=entry.get('shared_with'),
            teacher_id=entry.get('teacher_id'),
            year=entry.get('year', '') or '',  # Save year for color coding
            term=entry.get('term', '') or ''   # Save term for color coding
        )
        db.session.add(new_entry)
    
    db.session.commit()
    # Emit WebSocket event for live update
    try:
        from utils.websocket_events import emit_routine_updated
        emit_routine_updated({'updated_at': datetime.utcnow().isoformat()})
    except Exception as e:
        current_app.logger.warning(f'Failed to emit routine update event: {e}')
    return jsonify({'message': 'Routine saved successfully!'}), 200

@routine_management_bp.route('/api/routine/clear', methods=['POST'])
@login_required
def clear_routine():
    if not can_edit_routine():
        return jsonify({'message': 'You do not have permission to clear routine.'}), 403
    
    try:
        Routine.query.delete()
        db.session.commit()
        return jsonify({'message': 'Routine cleared successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 500

@routine_management_bp.route('/api/routine/load')
def load_routine():
    routine_entries = Routine.query.all()
    all_rooms = {r.room_number: r.id for r in Room.query.all()}

    routine_data = []
    scheduled_courses = set()
    for entry in routine_entries:
        # Track scheduled course codes
        if entry.course_code:
            scheduled_courses.add(entry.course_code)
        teachers_info = []
        if entry.is_shared and entry.shared_with:
            short_names = [name.strip() for name in entry.shared_with.split('/')]
            all_involved_teachers = Teacher.query.filter(Teacher.short_name.in_(short_names)).all()
            teachers_info = [{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in all_involved_teachers]
        elif entry.teacher_id:
            teacher = Teacher.query.get(entry.teacher_id)
            if teacher:
                teachers_info = [{'id': teacher.id, 'name': teacher.name, 'short_name': teacher.call_sign or teacher.short_name}]

        # Get year and term from saved Routine entry first, fallback to CourseSessionAssignment
        year = ''
        term = ''
        if hasattr(entry, 'year') and entry.year:
            year = str(entry.year).strip()
        if hasattr(entry, 'term') and entry.term:
            term = str(entry.term).strip()
        
        # If not saved in Routine, try to get from CourseSessionAssignment
        if not year or not term:
            if entry.teacher_id and entry.course_code:
                try:
                    from blueprints.course_management.models import CourseSessionAssignment, Course
                    # First find the course by course_code
                    course = Course.query.filter_by(course_code=entry.course_code).first()
                    if course:
                        # Then find the assignment for this teacher and course
                        assignment = CourseSessionAssignment.query.filter_by(
                            teacher_id=entry.teacher_id,
                            course_id=course.id
                        ).first()
                        if assignment:
                            year_val = getattr(assignment, 'year', None)
                            term_val = getattr(assignment, 'term', None)
                            if not year and year_val is not None:
                                year = str(year_val).strip()
                            if not term and term_val is not None:
                                term = str(term_val).strip()
                except Exception as e:
                    # Log error but continue
                    try:
                        from flask import current_app
                        current_app.logger.error(f'Error getting year/term for routine entry: {e}')
                    except:
                        pass

        routine_data.append({
            "day": entry.day,
            "slot": entry.time_slot,
            "room_id": all_rooms.get(entry.room_number),
            "course_code": entry.course_code,
            "teacher_short_name": entry.teacher_short_name,
            "part": entry.part,
            "is_shared": entry.is_shared,
            "shared_with": entry.shared_with,
            "teacher_id": entry.teacher_id,
            "year": year,
            "term": term,
            "teachers": teachers_info
        })

    return jsonify({
        'routine': routine_data,
        'scheduled_courses': list(scheduled_courses)
    })

@routine_management_bp.route('/download_pdf', methods=['POST'])
@login_required
def download_pdf():
    try:
        # PDF download is view-only, so no permission check needed
        data = request.get_json() or {}
        routine_list = data.get('routine', [])
        title_text = request.args.get('title', 'Class Routine')
        date_text = request.args.get('date', '')

        # Create a mapping from the list for easy lookup
        # Use day, slot (which may be edited), and room_id as key
        routine_map = {}
        for item in routine_list:
            key = (item['day'], item['slot'], item['room_id'])
            routine_map[key] = item

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(legal),
                                leftMargin=0.3*inch, rightMargin=0.3*inch,
                                topMargin=0.2*inch, bottomMargin=0.2*inch)
        
        styles = getSampleStyleSheet()
        h1_centered = ParagraphStyle(name='h1_centered', parent=styles['h1'], alignment=TA_CENTER, fontSize=14)
        h2_centered = ParagraphStyle(name='h2_centered', parent=styles['h2'], alignment=TA_CENTER, fontSize=12)
        h3_centered = ParagraphStyle(name='h3_centered', parent=styles['h3'], alignment=TA_CENTER, fontSize=11)
        
        body_text_style = ParagraphStyle(name='BodyText', parent=styles['Normal'], alignment=TA_CENTER, fontSize=7.5, leading=8.5)

        elements = []
        
        formatted_date = ''
        if date_text:
            try:
                dt = datetime.strptime(date_text, '%Y-%m-%d')
                formatted_date = dt.strftime('%d-%m-%Y')
            except ValueError:
                formatted_date = date_text # Fallback to raw date

        elements.append(Paragraph("Khulna University", h1_centered))
        elements.append(Paragraph("Law Discipline", h2_centered))
        elements.append(Paragraph(title_text, h3_centered))
        if formatted_date:
            elements.append(Paragraph(f"Effective from {formatted_date}", h3_centered))
        elements.append(Spacer(1, 0.08*inch))

        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
        
        # Get time slots from request (edited headers) or use default
        time_slots_from_request = request.args.getlist('time_slots')
        if time_slots_from_request:
            time_slots = time_slots_from_request
        else:
            # Default time slots
            time_slots = [
                "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
                "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
                "04:00 PM - 04:50 PM"
            ]
        
        lunch_time = "01:00 PM - 01:50 PM"
        rooms_db = Room.query.order_by('room_number').all()
        
        # Prepare header: Day, Room, then time slots with lunch inserted
        header = ['Day', 'Room']
        
        # Find lunch position (usually after 4th slot or where "01:00" appears)
        lunch_inserted = False
        for idx, slot in enumerate(time_slots):
            # Insert lunch before slot containing "01:00" or "12:10 PM - 01:00 PM"
            if not lunch_inserted and ('01:00' in slot or '12:10 PM - 01:00 PM' in slot):
                header.append(lunch_time.replace(' - ', '\n') + '\nLunch')
                lunch_inserted = True
            header.append(slot.replace(' - ', '\n'))
        
        # If lunch wasn't inserted, add it after 4th slot (default behavior)
        if not lunch_inserted and len(header) > 6:
            header.insert(6, lunch_time.replace(' - ', '\n') + '\nLunch')
        
        table_data = [header]

        # Data rows
        for day in days:
            for i, room in enumerate(rooms_db):
                row = []
                if i == 0:
                    row.append(Paragraph(f"<b>{day}</b>", body_text_style))
                else:
                    row.append("")
                row.append(Paragraph(str(room.room_number), body_text_style))
                
                # Insert lunch and time slots
                lunch_inserted = False
                for idx, slot in enumerate(time_slots):
                    # Insert lunch before slot containing "01:00" or "12:10 PM - 01:00 PM"
                    if not lunch_inserted and ('01:00' in slot or '12:10 PM - 01:00 PM' in slot):
                        row.append(Paragraph("LUNCH", body_text_style))
                        lunch_inserted = True
                    
                    # Find cell data - match by day, slot (which may have been edited), and room_id
                    cell_data = routine_map.get((day, slot, room.id))
                    
                    if cell_data:
                        cell_content = f"<b>{cell_data.get('course_code', '')}</b><br/>({cell_data.get('teacher_short_name', '')})"
                        row.append(Paragraph(cell_content, body_text_style))
                    else:
                        row.append("")
                
                # If lunch wasn't inserted, add it after 4th slot (default behavior)
                if not lunch_inserted and len(row) > 6:
                    row.insert(6, Paragraph("LUNCH", body_text_style))
                
                table_data.append(row)

        # Calculate column widths (now 15% wider than previous)
        col_widths = [0.72*1.3*1.15*inch, 0.72*1.3*1.15*inch]
        for idx in range(len(time_slots) + 1):  # +1 for lunch
            col_widths.append(0.9*1.3*1.15*inch)

        table = Table(table_data, colWidths=col_widths)
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('BACKGROUND', (0, 1), (0, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2.2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ])

        # Row span for Day column
        num_rooms = len(rooms_db) if rooms_db else 1
        for i, day in enumerate(days):
            start_row = 1 + (i * num_rooms)
            end_row = start_row + num_rooms - 1
            if num_rooms > 1:
                style.add('SPAN', (0, start_row), (0, end_row))
                style.add('VALIGN', (0, start_row), (0, end_row), 'MIDDLE')
            # Thick border above each day's first row
            if start_row > 1:
                style.add('LINEABOVE', (0, start_row), (-1, start_row), 2, colors.black)

        table.setStyle(style)
        elements.append(table)
        
        doc.build(elements)
        
        buffer.seek(0)
        
        # Enhanced headers for cPanel compatibility
        pdf_data = buffer.getvalue()
        filename = f'routine_{title_text.replace(" ", "_")}.pdf'
        
        response = Response(
            pdf_data,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}',
                'Content-Length': str(len(pdf_data)),
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY'
            }
        )
        
        return response
        
    except Exception as e:
        import traceback
        error_msg = f"PDF generation error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Log to server console
        return jsonify({'error': str(e), 'details': error_msg}), 500

@routine_management_bp.route('/download_teacher_wise_pdf')
def download_teacher_wise_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(name='Title', parent=styles['Title'], alignment=TA_CENTER)
    elements = []
    elements.append(Paragraph('Teacher-wise Course Assignment', style_title))
    elements.append(Spacer(1, 0.2*inch))
    from role_utils import get_teachers_excluding_head
    teachers = get_teachers_excluding_head()
    for teacher in teachers:
        assignments = AssignedCourse.query.filter_by(teacher_id=teacher.id).all()
        if not assignments:
            continue
        elements.append(Paragraph(f"<b>{teacher.name} ({teacher.call_sign or teacher.short_name})</b>", styles['Heading2']))
        data = [["Course Name", "Code", "Part", "Credit"]]
        for a in assignments:
            data.append([
                a.course.course_name,
                a.course.course_code,
                a.part,
                f"{a.course.credit:.2f}" if a.part == 'Full' else f"{float(a.course.credit)/2:.2f}"
            ])
        table = Table(data, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        elements.append(PageBreak())
    doc.build(elements)
    buffer.seek(0)
    
    # Enhanced headers for cPanel compatibility
    pdf_data = buffer.getvalue()
    filename = 'teacher_wise_assignment.pdf'
    
    response = Response(
        pdf_data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}',
            'Content-Length': str(len(pdf_data)),
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY'
        }
    )
    
    return response

@routine_management_bp.route('/download_course_wise_pdf')
def download_course_wise_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(name='Title', parent=styles['Title'], alignment=TA_CENTER)
    elements = []
    elements.append(Paragraph('Course-wise Teacher Assignment', style_title))
    elements.append(Spacer(1, 0.2*inch))
    data = [["Course Name", "Teacher Names", "Call Signs"]]
    courses = Course.query.order_by(Course.course_code).all()
    for course in courses:
        assignments = AssignedCourse.query.filter_by(course_id=course.id).all()
        if not assignments:
            continue
        teacher_names = ', '.join([a.teacher.name for a in assignments])
        call_signs = ', '.join([a.teacher.call_sign or a.teacher.short_name for a in assignments])
        data.append([f"{course.course_code} - {course.course_name}", teacher_names, call_signs])
    table = Table(data, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    
    # Enhanced headers for cPanel compatibility
    pdf_data = buffer.getvalue()
    filename = 'course_wise_assignment.pdf'
    
    response = Response(
        pdf_data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"; filename*=UTF-8\'\'{filename}',
            'Content-Length': str(len(pdf_data)),
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY'
        }
    )
    
    return response
