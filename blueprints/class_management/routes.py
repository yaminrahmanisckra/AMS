from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import db, Teacher, Session, ClassStudent, ClassAttendance
from models import User  # Import the User model from the new models file
import pandas as pd
import os
from datetime import datetime, date
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from collections import Counter, defaultdict
from reportlab.lib.units import inch
import io
from reportlab.lib.enums import TA_CENTER

class_management_bp = Blueprint(
    'class_management', __name__,
    template_folder='templates',
    static_folder='static'
)

# Create uploads folder if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@class_management_bp.route('/')
@login_required
def index():
    """Main dashboard for class management"""
    # Get or create teacher for current user
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        # Generate a simple short_name from the user's full name
        short_name = current_user.full_name.split(' ')[0].lower()
        teacher = Teacher(name=current_user.full_name, short_name=short_name)
        db.session.add(teacher)
        db.session.commit()
    
    # Get active sessions for this teacher
    sessions = Session.query.filter_by(teacher_id=teacher.id, archived=False).order_by(Session.created_at.desc()).all()
    
    return render_template('class_management/index.html', sessions=sessions, teacher=teacher)

@class_management_bp.route('/create_session', methods=['POST'])
@login_required
def create_session():
    """Create a new session"""
    # Get or create teacher for current user
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        short_name = current_user.full_name.split(' ')[0].lower()
        teacher = Teacher(name=current_user.full_name, short_name=short_name)
        db.session.add(teacher)
        db.session.commit()
    
    year = request.form.get('year')
    term = request.form.get('term')
    academic_session = request.form.get('academic_session')
    course_name = request.form.get('course_name')
    course_type = request.form.get('course_type', 'theory')
    category = request.form.get('category', 'ug')
    
    if not year or not term:
        flash('Year and term are required!', 'error')
        return redirect(url_for('class_management.index'))
    
    session_obj = Session(
        year=year, 
        term=term, 
        academic_session=academic_session, 
        course_name=course_name, 
        teacher_id=teacher.id, 
        course_type=course_type, 
        category=category
    )
    db.session.add(session_obj)
    db.session.commit()
    flash('Session created successfully!', 'success')
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/upload_students/<int:session_id>', methods=['POST'])
@login_required
def upload_students(session_id):
    """Upload students from Excel file"""
    # Get or create teacher for current user
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        teacher = Teacher(name=current_user.full_name)
        db.session.add(teacher)
        db.session.commit()
    
    if 'file' not in request.files:
        flash('No file uploaded!', 'error')
        return redirect(url_for('class_management.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected!', 'error')
        return redirect(url_for('class_management.index'))
    
    if not file.filename.endswith('.xlsx'):
        flash('Please upload an Excel file!', 'error')
        return redirect(url_for('class_management.index'))
    
    try:
        df = pd.read_excel(file)
        # Clean and normalize column names
        df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
        if 'student_id' not in df.columns or 'name' not in df.columns:
            raise Exception('Excel file must have columns: Student ID, Name')
        
        session = Session.query.get_or_404(session_id)
        for _, row in df.iterrows():
            student = ClassStudent(
                student_id=str(row['student_id']),
                name=row['name'],
                session_id=session.id,
                teacher_id=teacher.id
            )
            db.session.add(student)
        db.session.commit()
        flash('Students uploaded successfully!', 'success')
    except Exception as e:
        flash(f'Error uploading students: {str(e)}', 'error')
    
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/take_attendance/<int:session_id>', methods=['GET', 'POST'])
@login_required
def take_attendance(session_id):
    """Take or update attendance for a session."""
    session = Session.query.get_or_404(session_id)
    students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
    
    if request.method == 'POST':
        try:
            date_val = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            double_class = request.form.get('double_class') == '1'
            
            # Overwrite logic: Delete existing records for this date first
            ClassAttendance.query.filter_by(session_id=session_id, date=date_val).delete()
            
            # Add new records
            for student in students:
                is_present = request.form.get(f'student_{student.id}') == 'present'
                num_classes = 2 if double_class else 1
                for _ in range(num_classes):
                    db.session.add(ClassAttendance(
                        date=date_val,
                        is_present=is_present,
                        student_id=student.id,
                        session_id=session_id,
                        teacher_id=session.teacher_id
                    ))
            
            db.session.commit()
            flash('Attendance saved successfully!', 'success')
            return redirect(url_for('class_management.view_attendance', session_id=session_id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving attendance for session {session_id}: {e}")
            flash(f'Error saving attendance: {str(e)}', 'error')
            return redirect(url_for('class_management.take_attendance', session_id=session_id, date=request.form.get('date')))

    # GET request logic
    try:
        selected_date_str = request.args.get('date', date.today().strftime('%Y-%m-%d'))
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()

        # Fetch existing records for the selected date
        existing_records = ClassAttendance.query.filter_by(
            session_id=session_id,
            date=selected_date
        ).all()
        
        # Prepare data for the template
        attendance_status = {}
        is_double_class = False
        if existing_records:
            # Check if it was a double class
            student_counts = defaultdict(int)
            for record in existing_records:
                student_counts[record.student_id] += 1
            if student_counts and max(student_counts.values()) > 1:
                is_double_class = True
            
            # Get the attendance status for each student
            for student in students:
                # A student is marked 'present' if they have at least one present record on that day
                is_present = any(r.is_present for r in existing_records if r.student_id == student.id)
                attendance_status[student.id] = is_present

        return render_template('class_management/take_attendance.html', 
                                session=session, 
                                students=students, 
                                today=selected_date_str,
                                attendance_status=attendance_status,
                                is_double_class=is_double_class)
    except Exception as e:
        current_app.logger.error(f"Error loading attendance page for session {session_id}: {e}")
        flash(f'Error loading attendance page: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))

@class_management_bp.route('/view_attendance/<int:session_id>')
@login_required
def view_attendance(session_id):
    """View attendance for a session and display a detailed report."""
    session = Session.query.get_or_404(session_id)
    students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
    
    all_attendance_records = ClassAttendance.query.filter_by(session_id=session_id).order_by(ClassAttendance.date, ClassAttendance.id).all()

    if not all_attendance_records:
        return render_template('class_management/view_attendance.html', 
                               session=session, students=students, headers=[], student_report_data=[], unique_dates=[])

    # Group attendance by date to determine daily class counts
    attendance_by_date = defaultdict(list)
    for record in all_attendance_records:
        attendance_by_date[record.date].append(record)
    
    unique_dates_for_modal = sorted(attendance_by_date.keys(), reverse=True)
        
    daily_class_counts = {}
    for date, records in attendance_by_date.items():
        student_counts_on_date = defaultdict(int)
        for record in records:
            student_counts_on_date[record.student_id] += 1
        if student_counts_on_date:
            daily_class_counts[date] = max(student_counts_on_date.values())
            
    # Create dynamic headers
    headers = []
    sorted_dates = sorted(daily_class_counts.keys())
    for date in sorted_dates:
        count = daily_class_counts.get(date, 0)
        if count == 1:
            headers.append(date.strftime('%b %d, %Y'))
        else:
            for i in range(1, count + 1):
                headers.append(f"{date.strftime('%b %d')} ({i})")

    total_classes_held = sum(daily_class_counts.values())

    # Process data for each student
    student_report_data = []
    for student in students:
        student_records = [r for r in all_attendance_records if r.student_id == student.id]
        
        present_count = sum(1 for r in student_records if r.is_present)
        
        percentage = (present_count / total_classes_held * 100) if total_classes_held > 0 else 0
        
        # Determine marks based on percentage
        if percentage >= 90: marks = 10
        elif percentage >= 80: marks = 9
        elif percentage >= 70: marks = 8
        elif percentage >= 60: marks = 7
        else: marks = 0

        # Create attendance row for the table ('P' or 'A')
        attendance_row = []
        student_attendance_by_date = defaultdict(list)
        for r in student_records:
            student_attendance_by_date[r.date].append(r)

        for date in sorted_dates:
            records_for_date = student_attendance_by_date[date]
            num_classes_on_day = daily_class_counts.get(date, 0)
            
            for i in range(num_classes_on_day):
                if i < len(records_for_date):
                    attendance_row.append('P' if records_for_date[i].is_present else 'A')
                else:
                    attendance_row.append('-') # Mark as '-' if student has no record for a held class

        student_data = {
            'info': student,
            'attendance_row': attendance_row,
            'total_classes': total_classes_held,
            'present_count': present_count,
            'percentage': f"{percentage:.2f}%",
            'marks': marks
        }
        student_report_data.append(student_data)
    
    return render_template('class_management/view_attendance.html', 
                           session=session, 
                           headers=headers, 
                           student_report_data=student_report_data,
                           unique_dates=unique_dates_for_modal)

@class_management_bp.route('/students/<int:session_id>')
@login_required
def students_list(session_id):
    """View students list for a session"""
    session = Session.query.get_or_404(session_id)
    students = ClassStudent.query.filter_by(session_id=session_id).all()
    return render_template('class_management/students_list.html', 
                         session=session, students=students)

@class_management_bp.route('/add_student/<int:session_id>', methods=['POST'])
@login_required
def add_student(session_id):
    """Add a single student to a session"""
    session = Session.query.get_or_404(session_id)
    student_id = request.form.get('student_id')
    name = request.form.get('name')
    
    if not student_id or not name:
        flash('Student ID and name are required!', 'error')
        return redirect(url_for('class_management.students_list', session_id=session_id))
    
    # Get or create teacher for current user
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        teacher = Teacher(name=current_user.full_name)
        db.session.add(teacher)
        db.session.commit()
    
    student = ClassStudent(
        student_id=student_id,
        name=name,
        session_id=session.id,
        teacher_id=teacher.id
    )
    db.session.add(student)
    db.session.commit()
    flash('Student added successfully!', 'success')
    return redirect(url_for('class_management.students_list', session_id=session_id))

@class_management_bp.route('/edit_student/<int:student_id>', methods=['POST'])
@login_required
def edit_student(student_id):
    """Edit a student"""
    student = ClassStudent.query.get_or_404(student_id)
    student.student_id = request.form.get('student_id')
    student.name = request.form.get('name')
    db.session.commit()
    flash('Student updated successfully!', 'success')
    return redirect(url_for('class_management.students_list', session_id=student.session_id))

@class_management_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    """Delete a student"""
    student = ClassStudent.query.get_or_404(student_id)
    session_id = student.session_id
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('class_management.students_list', session_id=session_id))

@class_management_bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete a session"""
    session = Session.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Session deleted successfully!', 'success')
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/archive_session/<int:session_id>', methods=['POST'])
@login_required
def archive_session(session_id):
    """Archive a session"""
    session = Session.query.get_or_404(session_id)
    session.archived = True
    db.session.commit()
    flash('Session archived successfully!', 'success')
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/unarchive_session/<int:session_id>', methods=['POST'])
@login_required
def unarchive_session(session_id):
    """Unarchive a session"""
    session = Session.query.get_or_404(session_id)
    session.archived = False
    db.session.commit()
    flash('Session unarchived successfully!', 'success')
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/archive')
@login_required
def archive():
    """View archived sessions"""
    # Get or create teacher for current user
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        teacher = Teacher(name=current_user.full_name)
        db.session.add(teacher)
        db.session.commit()
    
    archived_sessions = Session.query.filter_by(teacher_id=teacher.id, archived=True).order_by(Session.created_at.desc()).all()
    return render_template('class_management/archive.html', sessions=archived_sessions)

@class_management_bp.route('/delete_attendance/<int:session_id>/<string:date_str>', methods=['POST'])
@login_required
def delete_attendance_by_date(session_id, date_str):
    """Delete all attendance records for a specific date."""
    try:
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        session = Session.query.get_or_404(session_id)
        
        if session.teacher.id != current_user.id:
            flash('You are not authorized to delete attendance for this session.', 'danger')
            return redirect(url_for('class_management.index'))
        
        # Count records before deletion
        records_to_delete = ClassAttendance.query.filter_by(
            session_id=session_id,
            date=attendance_date
        )
        
        if records_to_delete.count() == 0:
            flash(f'No attendance records found for {attendance_date.strftime("%b %d, %Y")}.', 'warning')
            return redirect(url_for('class_management.view_attendance', session_id=session_id))
            
        # Delete the records
        deleted_count = records_to_delete.delete()
        
        db.session.commit()
        
        flash(f'Successfully deleted {deleted_count} attendance records for {attendance_date.strftime("%b %d, %Y")}.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting attendance for session {session_id} on date {date_str}: {str(e)}")
        flash(f'Error deleting attendance: {str(e)}', 'danger')
        
    return redirect(url_for('class_management.view_attendance', session_id=session_id))

@class_management_bp.route('/download_attendance_excel/<int:session_id>')
@login_required
def download_attendance_excel(session_id):
    """Generate and download an Excel report of the attendance."""
    session = Session.query.get_or_404(session_id)
    students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
    all_attendance_records = ClassAttendance.query.filter_by(session_id=session_id).order_by(ClassAttendance.date, ClassAttendance.id).all()

    if not all_attendance_records:
        flash('No attendance data to download.', 'warning')
        return redirect(url_for('class_management.view_attendance', session_id=session_id))

    # This logic is similar to view_attendance, consider refactoring in a real app
    attendance_by_date = defaultdict(list)
    for record in all_attendance_records:
        attendance_by_date[record.date].append(record)
    
    daily_class_counts = {}
    for date, records in attendance_by_date.items():
        student_counts_on_date = defaultdict(int)
        for record in records:
            student_counts_on_date[record.student_id] += 1
        if student_counts_on_date:
            daily_class_counts[date] = max(student_counts_on_date.values())
            
    headers = []
    sorted_dates = sorted(daily_class_counts.keys())
    for dt in sorted_dates:
        count = daily_class_counts.get(dt, 0)
        if count == 1:
            headers.append(dt.strftime('%b %d, %Y'))
        else:
            for i in range(1, count + 1):
                headers.append(f"{dt.strftime('%b %d, %Y')} ({i})")

    # Prepare data for Excel
    data_for_excel = []
    total_classes_held = sum(daily_class_counts.values())

    for i, student in enumerate(students):
        student_attendance_records = [r for r in all_attendance_records if r.student_id == student.id]
        present_count = sum(1 for r in student_attendance_records if r.is_present)
        
        percentage = (present_count / total_classes_held * 100) if total_classes_held > 0 else 0
        
        marks = 0
        if percentage >= 90:
            marks = 10
        elif percentage >= 85:
            marks = 9
        elif percentage >= 80:
            marks = 8
        elif percentage >= 75:
            marks = 7
        elif percentage >= 70:
            marks = 6
        elif percentage >= 65:
            marks = 5
        elif percentage >= 60:
            marks = 4

        student_row = {
            '#': i + 1, 
            'Student ID': student.student_id, 
            'Name': student.name
        }
        
        # Initialize attendance row with placeholders
        attendance_statuses = ['-'] * len(headers)
        
        col_idx = 0
        for dt in sorted_dates:
            records_on_date = [r for r in student_attendance_records if r.date == dt]
            num_classes_on_date = daily_class_counts.get(dt, 0)
            
            for class_num in range(num_classes_on_date):
                if class_num < len(records_on_date):
                    attendance_statuses[col_idx] = 'P' if records_on_date[class_num].is_present else 'A'
                col_idx += 1

        for h, status in zip(headers, attendance_statuses):
            student_row[h] = status
            
        student_row['Total Classes'] = total_classes_held
        student_row['Present'] = present_count
        student_row['Percentage'] = f"{percentage:.2f}%"
        student_row['Marks'] = marks
            
        data_for_excel.append(student_row)

    df = pd.DataFrame(data_for_excel)
    
    # Create an in-memory Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance Report')
        # Auto-adjust columns width
        worksheet = writer.sheets['Attendance Report']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'attendance_report_{session.course_name}_{date.today()}.xlsx'
    )

@class_management_bp.route('/download_pdf_report/<int:session_id>')
@login_required
def download_pdf_report(session_id):
    """Generate and download a PDF summary report with headers and page numbers."""
    try:
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()

        buffer = io.BytesIO()
        
        # Define margins
        top_margin = 2.5 * inch
        bottom_margin = 0.7 * inch
        
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=0.5*inch, leftMargin=0.5*inch,
                                topMargin=top_margin, bottomMargin=bottom_margin)
        
        elements = []
        
        # --- Data Calculation (same as before) ---
        all_attendance_records = ClassAttendance.query.filter_by(session_id=session_id).all()
        attendance_by_date = defaultdict(list)
        for record in all_attendance_records:
            attendance_by_date[record.date].append(record)
        
        daily_class_counts = {}
        for date, records in attendance_by_date.items():
            if records:
                student_counts = defaultdict(int)
                for r in records:
                    student_counts[r.student_id] += 1
                daily_class_counts[date] = max(student_counts.values())
        total_classes_held = sum(daily_class_counts.values())

        student_data_for_pdf = []
        for student in students:
            present_count = sum(1 for r in all_attendance_records if r.student_id == student.id and r.is_present)
            percentage = (present_count / total_classes_held * 100) if total_classes_held > 0 else 0
            
            if percentage >= 90: attendance_marks = 10
            elif percentage >= 80: attendance_marks = 9
            elif percentage >= 70: attendance_marks = 8
            elif percentage >= 60: attendance_marks = 7
            else: attendance_marks = 0

            assessment_marks_display = student.assessment_total if student.assessment_total is not None else 0
            if session.course_type == 'theory' and session.category == 'pg':
                assessment_marks_display = student.assessment_total_40 if student.assessment_total_40 is not None else 0
            elif session.course_type == 'sessional':
                total = (student.sessional_report or 0) + (student.sessional_viva or 0)
                assessment_marks_display = total

            student_data_for_pdf.append({
                'id': student.student_id,
                'attendance': attendance_marks,
                'assessment': assessment_marks_display
            })

        # --- Table Creation (same as before) ---
        assessment_header_text = "Continuous Assessment (30)"
        if session.course_type == 'theory' and session.category == 'pg':
            assessment_header_text = "Continuous Assessment (40)"
        elif session.course_type == 'sessional':
             assessment_header_text = "Sessional Assessment (90)"

        table_data = [['ID', 'Attendance (10)', assessment_header_text]]
        for s_data in student_data_for_pdf:
            table_data.append([s_data['id'], s_data['attendance'], s_data['assessment']])
            
        table = Table(table_data, colWidths=[2*inch, 2*inch, 2.5*inch], repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F4F4F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F2F2F2')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        elements.append(table)
        
        # --- PDF Build with Canvas for Page Numbers ---
        from functools import partial

        class NumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                self.session_obj = kwargs.pop('session_obj', None)
                canvas.Canvas.__init__(self, *args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_header_footer(num_pages)
                    canvas.Canvas.showPage(self)
                canvas.Canvas.save(self)

            def draw_header_footer(self, page_count):
                self.saveState()
                width, height = self._pagesize
                
                # Header
                self.setFont('Helvetica-Bold', 18)
                self.drawCentredString(width / 2.0, height - 1.0*inch, "Khulna University")
                
                self.setFont('Helvetica', 12)
                self.drawCentredString(width / 2.0, height - 1.35*inch, "Law Discipline")
                self.drawCentredString(width / 2.0, height - 1.60*inch, "Continuous Assessment and Attendance Marks")
                
                self.setFont('Helvetica-Bold', 10)
                course_info = f"Course: {self.session_obj.course_name}  |  Type: {self.session_obj.course_type.capitalize()}"
                year_term_info = f"Year: {self.session_obj.year}, Term: {self.session_obj.term}  |  Session: {self.session_obj.academic_session}"

                self.drawCentredString(width / 2.0, height - 1.95*inch, course_info)
                self.drawCentredString(width / 2.0, height - 2.15*inch, year_term_info)
                
                # Footer - Page Number
                page_text = f"Page {self._pageNumber} of {page_count}"
                self.setFont('Helvetica', 9)
                self.drawRightString(width - 0.5*inch, 0.5*inch, page_text)
                
                self.restoreState()

        CustomCanvasMaker = partial(NumberedCanvas, session_obj=session)
        doc.build(elements, canvasmaker=CustomCanvasMaker)
        
        buffer.seek(0)
        filename = f"Report_{session.course_name}_{session.year}.pdf"
        return send_file(
            buffer, as_attachment=True, download_name=filename, mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error generating PDF for session {session_id}: {e}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))

@class_management_bp.route('/assessment/<int:session_id>', methods=['GET', 'POST'])
@login_required
def assessment(session_id):
    """Assessment management for a session"""
    try:
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).all()
        
        if request.method == 'POST':
            try:
                for student in students:
                    if session.course_type == 'theory' and session.category == 'ug':
                        # Handle theory course assessments
                        for i in range(1, 5):
                            value = request.form.get(f'assessment{i}_{student.id}')
                            if value:
                                setattr(student, f'assessment{i}', float(value))
                            else:
                                setattr(student, f'assessment{i}', None)
                        
                        # Calculate best 3 total
                        values = []
                        for i in range(1, 5):
                            val = getattr(student, f'assessment{i}')
                            if val is not None:
                                values.append(val)
                        if len(values) >= 3:
                            values.sort(reverse=True)
                            student.assessment_total = sum(values[:3])
                        else:
                            student.assessment_total = None

                    elif session.course_type == 'theory' and session.category == 'pg':
                        # Handle PG theory course assessments
                        for i in range(1, 5):
                            value = request.form.get(f'assessment{i}_{student.id}')
                            if value:
                                setattr(student, f'assessment{i}', float(value))
                            else:
                                setattr(student, f'assessment{i}', None)
                        
                        values = []
                        for i in range(1, 5):
                            val = getattr(student, f'assessment{i}')
                            if val is not None:
                                values.append(val)
                        if len(values) >= 3:
                            values.sort(reverse=True)
                            best3 = values[:3]
                            avg = sum(best3) / 3
                            student.assessment_avg = avg
                            student.assessment_total_40 = int(round(avg * 4))
                        elif len(values) > 0:
                            avg = sum(values) / len(values)
                            student.assessment_avg = avg
                            student.assessment_total_40 = int(round(avg * 4))
                        else:
                            student.assessment_avg = None
                            student.assessment_total_40 = None

                    elif session.course_type == 'sessional' and session.category == 'ug':
                        # Handle sessional course assessments
                        report = request.form.get(f'sessional_report_{student.id}')
                        viva = request.form.get(f'sessional_viva_{student.id}')
                        student.sessional_report = float(report) if report else None
                        student.sessional_viva = float(viva) if viva else None
                
                db.session.commit()
                flash('Assessment marks saved successfully!', 'success')
                return redirect(url_for('class_management.assessment', session_id=session_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving assessment: {str(e)}', 'error')
                return redirect(url_for('class_management.assessment', session_id=session_id))
        
        return render_template('class_management/assessment.html', session=session, students=students)
        
    except Exception as e:
        flash(f'Error loading assessment page: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))

@class_management_bp.route('/download_assessment_excel/<int:session_id>')
@login_required
def download_assessment_excel(session_id):
    """Download assessment data as Excel file"""
    try:
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).all()
        
        # Build data for DataFrame
        data = []
        if session.course_type == 'theory' and session.category == 'ug':
            columns = ['Student ID', 'Name', 'Assessment 1', 'Assessment 2', 'Assessment 3', 'Assessment 4', 'Total of Best 3']
            for s in students:
                data.append([
                    s.student_id,
                    s.name,
                    s.assessment1,
                    s.assessment2,
                    s.assessment3,
                    s.assessment4,
                    s.assessment_total
                ])
        elif session.course_type == 'theory' and session.category == 'pg':
            columns = ['Student ID', 'Name', 'Assessment 1', 'Assessment 2', 'Assessment 3', 'Assessment 4', 'Avg of Best 3', 'Total (40)']
            for s in students:
                data.append([
                    s.student_id,
                    s.name,
                    s.assessment1,
                    s.assessment2,
                    s.assessment3,
                    s.assessment4,
                    s.assessment_avg,
                    s.assessment_total_40
                ])
        elif session.course_type == 'sessional' and session.category == 'ug':
            columns = ['Student ID', 'Name', 'Sessional Report (60)', 'Sessional Viva (30)', 'Total (Sessional: 90)']
            for s in students:
                total = (s.sessional_report or 0) + (s.sessional_viva or 0)
                data.append([
                    s.student_id,
                    s.name,
                    s.sessional_report,
                    s.sessional_viva,
                    total
                ])
        else:
            flash('Unsupported course type for assessment export', 'error')
            return redirect(url_for('class_management.assessment', session_id=session_id))
        
        # Create DataFrame and Excel file
        df = pd.DataFrame(data, columns=columns)
        
        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Assessment', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Assessment']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        
        filename = f"assessment_{session.course_name or session.term}_{session.year}_{session.term}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        flash(f'Error downloading assessment Excel: {str(e)}', 'error')
        return redirect(url_for('class_management.assessment', session_id=session_id))

# Template filter for dynamic attribute access
@class_management_bp.app_template_filter('getattr')
def jinja_getattr(obj, name):
    return getattr(obj, name) 