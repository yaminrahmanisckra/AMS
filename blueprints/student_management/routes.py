from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required
from sqlalchemy import or_
import pandas as pd
from . import student_management_bp
from .models import Student
from extensions import db
from blueprints.course_management.models import (
    Curriculum,
    StudentCourseRegistration,
    CourseRegistrationInvite,
    DutyAssignment,
)
from user_models import User
from role_utils import parse_roles, serialize_roles


def _generate_student_email(preferred_email, student_id):
    base = (preferred_email or '').strip()
    if not base:
        base = f"{student_id}@students.local"
    email = base
    counter = 1
    while User.query.filter_by(email=email).first():
        local, sep, domain = email.partition('@')
        if not sep:
            domain = 'students.local'
        email = f"{local}+{counter}@{domain}"
        counter += 1
    return email


def ensure_student_user(student):
    username = (student.student_id or '').strip()
    if not username:
        return

    default_password = current_app.config.get('DEFAULT_STUDENT_PASSWORD', 'Student@123')
    account = User.query.filter_by(username=username).first()
    if not account:
        email = _generate_student_email(student.email, username)
        account = User(
            username=username,
            email=email,
            full_name=student.name or username,
            role='student'
        )
        account.set_password(default_password)
        db.session.add(account)
        db.session.flush()
        return

    updated = False
    roles = parse_roles(account.role)
    if 'student' not in roles:
        roles.append('student')
        account.role = serialize_roles(roles)
        updated = True

    if student.name and account.full_name != student.name:
        account.full_name = student.name
        updated = True

    new_email = (student.email or '').strip()
    if new_email and account.email != new_email:
        conflict = User.query.filter(User.email == new_email, User.id != account.id).first()
        if not conflict:
            account.email = new_email
            updated = True

    if updated:
        db.session.flush()

@student_management_bp.route('/')
@login_required
def index():
    """List all students"""
    search = request.args.get('search', '').strip()
    batch_filter = request.args.get('batch', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Student.query
    
    # Apply batch filter
    if batch_filter:
        query = query.filter(Student.batch == batch_filter)
    
    # Apply search filter
    if search:
        query = query.filter(
            or_(
                Student.name.ilike(f'%{search}%'),
                Student.student_id.ilike(f'%{search}%'),
                Student.batch.ilike(f'%{search}%'),
                Student.email.ilike(f'%{search}%'),
                Student.hall.ilike(f'%{search}%')
            )
        )
    
    students = query.order_by(Student.student_id.asc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get all distinct batches for the filter dropdown
    all_batches = db.session.query(Student.batch).distinct().filter(Student.batch.isnot(None)).order_by(Student.batch.desc()).all()
    batches = [batch[0] for batch in all_batches]
    
    # Get all curricula and create a mapping of batch to curricula
    all_curricula = Curriculum.query.all()
    batch_to_curricula = {}
    for curriculum in all_curricula:
        applicable_batches = curriculum.get_batches_list()
        for batch in applicable_batches:
            if batch not in batch_to_curricula:
                batch_to_curricula[batch] = []
            batch_to_curricula[batch].append(curriculum)
    
    return render_template('student_management/index.html', 
                         students=students, 
                         search=search,
                         batch_filter=batch_filter,
                         batches=batches,
                         batch_to_curricula=batch_to_curricula)

@student_management_bp.route('/add', methods=['POST'])
@login_required
def add_student():
    """Add a new student via AJAX (modal)"""
    student_id = request.form.get('student_id', '').strip()
    name = request.form.get('name', '').strip()
    batch = request.form.get('batch', '').strip() or None
    hall = request.form.get('hall', '').strip() or None
    email = request.form.get('email', '').strip() or None
    phone = request.form.get('phone', '').strip() or None
    
    if not student_id or not name:
        return jsonify({'success': False, 'message': 'Student ID and Name are required.'}), 400
    
    # Check if student_id already exists
    existing = Student.query.filter_by(student_id=student_id).first()
    if existing:
        return jsonify({'success': False, 'message': f'Student with ID {student_id} already exists.'}), 400
    
    try:
        student = Student(
            student_id=student_id,
            name=name,
            batch=batch,
            hall=hall,
            email=email,
            phone=phone
        )
        db.session.add(student)
        ensure_student_user(student)
        db.session.commit()
        default_password = current_app.config.get('DEFAULT_STUDENT_PASSWORD', 'Student@123')
        return jsonify({
            'success': True,
            'message': f'Student {name} ({student_id}) added successfully! Default password: {default_password}',
            'default_password': default_password
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error adding student: {str(e)}'}), 500

@student_management_bp.route('/edit/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    """Edit a student"""
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        original_student_id = student.student_id
        student_id_new = request.form.get('student_id', '').strip()
        name = request.form.get('name', '').strip()
        batch = request.form.get('batch', '').strip() or None
        hall = request.form.get('hall', '').strip() or None
        email = request.form.get('email', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        
        if not student_id_new or not name:
            flash('Student ID and Name are required.', 'error')
            return redirect(url_for('student_management.edit_student', student_id=student_id))
        
        # Check if student_id already exists (for different student)
        if student_id_new != student.student_id:
            existing = Student.query.filter_by(student_id=student_id_new).first()
            if existing:
                flash(f'Student with ID {student_id_new} already exists.', 'error')
                return redirect(url_for('student_management.edit_student', student_id=student_id))
        
        try:
            student.student_id = student_id_new
            student.name = name
            student.batch = batch
            student.hall = hall
            student.email = email
            student.phone = phone
            if student_id_new != original_student_id:
                linked_account = User.query.filter_by(username=original_student_id).first()
                if linked_account:
                    linked_account.username = student_id_new
            ensure_student_user(student)
            db.session.commit()
            flash(f'Student {name} updated successfully!', 'success')
            return redirect(url_for('student_management.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'error')
            return redirect(url_for('student_management.edit_student', student_id=student_id))
    
    return render_template('student_management/edit_student.html', student=student)

@student_management_bp.route('/delete/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    """Delete a student"""
    student = Student.query.get_or_404(student_id)
    
    try:
        name = student.name
        student_id_val = student.student_id

        # 1) Delete course registrations (and cascaded invites) for this student
        registrations = StudentCourseRegistration.query.filter_by(student_id=student.id).all()
        for reg in registrations:
            db.session.delete(reg)

        # 2) Delete any remaining invites that reference this student directly
        invites = CourseRegistrationInvite.query.filter_by(student_id=student.id).all()
        for invite in invites:
            db.session.delete(invite)

        # 3) Detach the student from any duty assignments (set nullable FK to NULL)
        duties = DutyAssignment.query.filter_by(student_id=student.id).all()
        for duty in duties:
            duty.student_id = None

        # 4) Clean up linked login account / roles
        account = User.query.filter_by(username=student.student_id).first()
        if account:
            roles = parse_roles(account.role)
            if 'student' in roles:
                roles.remove('student')
                if roles:
                    account.role = serialize_roles(roles)
                else:
                    db.session.delete(account)
        db.session.delete(student)
        db.session.commit()
        flash(f'Student {name} ({student_id_val}) deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'error')
    
    return redirect(url_for('student_management.index'))

@student_management_bp.route('/bulk-upload', methods=['POST'])
@login_required
def bulk_upload():
    """Bulk upload students from Excel file"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded!'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected!'}), 400
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)!'}), 400
    
    try:
        df = pd.read_excel(file)
        # Clean and normalize column names
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
        
        # Map various possible column names
        column_mapping = {
            'student_id': ['student_id', 'id', 'studentid', 'student_id'],
            'name': ['name', 'student_name', 'full_name', 'fullname'],
            'batch': ['batch', 'year', 'batch_year'],
            'email': ['email', 'e_mail', 'email_address'],
            'phone': ['phone', 'phone_number', 'mobile', 'contact', 'phone_no'],
            'hall': ['hall', 'hall_name', 'residence_hall']
        }
        
        # Find actual column names
        actual_columns = {}
        for key, possible_names in column_mapping.items():
            for col in df.columns:
                if col in possible_names:
                    actual_columns[key] = col
                    break
        
        if 'student_id' not in actual_columns or 'name' not in actual_columns:
            return jsonify({
                'success': False, 
                'message': 'Excel file must have columns: Student ID and Name. Found columns: ' + ', '.join(df.columns)
            }), 400
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        # Get all existing student IDs in one query
        existing_student_ids = {s.student_id for s in Student.query.with_entities(Student.student_id).all()}
        
        for idx, row in df.iterrows():
            try:
                student_id = str(row[actual_columns['student_id']]).strip()
                name = str(row[actual_columns['name']]).strip()
                
                if not student_id or not name or student_id == 'nan' or name == 'nan':
                    continue
                
                # Check if already exists
                if student_id in existing_student_ids:
                    skipped_count += 1
                    existing_student = Student.query.filter_by(student_id=student_id).first()
                    if existing_student:
                        ensure_student_user(existing_student)
                    continue
                
                batch = None
                if 'batch' in actual_columns:
                    batch_val = row[actual_columns['batch']]
                    if pd.notna(batch_val):
                        batch = str(batch_val).strip() or None
                
                hall = None
                if 'hall' in actual_columns:
                    hall_val = row[actual_columns['hall']]
                    if pd.notna(hall_val):
                        hall = str(hall_val).strip() or None
                
                email = None
                if 'email' in actual_columns:
                    email_val = row[actual_columns['email']]
                    if pd.notna(email_val):
                        email = str(email_val).strip() or None
                
                phone = None
                if 'phone' in actual_columns:
                    phone_val = row[actual_columns['phone']]
                    if pd.notna(phone_val):
                        phone = str(phone_val).strip() or None
                
                student = Student(
                    student_id=student_id,
                    name=name,
                    batch=batch,
                    hall=hall,
                    email=email,
                    phone=phone
                )
                db.session.add(student)
                ensure_student_user(student)
                existing_student_ids.add(student_id)  # Add to set to avoid duplicates in same upload
                added_count += 1
            except Exception as e:
                errors.append(f'Row {idx + 2}: {str(e)}')
                continue
        
        db.session.commit()
        
        default_password = current_app.config.get('DEFAULT_STUDENT_PASSWORD', 'Student@123')
        message = f'Successfully added {added_count} students.'
        if skipped_count > 0:
            message += f' Skipped {skipped_count} existing students.'
        if errors:
            message += f' {len(errors)} errors occurred.'
        if added_count > 0:
            message += f' Default password for new student logins: {default_password}'
        
        return jsonify({
            'success': True, 
            'message': message,
            'added': added_count,
            'skipped': skipped_count,
            'errors': errors[:10],  # Limit errors shown
            'default_password': default_password
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error processing Excel file: {str(e)}'}), 500


        # Find actual column names
        actual_columns = {}
        for key, possible_names in column_mapping.items():
            for col in df.columns:
                if col in possible_names:
                    actual_columns[key] = col
                    break
        
        if 'student_id' not in actual_columns or 'name' not in actual_columns:
            return jsonify({
                'success': False, 
                'message': 'Excel file must have columns: Student ID and Name. Found columns: ' + ', '.join(df.columns)
            }), 400
        
        added_count = 0
        skipped_count = 0
        errors = []
        
        # Get all existing student IDs in one query
        existing_student_ids = {s.student_id for s in Student.query.with_entities(Student.student_id).all()}
        
        for idx, row in df.iterrows():
            try:
                student_id = str(row[actual_columns['student_id']]).strip()
                name = str(row[actual_columns['name']]).strip()
                
                if not student_id or not name or student_id == 'nan' or name == 'nan':
                    continue
                
                # Check if already exists
                if student_id in existing_student_ids:
                    skipped_count += 1
                    existing_student = Student.query.filter_by(student_id=student_id).first()
                    if existing_student:
                        ensure_student_user(existing_student)
                    continue
                
                batch = None
                if 'batch' in actual_columns:
                    batch_val = row[actual_columns['batch']]
                    if pd.notna(batch_val):
                        batch = str(batch_val).strip() or None
                
                hall = None
                if 'hall' in actual_columns:
                    hall_val = row[actual_columns['hall']]
                    if pd.notna(hall_val):
                        hall = str(hall_val).strip() or None
                
                email = None
                if 'email' in actual_columns:
                    email_val = row[actual_columns['email']]
                    if pd.notna(email_val):
                        email = str(email_val).strip() or None
                
                phone = None
                if 'phone' in actual_columns:
                    phone_val = row[actual_columns['phone']]
                    if pd.notna(phone_val):
                        phone = str(phone_val).strip() or None
                
                student = Student(
                    student_id=student_id,
                    name=name,
                    batch=batch,
                    hall=hall,
                    email=email,
                    phone=phone
                )
                db.session.add(student)
                ensure_student_user(student)
                existing_student_ids.add(student_id)  # Add to set to avoid duplicates in same upload
                added_count += 1
            except Exception as e:
                errors.append(f'Row {idx + 2}: {str(e)}')
                continue
        
        db.session.commit()
        
        default_password = current_app.config.get('DEFAULT_STUDENT_PASSWORD', 'Student@123')
        message = f'Successfully added {added_count} students.'
        if skipped_count > 0:
            message += f' Skipped {skipped_count} existing students.'
        if errors:
            message += f' {len(errors)} errors occurred.'
        if added_count > 0:
            message += f' Default password for new student logins: {default_password}'
        
        return jsonify({
            'success': True, 
            'message': message,
            'added': added_count,
            'skipped': skipped_count,
            'errors': errors[:10],  # Limit errors shown
            'default_password': default_password
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error processing Excel file: {str(e)}'}), 500

