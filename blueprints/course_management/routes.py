from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from extensions import db
from . import course_management_bp
from .models import Curriculum, Course, StudentCourseRegistration, CourseRegistrationInvite, DutyAssignment, CurriculumYearTerm, CourseSessionAssignment
from .forms import CurriculumForm, CourseForm, CourseInfoForm
from blueprints.student_management.models import Student
from blueprints.class_management.models import Session, Teacher, ClassStudent
from role_utils import parse_roles
from user_models import User
from sqlalchemy import or_
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage
import os
from datetime import datetime


def _get_current_student_record():
    username = getattr(current_user, 'username', None)
    if not username:
        return None
    return Student.query.filter_by(student_id=username).first()

def _get_teachers_excluding_head():
    """Get all teachers excluding Head of the Discipline"""
    try:
        from blueprints.class_management.models import Teacher
        if not Teacher:
            return []
        
        # Get all teachers
        all_teachers = Teacher.query.order_by(Teacher.name).all()
        
        # Get Head of the Discipline users
        head_users = User.query.filter(
            or_(
                User.role.like('%head%'),
                User.role == 'head'
            )
        ).all()
        head_names = {user.full_name for user in head_users}
        
        # Filter out Head of the Discipline from teachers list
        teachers = [teacher for teacher in all_teachers if teacher.name not in head_names]
        return teachers
    except ImportError:
        return []
    except Exception as e:
        current_app.logger.warning(f'Error filtering teachers: {e}')
        # Fallback: get all teachers if filtering fails
        try:
            from blueprints.class_management.models import Teacher
            return Teacher.query.order_by(Teacher.name).all() if Teacher else []
        except:
            return []


def infer_year_and_term(course_code: str):
    """Infer academic year and term from course code (uses last 4 digits)."""
    if not course_code:
        return '', ''
    
    digits = ''.join(ch for ch in course_code if ch.isdigit())
    if len(digits) < 4:
        return '', ''
    
    relevant = digits[-4:]
    year_digit = relevant[0]
    term_digit = relevant[1]
    
    year_map = {
        '1': 'First',
        '2': 'Second',
        '3': 'Third',
        '4': 'Fourth',
        '5': 'LLM'
    }
    term_map = {
        '1': 'First',
        '2': 'Second'
    }
    return year_map.get(year_digit, ''), term_map.get(term_digit, '')

def get_available_batches(exclude_curriculum_id=None):
    """Get all distinct batches from Student model that are not already assigned to any curriculum"""
    # Get all batches from Student model
    all_batches = db.session.query(Student.batch).distinct().filter(Student.batch.isnot(None)).order_by(Student.batch.desc()).all()
    all_batch_values = [batch[0] for batch in all_batches if batch[0]]
    
    # Get all batches that are already assigned to curricula
    assigned_batches = set()
    curricula = Curriculum.query.all()
    for curriculum in curricula:
        # Skip the current curriculum if we're editing it
        if exclude_curriculum_id and curriculum.id == exclude_curriculum_id:
            continue
        if curriculum.applicable_batches:
            batches_list = curriculum.get_batches_list()
            assigned_batches.update(batches_list)
    
    # Filter out assigned batches
    available_batches = [batch for batch in all_batch_values if batch not in assigned_batches]
    
    return [(batch, batch) for batch in available_batches]

@course_management_bp.route('/')
@login_required
def index():
    """List all curricula"""
    curricula = Curriculum.query.order_by(Curriculum.created_at.desc()).all()
    curriculum_form = CurriculumForm()
    curriculum_form.applicable_batches.choices = get_available_batches()
    return render_template('course_management/index.html', curricula=curricula, curriculum_form=curriculum_form)

@course_management_bp.route('/curriculum/<int:curriculum_id>')
@login_required
def view_curriculum(curriculum_id):
    """View courses in a specific curriculum"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    courses = Course.query.filter_by(curriculum_id=curriculum_id).order_by('course_code').all()
    course_form = CourseForm()
    curriculum_form = CurriculumForm()
    curriculum_form.applicable_batches.choices = get_available_batches()
    
    # Create edit form for this curriculum
    edit_curriculum_form = CurriculumForm()
    edit_curriculum_form.applicable_batches.choices = get_available_batches(exclude_curriculum_id=curriculum_id)
    # Include batches already assigned to this curriculum
    existing_batches = curriculum.get_batches_list()
    for batch in existing_batches:
        if (batch, batch) not in edit_curriculum_form.applicable_batches.choices:
            edit_curriculum_form.applicable_batches.choices.append((batch, batch))
    # Populate with existing data
    edit_curriculum_form.name.data = curriculum.name
    edit_curriculum_form.date.data = curriculum.date
    edit_curriculum_form.applicable_batches.data = existing_batches
    
    curricula = Curriculum.query.order_by(Curriculum.created_at.desc()).all()
    
    # Group courses by Year and Term
    courses_by_year_term = {}
    for course in courses:
        year = course.display_year or 'Unspecified Year'
        term = course.display_term or 'Unspecified Term'
        key = (year, term)
        if key not in courses_by_year_term:
            courses_by_year_term[key] = []
        courses_by_year_term[key].append(course)
    
    # Sort the groups: First by year (First, Second, Third, Fourth, LLM), then by term (First, Second)
    year_order = {'First': 1, 'Second': 2, 'Third': 3, 'Fourth': 4, 'LLM': 5, 'Unspecified Year': 99}
    term_order = {'First': 1, 'Second': 2, 'Thesis Term': 3, 'Unspecified Term': 99}
    
    sorted_groups = sorted(courses_by_year_term.items(), 
                          key=lambda x: (year_order.get(x[0][0], 99), term_order.get(x[0][1], 99)))
    
    # Create CourseInfoForm instances for each course for CSRF token
    course_info_forms = {}
    for course in courses:
        form = CourseInfoForm()
        # Populate form fields with existing data
        form.year.data = course.year
        form.term.data = course.term
        form.rationale.data = course.rationale
        form.content_section_a.data = course.content_section_a
        form.content_section_b.data = course.content_section_b
        form.clos_json.data = course.clo  # Store JSON string
        course_info_forms[course.id] = form
    
    # Get batches for dropdown - only show batches applicable to this curriculum + "None" option
    curriculum_batches = curriculum.get_batches_list() if curriculum else []
    
    # Get teachers for assignment dropdown (exclude Head of the Discipline)
    teachers = _get_teachers_excluding_head()
    
    # Get existing session assignments for courses
    course_assignments = {}
    teacher_map = {}
    try:
        from .models import CourseSessionAssignment
        assignments = CourseSessionAssignment.query.filter_by(
            curriculum_id=curriculum_id
        ).all()
        for assignment in assignments:
            if assignment.course_id not in course_assignments:
                course_assignments[assignment.course_id] = []
            course_assignments[assignment.course_id].append(assignment)
            
            # Build teacher map for displaying teacher names
            if assignment.teacher_id and assignment.teacher_id not in teacher_map:
                try:
                    from blueprints.class_management.models import Teacher
                    teacher = Teacher.query.get(assignment.teacher_id)
                    if teacher:
                        teacher_map[assignment.teacher_id] = teacher.name
                except:
                    pass
    except:
        course_assignments = {}
        teacher_map = {}
    
    return render_template('course_management/index.html', 
                         curriculum=curriculum, 
                         courses=courses, 
                         courses_by_year_term=sorted_groups,
                         course_form=course_form,
                         curriculum_form=curriculum_form,
                         edit_curriculum_form=edit_curriculum_form,
                         curricula=curricula,
                         course_info_forms=course_info_forms,
                         curriculum_batches=curriculum_batches,
                         teachers=teachers,
                         course_assignments=course_assignments,
                         teacher_map=teacher_map)

@course_management_bp.route('/curriculum/add', methods=['POST'])
@login_required
def add_curriculum():
    """Add a new curriculum"""
    form = CurriculumForm()
    form.applicable_batches.choices = get_available_batches()
    if form.validate_on_submit():
        # Convert selected batches to comma-separated string
        applicable_batches_str = ','.join(form.applicable_batches.data) if form.applicable_batches.data else None
        
        new_curriculum = Curriculum(
            name=form.name.data,
            date=form.date.data,
            applicable_batches=applicable_batches_str
        )
        db.session.add(new_curriculum)
        db.session.commit()
        flash(f'Curriculum "{form.name.data}" added successfully!', 'success')
        return redirect(url_for('course_management.view_curriculum', curriculum_id=new_curriculum.id))
    
    # If validation fails, show errors
    curricula = Curriculum.query.order_by(Curriculum.created_at.desc()).all()
    return render_template('course_management/index.html', curricula=curricula, curriculum_form=form)

@course_management_bp.route('/curriculum/<int:curriculum_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_curriculum(curriculum_id):
    """Edit a curriculum"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    form = CurriculumForm()
    form.applicable_batches.choices = get_available_batches(exclude_curriculum_id=curriculum_id)
    
    # Include batches already assigned to this curriculum
    existing_batches = curriculum.get_batches_list()
    for batch in existing_batches:
        if (batch, batch) not in form.applicable_batches.choices:
            form.applicable_batches.choices.append((batch, batch))
    
    if request.method == 'POST':
        form.applicable_batches.choices = get_available_batches(exclude_curriculum_id=curriculum_id)
        # Re-add existing batches
        for batch in existing_batches:
            if (batch, batch) not in form.applicable_batches.choices:
                form.applicable_batches.choices.append((batch, batch))
        
        if form.validate_on_submit():
            # Convert selected batches to comma-separated string
            applicable_batches_str = ','.join(form.applicable_batches.data) if form.applicable_batches.data else None
            
            curriculum.name = form.name.data
            curriculum.date = form.date.data
            curriculum.applicable_batches = applicable_batches_str
            
            db.session.commit()
            flash(f'Curriculum "{form.name.data}" updated successfully!', 'success')
            return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
    
    # Populate form with existing data
    form.name.data = curriculum.name
    form.date.data = curriculum.date
    form.applicable_batches.data = existing_batches
    
    # Return JSON for AJAX or render template
    if request.is_json or request.args.get('format') == 'json':
        return jsonify({
            'success': True,
            'curriculum': {
                'id': curriculum.id,
                'name': curriculum.name,
                'date': curriculum.date,
                'applicable_batches': existing_batches
            },
            'form_data': {
                'name': form.name.data,
                'date': form.date.data,
                'applicable_batches': existing_batches
            }
        })
    
    # For regular GET request, redirect to view with edit flag
    return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id, edit='true'))

@course_management_bp.route('/curriculum/<int:curriculum_id>/delete', methods=['POST'])
@login_required
def delete_curriculum(curriculum_id):
    """Delete a curriculum"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    curriculum_name = curriculum.name
    db.session.delete(curriculum)
    db.session.commit()
    flash(f'Curriculum "{curriculum_name}" deleted successfully!', 'success')
    return redirect(url_for('course_management.index'))

@course_management_bp.route('/curriculum/<int:curriculum_id>/course/add', methods=['POST'])
@login_required
def add_course(curriculum_id):
    """Add a new course to a curriculum"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    form = CourseForm()
    if form.validate_on_submit():
        # Check if course code already exists in the same curriculum
        existing_course = Course.query.filter_by(
            curriculum_id=curriculum_id,
            course_code=form.course_code.data
        ).first()
        if existing_course:
            flash(f'Course with code {form.course_code.data} already exists in this curriculum!', 'error')
            return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
        
        entered_year = (form.year.data or '').strip()
        entered_term = (form.term.data or '').strip()
        if not entered_year or not entered_term:
            inferred_year, inferred_term = infer_year_and_term(form.course_code.data)
            if not entered_year:
                entered_year = inferred_year
            if not entered_term:
                entered_term = inferred_term
        
        new_course = Course(
            curriculum_id=curriculum_id,
            course_code=form.course_code.data,
            course_name=form.course_name.data,
            credit=form.credit.data,
            course_type=form.course_type.data,
            category=form.category.data,
            core_optional=form.core_optional.data,
            year=entered_year or None,
            term=entered_term or None
        )
        db.session.add(new_course)
        db.session.commit()
        flash('Course added successfully!', 'success')
        return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
    
    # If validation fails, show errors
    courses = Course.query.filter_by(curriculum_id=curriculum_id).order_by('course_code').all()
    curriculum_form = CurriculumForm()
    curricula = Curriculum.query.order_by(Curriculum.created_at.desc()).all()
    return render_template('course_management/index.html', 
                         curriculum=curriculum, 
                         courses=courses, 
                         course_form=form,
                         curriculum_form=curriculum_form,
                         curricula=curricula)

@course_management_bp.route('/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    """Edit a course"""
    course = Course.query.get_or_404(course_id)
    curriculum_id = course.curriculum_id
    
    if request.method == 'POST':
        course_code = request.form.get('course_code', '').strip()
        course_name = request.form.get('course_name', '').strip()
        credit = request.form.get('credit', type=float)
        course_type = request.form.get('course_type', '').strip()
        category = request.form.get('category', '').strip()
        core_optional = request.form.get('core_optional', '').strip()
        
        if not course_code or not course_name or credit is None or not course_type or not category or not core_optional:
            flash('All fields are required!', 'error')
            if curriculum_id:
                return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
            return redirect(url_for('course_management.index'))
        
        # Check if course code already exists in the same curriculum (excluding current course)
        existing_course = Course.query.filter_by(
            curriculum_id=curriculum_id,
            course_code=course_code
        ).first()
        if existing_course and existing_course.id != course_id:
            flash(f'Course with code {course_code} already exists in this curriculum!', 'error')
            if curriculum_id:
                return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
            return redirect(url_for('course_management.index'))
        
        try:
            course.course_code = course_code
            course.course_name = course_name
            course.credit = credit
            course.course_type = course_type
            course.category = category
            course.core_optional = core_optional
            db.session.commit()
            flash(f'Course {course_code} updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating course {course_id}: {e}", exc_info=True)
            flash(f'Error updating course: {str(e)}', 'error')
        
        if curriculum_id:
            return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
        return redirect(url_for('course_management.index'))
    
    # GET request - redirect to curriculum view
    if curriculum_id:
        return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
    return redirect(url_for('course_management.index'))

@course_management_bp.route('/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    """Delete a course and clean up dependent records."""
    course = Course.query.get_or_404(course_id)
    curriculum_id = course.curriculum_id
    course_code = course.course_code

    try:
        # Clean up any teacher assignments / sessions tied to this course
        assignments = CourseSessionAssignment.query.filter_by(course_id=course_id).all()
        for assignment in assignments:
            session_obj = Session.query.get(assignment.session_id) if assignment.session_id else None
            if session_obj:
                ClassStudent.query.filter_by(session_id=session_obj.id).delete()
                db.session.delete(session_obj)
            db.session.delete(assignment)

        # Detach historical records instead of deleting them
        StudentCourseRegistration.query.filter_by(course_id=course_id).update({'course_id': None})
        DutyAssignment.query.filter_by(course_id=course_id).update({'course_id': None})

        db.session.delete(course)
        db.session.commit()
        flash(f'Course {course_code} deleted successfully!', 'success')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to delete course {course_id}: {exc}', exc_info=True)
        flash('Failed to delete course. Please try again.', 'error')

    if curriculum_id:
        return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))
    return redirect(url_for('course_management.index'))

@course_management_bp.route('/course/<int:course_id>/info', methods=['POST'])
@login_required
def course_info(course_id):
    """Update course information (rationale, CLO, content)"""
    import json
    course = Course.query.get_or_404(course_id)
    form = CourseInfoForm()
    
    if form.validate_on_submit():
        course.year = form.year.data if form.year.data else None
        course.term = form.term.data if form.term.data else None
        course.rationale = form.rationale.data if form.rationale.data else None
        course.content_section_a = form.content_section_a.data if form.content_section_a.data else None
        course.content_section_b = form.content_section_b.data if form.content_section_b.data else None
        
        # Handle CLOs from JSON
        clos_json = request.form.get('clos_json', '')
        if clos_json:
            try:
                clos_list = json.loads(clos_json)
                course.set_clos_list(clos_list)
            except json.JSONDecodeError:
                course.clo = None
        else:
            course.clo = None
        
        db.session.commit()
        flash('Course information updated successfully!', 'success')
    else:
        flash('Error updating course information. Please try again.', 'error')
    
    if course.curriculum_id:
        return redirect(url_for('course_management.view_curriculum', curriculum_id=course.curriculum_id))
    return redirect(url_for('course_management.index'))

@course_management_bp.route('/course/<int:course_id>/toggle-offered', methods=['POST'])
@login_required
def toggle_offered(course_id):
    """Toggle the offered status of a course"""
    try:
        course = Course.query.get_or_404(course_id)
        
        if request.is_json:
            data = request.get_json()
            offered = data.get('offered', True)
        else:
            offered = request.form.get('offered', 'true').lower() == 'true'
        
        course.offered = offered
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Course {"offered" if offered else "not offered"} status updated successfully',
            'offered': course.offered
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling offered status for course {course_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error updating offered status: {str(e)}'
        }), 500

@course_management_bp.route('/student/registration')
@login_required
def student_course_registration():
    """Student course registration page"""
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        flash('Course registration is available only for student accounts.', 'danger')
        return redirect(url_for('index'))
    
    # Get distinct academic sessions
    sessions = db.session.query(Session.academic_session).distinct().filter(
        Session.academic_session.isnot(None)
    ).order_by(Session.academic_session.desc()).all()
    academic_sessions = [s[0] for s in sessions if s[0]]
    
    return render_template('course_management/student_registration.html', 
                         academic_sessions=academic_sessions)

@course_management_bp.route('/student/registration/api/courses', methods=['GET'])
@login_required
def get_courses_for_registration():
    """API endpoint to fetch courses by year and term"""
    roles = parse_roles(current_user.role)
    # Allow students, teaching assistants, and coordinators (teachers/head/dean)
    if 'student' not in roles and 'teaching_assistant' not in roles and 'teacher' not in roles and 'head' not in roles and 'dean' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()
    
    if not year or not term:
        return jsonify({'success': False, 'message': 'Year and Term are required'}), 400
    
    # Get all offered courses
    query = Course.query.filter_by(offered=True)
    courses = query.order_by(Course.course_name.asc()).all()
    
    # Filter by year and term
    filtered_courses = []
    for c in courses:
        if c.display_year == year and c.display_term == term:
            filtered_courses.append({
                'id': c.id,
                'course_code': c.course_code,
                'course_name': c.course_name,
                'credit': c.credit,
                'course_type': c.course_type,
                'category': c.category,
                'nature': c.core_optional or 'Core'
            })
    
    return jsonify({
        'success': True,
        'courses': filtered_courses
    })


@course_management_bp.route('/student/registration/api/registrations', methods=['GET'])
@login_required
def get_saved_registrations():
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    session_name = request.args.get('session', '').strip()
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()

    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400

    student_record = _get_current_student_record()
    if not student_record:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404

    registrations = StudentCourseRegistration.query.filter_by(
        student_id=student_record.id,
        academic_session=session_name,
        year=year,
        term=term
    ).order_by(StudentCourseRegistration.course_code.asc()).all()

    data = [{
        'id': reg.course_id,
        'course_code': reg.course_code,
        'course_name': reg.course_name,
        'credit': reg.credit,
        'course_type': reg.course_type,
        'nature': reg.nature,
        'remark': reg.remark
    } for reg in registrations]

    return jsonify({'success': True, 'registrations': data})


@course_management_bp.route('/student/registration/save', methods=['POST'])
@login_required
def save_course_registration():
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json() or {}
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    courses = data.get('courses') or []

    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400

    if not courses:
        return jsonify({'success': False, 'message': 'No courses selected'}), 400

    student_record = _get_current_student_record()
    if not student_record:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404

    try:
        # Get existing registrations to preserve status
        existing_regs = StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()
        existing_status = {reg.course_code: reg.status for reg in existing_regs}
        
        # Delete existing registrations
        StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).delete()

        for course in courses:
            # Preserve status if it was finalized, otherwise set to draft
            status = existing_status.get(course.get('course_code', ''), 'draft')
            if status not in ['finalized', 'pending']:
                status = 'draft'
            
            reg = StudentCourseRegistration(
                student_id=student_record.id,
                course_id=course.get('id'),
                academic_session=session_name,
                year=year,
                term=term,
                course_code=course.get('course_code', ''),
                course_name=course.get('course_name', ''),
                credit=course.get('credit', 0),
                course_type=course.get('course_type', ''),
                nature=course.get('nature', 'Core'),
                remark=course.get('remark', 'Regular'),
                status=status
            )
            db.session.add(reg)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Registration saved successfully.'})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to save registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to save registration.'}), 500

@course_management_bp.route('/student/registration/download-pdf', methods=['POST'])
@login_required
def download_registration_pdf():
    """Generate and download course registration PDF matching the scanned copy design"""
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))
    
    try:
        data = request.get_json()
        session_name = data.get('session', '')
        year = data.get('year', '')
        term = data.get('term', '')
        courses = data.get('courses', [])
        student_name = current_user.full_name or current_user.username
        student_id = current_user.username
        
        if not courses:
            return jsonify({'success': False, 'message': 'No courses selected'}), 400
        
        # Get student data from Student model
        student_record = Student.query.filter_by(student_id=student_id).first()
        hall = student_record.hall if student_record else None
        contact_no = student_record.phone if student_record else None
        
        # Get registration data for approval timestamps
        registration_record = None
        if student_record:
            registration_record = StudentCourseRegistration.query.filter_by(
                student_id=student_record.id,
                academic_session=session_name,
                year=year,
                term=term
            ).first()
        
        # Generate PDF with custom canvas for watermark
        buffer = BytesIO()
        
        def add_watermark(canvas_obj, doc):
            """Add watermark logo in background"""
            try:
                logo_path = os.path.join(current_app.static_folder, 'Images', 'KU_logo_2.png')
                if os.path.exists(logo_path):
                    # Draw large faded logo in center as watermark
                    canvas_obj.saveState()
                    canvas_obj.setFillAlpha(0.1)  # Very transparent
                    # Center position
                    x_center = A4[0] / 2
                    y_center = A4[1] / 2
                    logo_size = 150 * mm  # Large watermark size
                    canvas_obj.drawImage(logo_path, 
                                       x_center - logo_size/2, 
                                       y_center - logo_size/2,
                                       width=logo_size, 
                                       height=logo_size, 
                                       preserveAspectRatio=True,
                                       mask='auto')
                    canvas_obj.restoreState()
            except Exception as e:
                current_app.logger.warning(f"Could not add watermark: {e}")
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=15 * mm,
            bottomMargin=15 * mm,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            onFirstPage=add_watermark,
            onLaterPages=add_watermark,
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        university_style = ParagraphStyle(
            'University',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=14,
            leading=16,
            textColor=colors.black,
            fontName='Helvetica-Bold',
            spaceAfter=4,
        )
        
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=12,
            leading=14,
            textColor=colors.black,
            fontName='Helvetica-Bold',
            spaceAfter=6,
        )
        
        session_style = ParagraphStyle(
            'Session',
            parent=styles['Normal'],
            alignment=TA_CENTER,
            fontSize=10,
            leading=12,
            textColor=colors.black,
            spaceAfter=12,
        )
        
        discipline_style = ParagraphStyle(
            'Discipline',
            parent=styles['Normal'],
            alignment=TA_LEFT,
            fontSize=11,
            leading=13,
            textColor=colors.black,
            fontName='Helvetica-Bold',
            spaceAfter=8,
        )
        
        info_style = ParagraphStyle(
            'Info',
            parent=styles['Normal'],
            alignment=TA_LEFT,
            fontSize=10,
            leading=14,
            textColor=colors.black,
            leftIndent=0,
            spaceAfter=4,
        )
        
        approval_style = ParagraphStyle(
            'Approval',
            parent=styles['Normal'],
            alignment=TA_LEFT,
            fontSize=9,
            leading=12,
            textColor=colors.black,
            spaceAfter=3,
        )
        
        elements = []
        
        # Header with logo, title, and photo placeholder
        # Left: Logo
        logo_path = os.path.join(current_app.static_folder, 'Images', 'KU_logo_2.png')
        logo_cell = ''
        if os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=35*mm, height=35*mm, kind='proportional')
                logo_cell = logo_img
            except:
                logo_cell = ''
        
        # Center: University name and title (create a table for vertical stacking)
        center_table = Table([
            [Paragraph('KHULNA UNIVERSITY, KHULNA', university_style)],
            [Paragraph('Course Registration Card', title_style)],
            [Paragraph(f'Session: {session_name}', session_style)],
        ], colWidths=[100*mm])
        center_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        # Right: Student photo
        photo_cell = ''
        if current_user.photo:
            # Try to get student photo
            # photo path is stored as "/static/uploads/user_photos/filename.jpg"
            # Need to convert to absolute path
            photo_rel_path = current_user.photo.lstrip('/')
            student_photo_path = os.path.join(current_app.root_path, photo_rel_path)
            if os.path.exists(student_photo_path):
                try:
                    # Resize photo to fit in the box (30mm x 30mm)
                    student_photo = Image(student_photo_path, width=30*mm, height=30*mm, kind='proportional')
                    # Create a table with border for the photo
                    photo_table = Table([[student_photo]], colWidths=[30*mm], rowHeights=[30*mm])
                    photo_table.setStyle(TableStyle([
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ]))
                    photo_cell = photo_table
                except Exception as e:
                    current_app.logger.warning(f"Could not add student photo to PDF: {e}")
                    # Fallback to empty box
                    photo_box = Table([['']], colWidths=[30*mm], rowHeights=[30*mm])
                    photo_box.setStyle(TableStyle([
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ]))
                    photo_cell = photo_box
            else:
                # Photo path exists in DB but file not found - use empty box
                photo_box = Table([['']], colWidths=[30*mm], rowHeights=[30*mm])
                photo_box.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                photo_cell = photo_box
        else:
            # No photo uploaded - use empty box
            photo_box = Table([['']], colWidths=[30*mm], rowHeights=[30*mm])
            photo_box.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            photo_cell = photo_box
        
        # Create header table with 3 columns
        header_table = Table(
            [[logo_cell, center_table, photo_cell]],
            colWidths=[40*mm, 100*mm, 40*mm]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 12))
        
        # Law Discipline section
        elements.append(Paragraph('Law Discipline', discipline_style))
        
        # Student information in numbered list format
        student_info = [
            f'1. Roll Number: {student_id}',
            f'2. Name: {student_name.upper()}',
            f'3. Year: {year}',
            f'4. Term: {term}',
            f'5. Hall: {hall or "N/A"}',
            f'6. Contact No: {contact_no or "N/A"}',
        ]
        
        for info in student_info:
            elements.append(Paragraph(info, info_style))
        
        elements.append(Spacer(1, 10))
        
        # Course table with columns: Course No., Course Title, Credit, Remarks
        course_headers = ['Course No.', 'Course Title', 'Credit', 'Remarks']
        course_data = [course_headers]
        
        total_credits = 0
        for course in courses:
            course_code = course.get('course_code', '')
            
            course_data.append([
                course_code,
                course.get('course_name', ''),
                str(course.get('credit', 0)),
                course.get('remark', '') or ''
            ])
            total_credits += float(course.get('credit', 0))
        
        # Add total row
        course_data.append([
            '',
            'Total',
            str(int(total_credits)),
            ''
        ])
        
        course_table = Table(course_data, colWidths=[40*mm, 75*mm, 20*mm, 35*mm])
        course_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTSIZE', (0, 0), (-1, 0), 10),  # Header row
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),  # Course Title left aligned
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
        ]))
        elements.append(course_table)
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        filename = f'course_registration_{student_id}_{datetime.now().strftime("%Y%m%d")}.pdf'
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.error(f"Error generating registration PDF: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error generating PDF: {str(e)}'}), 500


@course_management_bp.route('/student/registration/send-to-coordinator', methods=['POST'])
@login_required
def send_to_coordinator():
    """Send registration to assigned course coordinator (by batch) for review"""
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json() or {}
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()

    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400

    student_record = _get_current_student_record()
    if not student_record:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404

    if not student_record.batch:
        return jsonify({'success': False, 'message': 'Student batch not found'}), 400

    try:
        coordinator_teacher = None

        # Look for batch-specific coordinator assignment
        coordinator_assignment = DutyAssignment.query.filter(
            DutyAssignment.duty_type == 'course_coordinator',
            DutyAssignment.status == 'active',
            DutyAssignment.batch == student_record.batch,
            DutyAssignment.assigned_teacher_id.isnot(None)
        ).order_by(DutyAssignment.created_at.desc()).first()

        if coordinator_assignment and coordinator_assignment.assigned_teacher:
            coordinator_teacher = coordinator_assignment.assigned_teacher
        else:
            # Fallback to legacy assignments without batch
            legacy_assignment = DutyAssignment.query.filter(
                DutyAssignment.duty_type == 'course_coordinator',
                DutyAssignment.status == 'active',
                or_(DutyAssignment.batch.is_(None), DutyAssignment.batch == ''),
                DutyAssignment.assigned_teacher_id.isnot(None)
            ).order_by(DutyAssignment.created_at.desc()).first()

            if legacy_assignment and legacy_assignment.assigned_teacher:
                coordinator_teacher = legacy_assignment.assigned_teacher
            else:
                coordinator_teacher = None

        if not coordinator_teacher:
            # Fall back to head users
            head_users = User.query.filter(
                User.role.like('%head%')
            ).all()

            if not head_users:
                return jsonify({'success': False, 'message': 'No Head teacher found. Please contact administration.'}), 404

            head_user = head_users[0]
            coordinator_teacher = Teacher.query.filter_by(name=head_user.full_name).first()
            if not coordinator_teacher:
                short_name = head_user.username[:20] if head_user.username else head_user.full_name[:20]
                coordinator_teacher = Teacher(name=head_user.full_name, short_name=short_name)
                db.session.add(coordinator_teacher)
                db.session.flush()

        # Get registrations for this session/year/term
        registrations = StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()

        if not registrations:
            return jsonify({'success': False, 'message': 'No courses registered. Please register courses first.'}), 400

        # Update registration status to pending
        for reg in registrations:
            reg.status = 'pending'
            # Create or update invite
            existing_invites = CourseRegistrationInvite.query.filter_by(
                registration_id=reg.id
            ).all()
            
            if existing_invites:
                for invite in existing_invites:
                    invite.status = 'pending'
                    invite.coordinator_teacher_id = coordinator_teacher.id
                    invite.created_at = datetime.utcnow()
                    invite.responded_at = None
            else:
                invite = CourseRegistrationInvite(
                    registration_id=reg.id,
                    student_id=student_record.id,
                    coordinator_teacher_id=coordinator_teacher.id,
                    status='pending'
                )
                db.session.add(invite)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Registration sent to coordinator for review.'})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to send to coordinator: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to send registration.'}), 500


@course_management_bp.route('/coordinator/registrations')
@login_required
def coordinator_registrations():
    """View course registrations as coordinator"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        flash('This page is available only for coordinators.', 'danger')
        return redirect(url_for('index'))

    # Get current teacher profile
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        flash('Teacher profile not found.', 'warning')
        return redirect(url_for('index'))

    # Get pending invitations
    invites = CourseRegistrationInvite.query.filter_by(
        coordinator_teacher_id=teacher.id,
        status='pending'
    ).order_by(CourseRegistrationInvite.created_at.desc()).all()

    # Group registrations by student and session
    registrations_by_student = {}
    for invite in invites:
        reg = invite.registration
        if reg:
            key = (reg.student_id, reg.academic_session, reg.year, reg.term)
            if key not in registrations_by_student:
                registrations_by_student[key] = {
                    'student': reg.student,
                    'session': reg.academic_session,
                    'year': reg.year,
                    'term': reg.term,
                    'registrations': [],
                    'registration_ids': set(),
                    'invite_ids': []
                }
            entry = registrations_by_student[key]
            if reg.id not in entry['registration_ids']:
                entry['registrations'].append(reg)
                entry['registration_ids'].add(reg.id)
            registrations_by_student[key]['invite_ids'].append(invite.id)

    # Get finalized registrations
    finalized_invites = CourseRegistrationInvite.query.filter_by(
        coordinator_teacher_id=teacher.id,
        status='finalized'
    ).order_by(CourseRegistrationInvite.responded_at.desc()).all()

    finalized_by_student = {}
    for invite in finalized_invites:
        reg = invite.registration
        if reg:
            key = (reg.student_id, reg.academic_session, reg.year, reg.term)
            if key not in finalized_by_student:
                finalized_by_student[key] = {
                    'student': reg.student,
                    'session': reg.academic_session,
                    'year': reg.year,
                    'term': reg.term,
                    'registrations': [],
                    'registration_ids': set(),
                    'invite_ids': []
                }
            entry = finalized_by_student[key]
            if reg.id not in entry['registration_ids']:
                entry['registrations'].append(reg)
                entry['registration_ids'].add(reg.id)
            finalized_by_student[key]['invite_ids'].append(invite.id)

    return render_template('course_management/coordinator_registrations.html',
                         pending_registrations=registrations_by_student,
                         finalized_registrations=finalized_by_student)


@course_management_bp.route('/coordinator/registration/<int:student_id>/view', methods=['GET'])
@login_required
def view_student_registration(student_id):
    """View and edit a specific student's registration"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    session_name = request.args.get('session', '').strip()
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()

    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400

    student = Student.query.get_or_404(student_id)
    registrations = StudentCourseRegistration.query.filter_by(
        student_id=student_id,
        academic_session=session_name,
        year=year,
        term=term
    ).order_by(StudentCourseRegistration.course_code.asc()).all()

    data = [{
        'id': reg.id,
        'course_id': reg.course_id,
        'course_code': reg.course_code,
        'course_name': reg.course_name,
        'credit': reg.credit,
        'course_type': reg.course_type,
        'nature': reg.nature,
        'remark': reg.remark,
        'status': reg.status
    } for reg in registrations]

    total_credits = sum(reg.credit for reg in registrations)

    return jsonify({
        'success': True,
        'student': {
            'id': student.id,
            'student_id': student.student_id,
            'name': student.name,
            'batch': student.batch
        },
        'session': session_name,
        'year': year,
        'term': term,
        'courses': data,
        'total_credits': total_credits
    })


@course_management_bp.route('/coordinator/registration/update', methods=['POST'])
@login_required
def update_student_registration():
    """Update student registration (coordinator can edit)"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json() or {}
    student_id = data.get('student_id')
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    courses = data.get('courses', [])

    if not student_id or not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Student ID, Session, Year, and Term are required'}), 400

    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher profile not found'}), 404

    try:
        # Get existing registrations
        existing_regs = StudentCourseRegistration.query.filter_by(
            student_id=student_id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()

        # Update or create registrations
        existing_codes = {reg.course_code: reg for reg in existing_regs}
        updated_codes = set()

        for course in courses:
            course_code = course.get('course_code', '')
            if course_code in existing_codes:
                # Update existing
                reg = existing_codes[course_code]
                reg.course_name = course.get('course_name', reg.course_name)
                reg.credit = course.get('credit', reg.credit)
                reg.course_type = course.get('course_type', reg.course_type)
                reg.nature = course.get('nature', reg.nature)
                reg.remark = course.get('remark', reg.remark)
                updated_codes.add(course_code)
            else:
                # Create new
                reg = StudentCourseRegistration(
                    student_id=student_id,
                    course_id=course.get('course_id'),
                    academic_session=session_name,
                    year=year,
                    term=term,
                    course_code=course_code,
                    course_name=course.get('course_name', ''),
                    credit=course.get('credit', 0),
                    course_type=course.get('course_type', ''),
                    nature=course.get('nature', 'Core'),
                    remark=course.get('remark', 'Regular'),
                    status='pending'
                )
                db.session.add(reg)
                updated_codes.add(course_code)

        # Delete removed courses
        for code, reg in existing_codes.items():
            if code not in updated_codes:
                db.session.delete(reg)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Registration updated successfully.'})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to update registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to update registration.'}), 500


@course_management_bp.route('/coordinator/registration/finalize', methods=['POST'])
@login_required
def finalize_registration():
    """Finalize a student's registration"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json() or {}
    student_id = data.get('student_id')
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()

    if not student_id or not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Student ID, Session, Year, and Term are required'}), 400

    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher profile not found'}), 404

    try:
        # Get registrations
        registrations = StudentCourseRegistration.query.filter_by(
            student_id=student_id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()

        if not registrations:
            return jsonify({'success': False, 'message': 'No registrations found'}), 404

        # Update registration status
        for reg in registrations:
            reg.status = 'finalized'

        # Update invite status
        invite_ids = [reg.id for reg in registrations]
        invites = CourseRegistrationInvite.query.filter(
            CourseRegistrationInvite.registration_id.in_(invite_ids),
            CourseRegistrationInvite.coordinator_teacher_id == teacher.id
        ).all()

        for invite in invites:
            invite.status = 'finalized'
            invite.responded_at = datetime.utcnow()

        db.session.commit()
        return jsonify({'success': True, 'message': 'Registration finalized successfully.'})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to finalize registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to finalize registration.'}), 500


@course_management_bp.route('/coordinator/register-student')
@login_required
def coordinator_register_student():
    """Coordinator can register courses for a student"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        flash('This page is available only for coordinators.', 'danger')
        return redirect(url_for('index'))
    
    # Get all students
    from blueprints.student_management.models import Student
    students = Student.query.order_by(Student.student_id.asc()).all()
    
    # Get distinct academic sessions
    sessions = db.session.query(Session.academic_session).distinct().filter(
        Session.academic_session.isnot(None)
    ).order_by(Session.academic_session.desc()).all()
    academic_sessions = [s[0] for s in sessions if s[0]]
    
    return render_template('course_management/coordinator_register_student.html',
                         students=students,
                         academic_sessions=academic_sessions)


@course_management_bp.route('/coordinator/register-student/save', methods=['POST'])
@login_required
def coordinator_save_student_registration():
    """Save course registration for a student by coordinator"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json() or {}
    student_id = data.get('student_id')
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    courses = data.get('courses') or []
    
    if not student_id or not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Student ID, Session, Year, and Term are required'}), 400
    
    if not courses:
        return jsonify({'success': False, 'message': 'No courses selected'}), 400
    
    from blueprints.student_management.models import Student
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    # Get current teacher profile
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher profile not found'}), 404
    
    try:
        # Delete existing registrations for this student/session/year/term
        StudentCourseRegistration.query.filter_by(
            student_id=student_id,
            academic_session=session_name,
            year=year,
            term=term
        ).delete()
        
        # Create new registrations
        for course in courses:
            reg = StudentCourseRegistration(
                student_id=student_id,
                course_id=course.get('id'),
                academic_session=session_name,
                year=year,
                term=term,
                course_code=course.get('course_code', ''),
                course_name=course.get('course_name', ''),
                credit=course.get('credit', 0),
                course_type=course.get('course_type', ''),
                nature=course.get('nature', 'Core'),
                remark=course.get('remark', 'Regular'),
                status='pending'  # Coordinator registrations start as pending
            )
            db.session.add(reg)
        
        db.session.commit()
        
        # Create or update invite for this coordinator
        registrations = StudentCourseRegistration.query.filter_by(
            student_id=student_id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()
        
        for reg in registrations:
            # Check if invite already exists
            existing_invite = CourseRegistrationInvite.query.filter_by(
                registration_id=reg.id,
                coordinator_teacher_id=teacher.id
            ).first()
            
            if not existing_invite:
                invite = CourseRegistrationInvite(
                    registration_id=reg.id,
                    student_id=student_id,
                    coordinator_teacher_id=teacher.id,
                    status='pending'
                )
                db.session.add(invite)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Courses registered successfully for {student.name}'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to save coordinator registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to save registration'}), 500


@course_management_bp.route('/curriculum/<int:curriculum_id>/year-term-config', methods=['POST'])
@login_required
def save_year_term_config(curriculum_id):
    """Save or update batch and academic session for a year/term combination"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    
    data = request.get_json() or {}
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    academic_session = data.get('academic_session', '').strip()
    batch = data.get('batch', '').strip()
    
    if not year or not term:
        return jsonify({'success': False, 'message': 'Year and Term are required'}), 400
    
    try:
        # Check if configuration already exists
        config = CurriculumYearTerm.query.filter_by(
            curriculum_id=curriculum_id,
            year=year,
            term=term
        ).first()
        
        if config:
            # Update existing
            config.academic_session = academic_session if academic_session else None
            config.batch = batch if batch else None
            config.updated_at = datetime.utcnow()
        else:
            # Create new
            config = CurriculumYearTerm(
                curriculum_id=curriculum_id,
                year=year,
                term=term,
                academic_session=academic_session if academic_session else None,
                batch=batch if batch else None
            )
            db.session.add(config)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to save year/term config: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to save configuration'}), 500

@course_management_bp.route('/api/assign-teacher-session', methods=['POST'])
@login_required
def assign_teacher_session():
    """Assign teacher to course and automatically create Session in Class Management"""
    try:
        data = request.get_json() or {}
        
        def _parse_int(value):
            try:
                return int(value) if value is not None and value != '' else None
            except (TypeError, ValueError):
                return None

        course_id = _parse_int(data.get('course_id'))
        curriculum_id = _parse_int(data.get('curriculum_id'))
        teacher_id = _parse_int(data.get('teacher_id'))
        section = data.get('section', '').strip() or None
        year = data.get('year', '').strip()
        term = data.get('term', '').strip()
        batch_str = data.get('batch', '').strip()
        # Handle batch: empty string, 'None', or None should become None, otherwise use the value
        batch = None if (not batch_str or batch_str == 'None' or batch_str == '') else batch_str
        academic_session = data.get('academic_session', '').strip() or None
        
        current_app.logger.info(f'Assign teacher request - course_id: {course_id}, batch_str: "{batch_str}", batch: "{batch}", year: {year}, term: {term}')
        
        if not course_id or not curriculum_id or not teacher_id or not year or not term:
            return jsonify({
                'success': False,
                'message': 'Course, Curriculum, Teacher, Year, and Term are required.'
            }), 400
        
        # Fetch course and verify it exists
        course = Course.query.get_or_404(course_id)
        curriculum = Curriculum.query.get_or_404(curriculum_id)
        teacher = Teacher.query.get_or_404(teacher_id)
        
        # If batch or academic_session not provided, try to get from curriculum year-term config
        if not batch or not academic_session:
            try:
                year_term_config = curriculum.get_year_term_config(year, term)
                if year_term_config:
                    if not batch and year_term_config.batch and year_term_config.batch != 'None' and year_term_config.batch.strip():
                        batch = year_term_config.batch.strip()
                        current_app.logger.info(f'Using batch from year-term config: {batch}')
                    if not academic_session and year_term_config.academic_session and year_term_config.academic_session.strip():
                        academic_session = year_term_config.academic_session.strip()
                        current_app.logger.info(f'Using academic_session from year-term config: {academic_session}')
            except Exception as e:
                current_app.logger.warning(f'Could not get year-term config: {e}')
        
        # Log final batch value before creating session
        current_app.logger.info(f'Final batch value before session creation: "{batch}"')
        
        # Check if assignment already exists
        existing_assignment = CourseSessionAssignment.query.filter_by(
            course_id=course_id,
            teacher_id=teacher_id,
            section=section,
            year=year,
            term=term
        ).filter(
            (CourseSessionAssignment.batch == batch) if batch else (CourseSessionAssignment.batch.is_(None))
        ).first()
        
        if existing_assignment:
            return jsonify({
                'success': False,
                'message': 'This assignment already exists. Please remove the existing assignment first.'
            }), 400
        
        # Determine course scope based on section
        SCOPE_FULL = 'full'
        SCOPE_PART_A = 'part_a'
        SCOPE_PART_B = 'part_b'
        
        if section == 'A':
            course_scope = SCOPE_PART_A
        elif section == 'B':
            course_scope = SCOPE_PART_B
        else:
            course_scope = SCOPE_FULL
        
        # Determine split_group_id for split courses (Part A and Part B)
        # For split courses, all sessions of the same course/year/term/session should share the same split_group_id
        split_group_id = None
        if course_scope in [SCOPE_PART_A, SCOPE_PART_B]:
            # Generate a unique identifier for this split course group
            # Format: course_code_year_term_academic_session (normalized)
            split_group_parts = [
                course.course_code.lower().strip(),
                year.lower().strip(),
                term.lower().strip()
            ]
            if academic_session:
                split_group_parts.append(academic_session.lower().strip())
            split_group_id = '_'.join(split_group_parts)
            
            # Check if there's already a session with this split_group_id
            # If yes, use the same split_group_id to link them
            existing_split_session = Session.query.filter_by(
                split_group_id=split_group_id,
                archived=False
            ).first()
            
            if existing_split_session:
                # Use the existing split_group_id to link sessions
                current_app.logger.info(f'Found existing split course session {existing_split_session.id} with split_group_id {split_group_id}, linking new session')
        
        # Check if a session with similar parameters already exists in Class Management
        # to avoid creating duplicate sessions
        existing_sessions = Session.query.filter_by(
            course_code=course.course_code,
            teacher_id=teacher_id,
            year=year,
            term=term,
            archived=False
        ).all()
        
        if existing_sessions:
            for existing_session in existing_sessions:
                # Check course scope conflicts
                if existing_session.course_scope == SCOPE_FULL and course_scope != SCOPE_FULL:
                    return jsonify({
                        'success': False,
                        'message': 'A full-course session already exists for this teacher. Delete it first to create section-specific sessions.'
                    }), 400
                elif course_scope == SCOPE_FULL and existing_session.course_scope != SCOPE_FULL:
                    return jsonify({
                        'success': False,
                        'message': 'Section-specific sessions already exist for this teacher. Delete them first to create a full-course session.'
                    }), 400
                elif existing_session.course_scope == course_scope:
                    # Check if this session is linked to an assignment
                    linked_assignment = CourseSessionAssignment.query.filter_by(session_id=existing_session.id).first()
                    if linked_assignment:
                        # Session is properly linked to an assignment, this is a real conflict
                        return jsonify({
                            'success': False,
                            'message': f'A session for this course and section already exists for teacher {teacher.name}. Please check Class Management.'
                        }), 400
                    else:
                        # Orphaned session - archive it instead of blocking
                        current_app.logger.warning(f'Found orphaned session {existing_session.id}, archiving it')
                        existing_session.archived = True
                        db.session.commit()
        
        # Create Session in Class Management
        session_obj = Session(
            year=year,
            term=term,
            academic_session=academic_session,
            course_code=course.course_code,
            course_name=course.course_name,
            teacher_id=teacher_id,
            course_type=course.course_type.lower(),
            category=course.category,
            course_scope=course_scope,
            split_group_id=split_group_id  # Set split_group_id for split courses
        )
        db.session.add(session_obj)
        db.session.flush()  # Get session ID before commit
        
        # Automatically add students from batch if available
        added_students_count = 0
        if batch and batch.strip() and batch != 'None' and Student:
            try:
                current_app.logger.info(f'Attempting to add students from batch: {batch} for session {session_obj.id}')
                students_from_batch = Student.query.filter_by(batch=batch).all()
                current_app.logger.info(f'Found {len(students_from_batch)} students in batch {batch}')
                
                if not students_from_batch:
                    current_app.logger.warning(f'No students found in batch {batch} for course {course.course_code}')
                
                for student in students_from_batch:
                    # Check if already exists
                    existing = ClassStudent.query.filter_by(
                        session_id=session_obj.id,
                        student_id=student.student_id
                    ).first()
                    
                    if existing:
                        current_app.logger.debug(f'Student {student.student_id} already exists in session {session_obj.id}')
                        continue
                    
                    class_student = ClassStudent(
                        student_id=student.student_id,
                        name=student.name,
                        session_id=session_obj.id,
                        teacher_id=teacher_id
                    )
                    db.session.add(class_student)
                    added_students_count += 1
                    current_app.logger.debug(f'Added student {student.student_id} ({student.name}) to session {session_obj.id}')
                
                if added_students_count > 0:
                    db.session.flush()  # Flush before commit to ensure students are added
                    current_app.logger.info(f'Successfully added {added_students_count} students from batch {batch} to session {session_obj.id}')
            except Exception as e:
                current_app.logger.error(f'Error auto-adding students from batch {batch}: {str(e)}', exc_info=True)
                # Don't fail the entire assignment if student addition fails
        else:
            if not batch:
                current_app.logger.info(f'No batch provided for session {session_obj.id}, skipping auto-add students')
            elif batch == 'None' or not batch.strip():
                current_app.logger.info(f'Batch is None or empty for session {session_obj.id}, skipping auto-add students')
            elif not Student:
                current_app.logger.warning(f'Student model not available, cannot auto-add students for session {session_obj.id}')
        
        # Create CourseSessionAssignment
        assignment = CourseSessionAssignment(
            course_id=course_id,
            curriculum_id=curriculum_id,
            teacher_id=teacher_id,
            section=section,
            batch=batch,
            year=year,
            term=term,
            academic_session=academic_session,
            session_created=True,
            session_id=session_obj.id
        )
        db.session.add(assignment)
        
        db.session.commit()
        
        message = f'Teacher assigned and session created successfully!'
        if added_students_count > 0:
            message += f' {added_students_count} students added from batch {batch}.'
        
        return jsonify({
            'success': True,
            'message': message,
            'session_id': session_obj.id,
            'assignment_id': assignment.id
        })
        
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to assign teacher and create session: {exc}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Failed to assign teacher: {str(exc)}'
        }), 500


@course_management_bp.route('/api/unassign-teacher-session', methods=['POST'])
@login_required
def unassign_teacher_session():
    """Unassign teacher and remove associated session created via CourseSessionAssignment."""
    try:
        data = request.get_json() or {}
        assignment_id = data.get('assignment_id')
        
        # Better validation
        if assignment_id is None:
            current_app.logger.warning('Unassign request missing assignment_id')
            return jsonify({'success': False, 'message': 'Assignment ID is required.'}), 400
        
        try:
            assignment_id = int(assignment_id)
        except (ValueError, TypeError):
            current_app.logger.warning(f'Invalid assignment_id format: {assignment_id}')
            return jsonify({'success': False, 'message': 'Invalid assignment ID format.'}), 400

        assignment = CourseSessionAssignment.query.get(assignment_id)
        if not assignment:
            current_app.logger.warning(f'Assignment not found: {assignment_id}')
            return jsonify({'success': False, 'message': 'Assignment not found.'}), 404

        # Store session_id before deletion
        session_id_to_delete = assignment.session_id
        
        # Delete associated session if exists - clean up all related records
        session_obj = None
        if session_id_to_delete:
            try:
                session_obj = Session.query.get(session_id_to_delete)
            except Exception as e:
                current_app.logger.warning(f'Error fetching session {session_id_to_delete}: {e}')
                session_obj = None

        if session_obj and hasattr(session_obj, 'id'):
            session_id = session_obj.id
            
            # Instead of deleting, archive the session to preserve data
            # This ensures batch and academic_session information is retained
            try:
                # Ensure session has academic_session from assignment if missing
                if assignment.academic_session and not session_obj.academic_session:
                    session_obj.academic_session = assignment.academic_session
                
                # Archive the session instead of deleting
                session_obj.archived = True
                db.session.flush()
                current_app.logger.info(f'Archived session {session_id} (course: {session_obj.course_name}) instead of deleting to preserve batch and session information')
            except Exception as archive_error:
                db.session.rollback()
                current_app.logger.error(f'Error archiving session {session_id}: {archive_error}', exc_info=True)
                # If archiving fails, try to delete as fallback
                try:
                    # Import all necessary models for cleanup
                    from blueprints.class_management.models import ClassAttendance, CourseReview, EvaluationInvite, EvaluationSubmission, StudentFeedbackLink, StudentFeedbackResponse, ClassSplitInvite
                    from blueprints.course_management.models import CourseOutline
                    
                    # Delete all related records in correct order
                    # 1. Delete course_outline first (if exists)
                    try:
                        CourseOutline.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting CourseOutline for session {session_id}: {e}')
                    
                    # 2. Delete student feedback responses first (before feedback links)
                    try:
                        feedback_link_ids = [link.id for link in StudentFeedbackLink.query.filter_by(session_id=session_id).all()]
                        if feedback_link_ids:
                            StudentFeedbackResponse.query.filter(
                                StudentFeedbackResponse.feedback_link_id.in_(feedback_link_ids)
                            ).delete(synchronize_session=False)
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting StudentFeedbackResponse for session {session_id}: {e}')
                    
                    # 3. Delete student feedback links
                    try:
                        StudentFeedbackLink.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting StudentFeedbackLink for session {session_id}: {e}')
                    
                    # 4. Delete evaluation submissions (has session_id directly)
                    try:
                        EvaluationSubmission.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting EvaluationSubmission for session {session_id}: {e}')
                    
                    # 5. Delete evaluation invites
                    try:
                        EvaluationInvite.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting EvaluationInvite for session {session_id}: {e}')
                    
                    # 6. Delete course reviews
                    try:
                        CourseReview.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting CourseReview for session {session_id}: {e}')
                    
                    # 7. Delete attendance records
                    try:
                        ClassAttendance.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting ClassAttendance for session {session_id}: {e}')
                    
                    # 8. Delete student records
                    try:
                        ClassStudent.query.filter_by(session_id=session_id).delete()
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting ClassStudent for session {session_id}: {e}')
                    
                    # 9. Delete split course invites
                    try:
                        ClassSplitInvite.query.filter(
                            (ClassSplitInvite.inviter_session_id == session_id) | 
                            (ClassSplitInvite.invited_session_id == session_id)
                        ).delete(synchronize_session=False)
                    except Exception as e:
                        current_app.logger.warning(f'Error deleting ClassSplitInvite for session {session_id}: {e}')
                    
                    # 10. Finally delete the session itself as fallback
                    db.session.delete(session_obj)
                    db.session.flush()
                    current_app.logger.warning(f'Deleted session {session_id} as fallback after archiving failed')
                except Exception as delete_error:
                    db.session.rollback()
                    current_app.logger.error(f'Failed to delete session {session_id} as fallback: {delete_error}', exc_info=True)

        # Delete the assignment (even if session cleanup had issues)
        try:
            db.session.delete(assignment)
            db.session.commit()
            current_app.logger.info(f'Successfully unassigned teacher from assignment {assignment_id}')
            return jsonify({'success': True, 'message': 'টিচার সফলভাবে আনএসাইন করা হয়েছে।'})
        except Exception as delete_error:
            db.session.rollback()
            current_app.logger.error(f'Failed to delete assignment {assignment_id}: {delete_error}', exc_info=True)
            raise delete_error
    except Exception as exc:
        db.session.rollback()
        error_msg = str(exc)
        current_app.logger.error(f'Failed to unassign teacher from assignment {assignment_id}: {exc}', exc_info=True)
        
        # Provide more user-friendly error message
        if 'foreign key' in error_msg.lower() or 'constraint' in error_msg.lower():
            return jsonify({
                'success': False, 
                'message': 'এই অ্যাসাইনমেন্টটি অন্য রেকর্ডের সাথে যুক্ত থাকায় মুছে ফেলা যায়নি। অনুগ্রহ করে অ্যাডমিনের সাথে যোগাযোগ করুন।'
            }), 500
        else:
            return jsonify({
                'success': False, 
                'message': f'টিচার আনএসাইন করতে ব্যর্থ হয়েছে: {error_msg}'
            }), 500


@course_management_bp.route('/api/replace-teacher-session', methods=['POST'])
@login_required
def replace_teacher_session():
    """Replace teacher in assignment while keeping all other data intact"""
    try:
        data = request.get_json() or {}
        assignment_id = data.get('assignment_id')
        new_teacher_id = data.get('new_teacher_id')
        
        # Validation
        if not assignment_id:
            return jsonify({'success': False, 'message': 'Assignment ID is required.'}), 400
        
        if not new_teacher_id:
            return jsonify({'success': False, 'message': 'New Teacher ID is required.'}), 400
        
        try:
            assignment_id = int(assignment_id)
            new_teacher_id = int(new_teacher_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid ID format.'}), 400
        
        # Get assignment
        assignment = CourseSessionAssignment.query.get(assignment_id)
        if not assignment:
            return jsonify({'success': False, 'message': 'Assignment not found.'}), 404
        
        # Get new teacher
        new_teacher = Teacher.query.get(new_teacher_id)
        if not new_teacher:
            return jsonify({'success': False, 'message': 'New teacher not found.'}), 404
        
        # Check if new teacher is same as current teacher
        if assignment.teacher_id == new_teacher_id:
            return jsonify({'success': False, 'message': 'New teacher is same as current teacher.'}), 400
        
        old_teacher_id = assignment.teacher_id
        old_teacher = Teacher.query.get(old_teacher_id)
        
        # Update assignment
        assignment.teacher_id = new_teacher_id
        assignment.updated_at = datetime.utcnow()
        
        # Update session if exists
        if assignment.session_id:
            session_obj = Session.query.get(assignment.session_id)
            if session_obj:
                session_obj.teacher_id = new_teacher_id
                current_app.logger.info(f'Updated session {session_obj.id} teacher from {old_teacher_id} to {new_teacher_id}')
                
                # Update all ClassStudent records in this session
                ClassStudent.query.filter_by(session_id=session_obj.id).update({
                    'teacher_id': new_teacher_id
                })
                current_app.logger.info(f'Updated ClassStudent records in session {session_obj.id} to new teacher {new_teacher_id}')
        
        db.session.commit()
        
        old_teacher_name = old_teacher.name if old_teacher else f'Teacher ID: {old_teacher_id}'
        new_teacher_name = new_teacher.name
        
        current_app.logger.info(f'Successfully replaced teacher in assignment {assignment_id}: {old_teacher_name} -> {new_teacher_name}')
        
        return jsonify({
            'success': True,
            'message': f'টিচার সফলভাবে পরিবর্তন করা হয়েছে: {old_teacher_name} → {new_teacher_name}'
        })
        
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to replace teacher: {exc}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'টিচার পরিবর্তন করতে ব্যর্থ হয়েছে: {str(exc)}'
        }), 500


@course_management_bp.route('/api/course/<int:course_id>/assignments', methods=['GET'])
@login_required
def get_course_assignments(course_id):
    """Return existing assignments for a course."""
    try:
        assignments = CourseSessionAssignment.query.filter_by(course_id=course_id).order_by(
            CourseSessionAssignment.created_at.desc()
        ).all()

        data = []
        for assignment in assignments:
            teacher_name = assignment.teacher.name if hasattr(assignment, 'teacher') and assignment.teacher else None
            data.append({
                'id': assignment.id,
                'teacher_id': assignment.teacher_id,
                'teacher_name': teacher_name,
                'section': assignment.section or '',
                'batch': assignment.batch or '',
                'academic_session': assignment.academic_session or '',
                'session_created': assignment.session_created,
                'created_at': assignment.created_at.strftime('%Y-%m-%d %H:%M') if assignment.created_at else ''
            })

        return jsonify({'success': True, 'assignments': data})
    except Exception as exc:
        current_app.logger.error(f'Failed to fetch course assignments: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to load assignments.'}), 500
