from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from extensions import db
from .models import Teacher, Course, Room, AssignedCourse, Routine
from .forms import TeacherForm, CourseForm, RoomForm, AssignCourseForm
from datetime import datetime
from collections import defaultdict
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch

routine_management_bp = Blueprint('routine_management', __name__,
                                  template_folder='templates',
                                  static_folder='static')

# Main dashboard for routine management
@routine_management_bp.route('/')
def index():
    return render_template('routine_management/index.html')

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
    teachers = Teacher.query.order_by('name').all()
    return render_template('routine_management/teachers.html', form=form, teachers=teachers)

@routine_management_bp.route('/teacher/edit/<int:id>', methods=['POST'])
def edit_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    
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
        
    teacher.name = new_name
    teacher.short_name = new_short_name
    db.session.commit()
    flash('Teacher updated successfully!', 'success')
    return redirect(url_for('routine_management.manage_teachers'))

@routine_management_bp.route('/teacher/delete/<int:id>', methods=['POST'])
def delete_teacher(id):
    teacher = Teacher.query.get_or_404(id)
    
    try:
        # Delete assigned courses
        AssignedCourse.query.filter_by(teacher_id=id).delete()
        
        # Delete routine entries
        Routine.query.filter_by(teacher_id=id).delete()
        
        # Delete class sessions and their related data
        from blueprints.class_management.models import Session, ClassStudent, ClassAttendance
        sessions = Session.query.filter_by(teacher_id=id).all()
        for session in sessions:
            ClassAttendance.query.filter_by(session_id=session.id).delete()
            ClassStudent.query.filter_by(session_id=session.id).delete()
            db.session.delete(session)
        
        # Now delete the teacher
        db.session.delete(teacher)
        db.session.commit()
        flash('Teacher and all related data deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting teacher: {str(e)}', 'danger')
    
    return redirect(url_for('routine_management.manage_teachers'))

# Course Management
@routine_management_bp.route('/courses', methods=['GET', 'POST'])
def manage_courses():
    form = CourseForm()
    if form.validate_on_submit():
        new_course = Course(course_code=form.course_code.data, course_name=form.course_name.data, credit=form.credit.data, course_type=form.course_type.data, category=form.category.data)
        db.session.add(new_course)
        db.session.commit()
        flash('Course added successfully!', 'success')
        return redirect(url_for('routine_management.manage_courses'))
    courses = Course.query.order_by('course_code').all()
    return render_template('routine_management/courses.html', form=form, courses=courses)

@routine_management_bp.route('/course/delete/<int:id>', methods=['POST'])
def delete_course(id):
    course = Course.query.get_or_404(id)
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully!', 'success')
    return redirect(url_for('routine_management.manage_courses'))

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
def delete_room(id):
    room = Room.query.get_or_404(id)
    db.session.delete(room)
    db.session.commit()
    flash('Room deleted successfully!', 'success')
    return redirect(url_for('routine_management.manage_rooms'))

# Course Assignment
@routine_management_bp.route('/assign_course', methods=['GET', 'POST'])
def assign_course():
    form = AssignCourseForm()
    form.teacher.choices = [(t.id, f"{t.name} ({t.short_name})") for t in Teacher.query.order_by('name').all()]

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
    form.teacher.choices = [(t.id, f"{t.name} ({t.short_name})") for t in Teacher.query.order_by('name').all()]
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
def delete_assignment(id):
    assignment = AssignedCourse.query.get_or_404(id)
    db.session.delete(assignment)
    db.session.commit()
    flash('Course assignment deleted successfully!', 'success')
    return redirect(url_for('routine_management.assign_course'))

# Generate Routine
@routine_management_bp.route('/generate_routine')
def generate_routine():
    teachers_list = Teacher.query.order_by('name').all()
    teachers = [{'id': t.id, 'name': t.name, 'short_name': t.short_name} for t in teachers_list]
    
    rooms = Room.query.order_by('room_number').all()
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]
    return render_template('routine_management/routine.html', 
                           teachers=teachers, rooms=rooms, days=days, 
                           time_slots=time_slots)

# --- API Endpoints for Routine ---

@routine_management_bp.route('/api/teacher_courses/<int:teacher_id>')
def teacher_courses(teacher_id):
    assigned_courses = AssignedCourse.query.filter_by(teacher_id=teacher_id).all()
    courses_data = []

    for a in assigned_courses:
        # Special handling for 3-credit shared courses
        if a.course.credit == 3.0 and a.part in ['Part A', 'Part B']:
            courses_data.append({
                'assigned_id': str(a.id),
                'course_code': a.course.course_code,
                'course_name': a.course.course_name,
                'course_type': a.course.course_type,
                'part': a.part,
                'classes_per_week': 1,
                'is_shared_slot': False,
                'teachers': [{'id': a.teacher.id, 'name': a.teacher.name, 'short_name': a.teacher.short_name}]
            })

            if a.part == 'Part A':
                other_assignment = AssignedCourse.query.filter(
                    AssignedCourse.course_id == a.course_id,
                    AssignedCourse.part == 'Part B'
                ).first()

                if other_assignment:
                    courses_data.append({
                        'assigned_id': str(a.id),
                        'course_code': a.course.course_code,
                        'course_name': f"{a.course.course_name} (Shared)",
                        'course_type': a.course.course_type,
                        'part': 'Shared',
                        'classes_per_week': 1,
                        'is_shared_slot': True,
                        'teachers': [
                            {'id': a.teacher.id, 'name': a.teacher.name, 'short_name': a.teacher.short_name},
                            {'id': other_assignment.teacher.id, 'name': other_assignment.teacher.name, 'short_name': other_assignment.teacher.short_name}
                        ]
                    })
        
        else: # Logic for all other courses
            credit = float(a.course.credit)
            
            if a.course.course_type == 'Sessional':
                total_classes = int(credit * 2)
            else:
                total_classes = int(credit)
            
            if a.part != 'Full':
                classes_for_part = (total_classes + 1) // 2
            else:
                classes_for_part = total_classes
            
            courses_data.append({
                'assigned_id': str(a.id),
                'course_code': a.course.course_code,
                'course_name': a.course.course_name,
                'course_type': a.course.course_type,
                'part': a.part,
                'classes_per_week': classes_for_part,
                'is_shared_slot': False,
                'teachers': [{'id': a.teacher.id, 'name': a.teacher.name, 'short_name': a.teacher.short_name}]
            })
            
    return jsonify(courses_data)

@routine_management_bp.route('/api/get_teachers')
def get_teachers():
    teachers_list = Teacher.query.order_by('name').all()
    return jsonify([{'id': t.id, 'name': t.name, 'short_name': t.short_name} for t in teachers_list])

@routine_management_bp.route('/api/routine/save', methods=['POST'])
def save_routine():
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
            teacher_id=entry.get('teacher_id')
        )
        db.session.add(new_entry)
    
    db.session.commit()
    return jsonify({'message': 'Routine saved successfully!'}), 200

@routine_management_bp.route('/api/routine/clear', methods=['POST'])
def clear_routine():
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
    
    # Need to get all rooms to map room_number back to room_id for the frontend
    all_rooms = {r.room_number: r.id for r in Room.query.all()}

    routine_data = []
    for entry in routine_entries:
        # Reconstruct the nested teacher objects for shared courses
        teachers_info = []
        if entry.is_shared and entry.shared_with:
            short_names = [name.strip() for name in entry.shared_with.split('/')]
            all_involved_teachers = Teacher.query.filter(Teacher.short_name.in_(short_names)).all()
            teachers_info = [{'id': t.id, 'name': t.name, 'short_name': t.short_name} for t in all_involved_teachers]
        elif entry.teacher_id:
            teacher = Teacher.query.get(entry.teacher_id)
            if teacher:
                teachers_info = [{'id': teacher.id, 'name': teacher.name, 'short_name': teacher.short_name}]

        routine_data.append({
            "day": entry.day,
            "slot": entry.time_slot, # Corrected: time_slot -> slot
            "room_id": all_rooms.get(entry.room_number), # Map back to ID
            "course_code": entry.course_code,
            "teacher_short_name": entry.teacher_short_name,
            "part": entry.part,
            "is_shared": entry.is_shared,
            "shared_with": entry.shared_with,
            "teacher_id": entry.teacher_id,
            "teachers": teachers_info
        })

    return jsonify(routine_data)

@routine_management_bp.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.get_json()
    routine_list = data.get('routine', [])
    title_text = request.args.get('title', 'Class Routine')
    date_text = request.args.get('date', '')

    # Create a mapping from the list for easy lookup
    routine_map = {
        (item['day'], item['slot'], item['room_id']): item
        for item in routine_list
    }

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    h1_centered = ParagraphStyle(name='h1_centered', parent=styles['h1'], alignment=TA_CENTER)
    h2_centered = ParagraphStyle(name='h2_centered', parent=styles['h2'], alignment=TA_CENTER)
    h3_centered = ParagraphStyle(name='h3_centered', parent=styles['h3'], alignment=TA_CENTER)
    
    body_text_style = ParagraphStyle(name='BodyText', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8)

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
    elements.append(Spacer(1, 0.2*inch))

    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]
    rooms_db = Room.query.order_by('room_number').all()
    
    table_data = []
    # Header row
    header = ['Day/Room'] + [slot.replace(' - ', '\n') for slot in time_slots]
    table_data.append(header)

    # Data rows
    for day in days:
        for i, room in enumerate(rooms_db):
            row_label = f"<b>{day}</b>" if i == 0 else ''
            row_label += f"<br/>{room.room_number}" if i == 0 else room.room_number
            row = [Paragraph(row_label, body_text_style)]

            for slot in time_slots:
                cell_data = routine_map.get((day, slot, room.id))
                if cell_data:
                    cell_content = f"<b>{cell_data.get('course_code', '')}</b><br/>({cell_data.get('teacher_short_name', '')})"
                    row.append(Paragraph(cell_content, body_text_style))
                else:
                    row.append("")
            table_data.append(row)

    col_widths = [1.2*inch] + [1.25*inch] * len(time_slots)

    table = Table(table_data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Span the day cell
    ])

    # Apply row span for day cells and thicker border for day starts
    num_rooms = len(rooms_db) if rooms_db else 1
    for i, day in enumerate(days):
        start_row = 1 + (i * num_rooms)
        end_row = start_row + num_rooms - 1
        
        # Add thick border above each day's first row
        if start_row > 1: # Don't add for the very first day row
             style.add('LINEABOVE', (0, start_row), (-1, start_row), 2, colors.black)

        if num_rooms > 1:
            style.add('SPAN', (0, start_row), (0, end_row))
            style.add('VALIGN', (0, start_row), (0, end_row), 'MIDDLE')


    table.setStyle(style)
    elements.append(table)
    
    doc.build(elements)
    
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment;filename=routine_{title_text.replace(" ", "_")}.pdf'
    })

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
    elements.append(Spacer(1, 0.2*inch))

    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]
    rooms_db = Room.query.order_by('room_number').all()
    
    table_data = []
    # Header row
    header = ['Day/Room'] + [slot.replace(' - ', '\n') for slot in time_slots]
    table_data.append(header)

    # Data rows
    for day in days:
        for i, room in enumerate(rooms_db):
            row_label = f"<b>{day}</b>" if i == 0 else ''
            row_label += f"<br/>{room.room_number}" if i == 0 else room.room_number
            row = [Paragraph(row_label, body_text_style)]

            for slot in time_slots:
                cell_data = routine_map.get((day, slot, room.id))
                if cell_data:
                    cell_content = f"<b>{cell_data.get('course_code', '')}</b><br/>({cell_data.get('teacher_short_name', '')})"
                    row.append(Paragraph(cell_content, body_text_style))
                else:
                    row.append("")
            table_data.append(row)

    col_widths = [1.2*inch] + [1.25*inch] * len(time_slots)

    table = Table(table_data, colWidths=col_widths)
    
    style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        # Span the day cell
    ])

    # Apply row span for day cells and thicker border for day starts
    num_rooms = len(rooms_db) if rooms_db else 1
    for i, day in enumerate(days):
        start_row = 1 + (i * num_rooms)
        end_row = start_row + num_rooms - 1
        
        # Add thick border above each day's first row
        if start_row > 1: # Don't add for the very first day row
             style.add('LINEABOVE', (0, start_row), (-1, start_row), 2, colors.black)

        if num_rooms > 1:
            style.add('SPAN', (0, start_row), (0, end_row))
            style.add('VALIGN', (0, start_row), (0, end_row), 'MIDDLE')


    table.setStyle(style)
    elements.append(table)
    
    doc.build(elements)
    
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment;filename=routine_{title_text.replace(" ", "_")}.pdf'
    })
