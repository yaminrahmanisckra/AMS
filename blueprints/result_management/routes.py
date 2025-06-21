from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import inch
from io import BytesIO
from .models import db, RSession, RStudent, RSubject, RMark
from openpyxl import load_workbook
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
import zipfile

result_management_bp = Blueprint('result_management', __name__, template_folder='templates/result_management')

def calculate_grade(total_marks, is_retake=False):
    grade_point = 0.0
    grade_letter = 'F'
    if total_marks >= 80: grade_point, grade_letter = 4.0, 'A+'
    elif total_marks >= 75: grade_point, grade_letter = 3.75, 'A'
    elif total_marks >= 70: grade_point, grade_letter = 3.5, 'A-'
    elif total_marks >= 65: grade_point, grade_letter = 3.25, 'B+'
    elif total_marks >= 60: grade_point, grade_letter = 3.0, 'B'
    elif total_marks >= 55: grade_point, grade_letter = 2.75, 'B-'
    elif total_marks >= 50: grade_point, grade_letter = 2.5, 'C+'
    elif total_marks >= 45: grade_point, grade_letter = 2.25, 'C'
    elif total_marks >= 40: grade_point, grade_letter = 2.0, 'D'
    if is_retake and grade_letter != 'F':
        if grade_letter == 'A+': grade_point, grade_letter = 3.75, 'A'
        elif grade_letter == 'A': grade_point, grade_letter = 3.5, 'A-'
        elif grade_letter == 'A-': grade_point, grade_letter = 3.25, 'B+'
        elif grade_letter == 'B+': grade_point, grade_letter = 3.0, 'B'
        elif grade_letter == 'B': grade_point, grade_letter = 2.75, 'B-'
        elif grade_letter == 'B-': grade_point, grade_letter = 2.5, 'C+'
        elif grade_letter == 'C+': grade_point, grade_letter = 2.25, 'C'
        elif grade_letter == 'C': grade_point, grade_letter = 2.0, 'D'
    return grade_point, grade_letter

def convert_to_roman(num):
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syb[i]
            num -= val[i]
        i += 1
    return roman_num

# --- Page Numbering Function ---
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    page_number_text = f"Page {doc.page} of {doc.doc.page_count}"
    canvas.drawRightString(letter[0] - 40, 30, page_number_text)
    canvas.restoreState()

@result_management_bp.route('/')
@login_required
def index():
    sessions = RSession.query.filter_by(is_archived=False).order_by(RSession.created_at.desc()).all()
    return render_template('rm_index.html', sessions=sessions)

@result_management_bp.route('/archived')
@login_required
def archived_sessions():
    sessions = RSession.query.filter_by(is_archived=True).order_by(RSession.created_at.desc()).all()
    return render_template('rm_archive.html', sessions=sessions)

@result_management_bp.route('/archive_session/<int:session_id>', methods=['POST'])
@login_required
def archive_session(session_id):
    session = RSession.query.get_or_404(session_id)
    session.is_archived = True
    db.session.commit()
    flash(f'Session "{session.name}" has been archived.', 'success')
    return redirect(url_for('result_management.index'))

@result_management_bp.route('/unarchive_session/<int:session_id>', methods=['POST'])
@login_required
def unarchive_session(session_id):
    session = RSession.query.get_or_404(session_id)
    session.is_archived = False
    db.session.commit()
    flash(f'Session "{session.name}" has been unarchived.', 'success')
    return redirect(url_for('result_management.archived_sessions'))

@result_management_bp.route('/add_session', methods=['GET', 'POST'])
@login_required
def add_session():
    if request.method == 'POST':
        name = request.form['name']
        term = request.form['term']
        term_roman = convert_to_roman(int(term))
        session = RSession(name=name, term=term_roman)
        db.session.add(session)
        db.session.commit()
        flash('Session added successfully!', 'success')
        return redirect(url_for('result_management.index'))
    return render_template('rm_add_session.html')

@result_management_bp.route('/add_student/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_student(session_id):
    if request.method == 'POST':
        if 'excel_file' in request.files and request.files['excel_file'].filename != '':
            file = request.files['excel_file']
            if file and file.filename.endswith('.xlsx'):
                try:
                    wb = load_workbook(file)
                    ws = wb.active
                    added_count = 0
                    skipped_count = 0

                    # --- Optimization Start ---
                    # 1. Read all student IDs from the Excel file
                    all_student_ids_from_excel = []
                    rows_to_process = []
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        student_data = (list(row) + [None]*5)[:5]
                        student_id = student_data[0]
                        if student_id:
                            all_student_ids_from_excel.append(str(student_id))
                            rows_to_process.append(student_data)

                    # 2. Find which of these students already exist in the DB in a single query
                    existing_students = db.session.query(RStudent.student_id).filter(
                        RStudent.session_id == session_id,
                        RStudent.student_id.in_(all_student_ids_from_excel)
                    ).all()
                    existing_student_ids = {str(s_id[0]) for s_id in existing_students}

                    # 3. Iterate and add only the new students
                    students_to_add = []
                    for student_id, name, year, discipline, school in rows_to_process:
                        if str(student_id) not in existing_student_ids:
                            students_to_add.append(RStudent(
                                student_id=str(student_id), name=name, year=year,
                                discipline=discipline, school=school, session_id=session_id
                            ))
                            added_count += 1
                        else:
                            skipped_count += 1
                    
                    if students_to_add:
                        db.session.bulk_save_objects(students_to_add)
                    # --- Optimization End ---
                    
                    db.session.commit()
                    flash(f'Successfully added {added_count} new students. Skipped {skipped_count} existing students.', 'success')
                except Exception as e:
                    flash(f'Error processing Excel file: {e}', 'danger')
                return redirect(url_for('result_management.add_student', session_id=session_id))
            else:
                flash('Invalid file type. Please upload a .xlsx file.', 'danger')
        else:
            student_id = request.form.get('student_id')
            name = request.form.get('name')
            if student_id and name:
                exists = RStudent.query.filter_by(student_id=student_id, session_id=session_id).first()
                if exists:
                    flash('Student with this ID already exists in this session.', 'danger')
                else:
                    student = RStudent(
                        student_id=student_id, name=name, session_id=session_id
                    )
                    db.session.add(student)
                    db.session.commit()
                    flash('Student added successfully!', 'success')
            else:
                flash('Student ID and Name are required for single add.', 'warning')
        return redirect(url_for('result_management.add_student', session_id=session_id))
    
    students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_add_student.html', session=session, students=students)

@result_management_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = RStudent.query.get_or_404(student_id)
    if request.method == 'POST':
        student.student_id = request.form['student_id']
        student.name = request.form['name']
        student.year = request.form.get('year')
        student.discipline = request.form.get('discipline')
        student.school = request.form.get('school')
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('result_management.add_student', session_id=student.session_id))
    return render_template('rm_edit_student.html', student=student)

@result_management_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = RStudent.query.get_or_404(student_id)
    session_id = student.session_id
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('result_management.add_student', session_id=session_id))

@result_management_bp.route('/add_subject/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_subject(session_id):
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        credit = float(request.form['credit'])
        subject_type = request.form['subject_type']
        dissertation_type = request.form.get('dissertation_type') if subject_type == 'Dissertation' else None
        
        subject = RSubject(
            code=code, name=name, credit=credit, subject_type=subject_type,
            dissertation_type=dissertation_type, session_id=session_id
        )
        db.session.add(subject)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('result_management.add_subject', session_id=session_id))
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_add_subject.html', session=session, subjects=subjects)

@result_management_bp.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = RSubject.query.get_or_404(subject_id)
    session_id = subject.session_id
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('result_management.add_subject', session_id=session_id))

@result_management_bp.route('/add_marks/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_marks(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_subject = RSubject.query.get(selected_subject_id) if selected_subject_id else None

    students = []
    if selected_subject:
        registered_students_query = RStudent.query.join(RMark).filter(RMark.subject_id == selected_subject.id)
        students = registered_students_query.all()

    marks_data = {}
    if selected_subject:
        marks = RMark.query.filter_by(subject_id=selected_subject.id).all()
        for mark in marks:
            marks_data[mark.student_id] = mark

    if request.method == 'POST':
        subject_id = int(request.form.get('subject_id'))
        selected_subject = RSubject.query.get(subject_id)
        
        student_ids_on_page = {int(k.split('_')[1]) for k in request.form if k.startswith('student_')}
        
        for student_id in student_ids_on_page:
            prefix = f'student_{student_id}'
            
            if f'{prefix}_total_marks' in request.form and request.form[f'{prefix}_total_marks']:
                total_marks = float(request.form[f'{prefix}_total_marks'])
                is_retake = f'{prefix}_is_retake' in request.form

                grade_point, grade_letter = calculate_grade(total_marks, is_retake)

                existing_mark = RMark.query.filter_by(student_id=student_id, subject_id=subject_id).first()

                if existing_mark:
                    existing_mark.total_marks = total_marks
                    existing_mark.grade_point = grade_point
                    existing_mark.grade_letter = grade_letter
                    
                    if selected_subject.subject_type == 'Theory':
                        existing_mark.attendance = float(request.form.get(f'{prefix}_attendance') or 0)
                        existing_mark.continuous_assessment = float(request.form.get(f'{prefix}_continuous_assessment') or 0)
                        existing_mark.part_a = float(request.form.get(f'{prefix}_part_a') or 0)
                        existing_mark.part_b = float(request.form.get(f'{prefix}_part_b') or 0)
        
        db.session.commit()
        flash(f'Marks for {selected_subject.name} updated successfully!', 'success')
        return redirect(url_for('result_management.add_marks', session_id=session_id, subject_id=subject_id))

    return render_template('rm_add_marks.html', 
                           session=session, 
                           subjects=subjects, 
                           students=students,
                           selected_subject=selected_subject,
                           marks_data=marks_data)

@result_management_bp.route('/view_results/<int:session_id>')
@login_required
def view_results(session_id):
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_view_results.html', session=session)

@result_management_bp.route('/course_wise_result/<int:session_id>')
@login_required
def course_wise_result(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    selected_subject_id = request.args.get('subject_id', type=int)
    
    results = []
    if selected_subject_id:
        results = db.session.query(RStudent, RMark).join(RMark).filter(
            RStudent.session_id == session_id,
            RMark.subject_id == selected_subject_id
        ).all()
        
    return render_template('rm_course_wise_result.html', 
                           session=session, 
                           subjects=subjects, 
                           results=results, 
                           selected_subject_id=selected_subject_id)

@result_management_bp.route('/student_wise_result/<int:session_id>')
@login_required
def student_wise_result(session_id):
    session = RSession.query.get_or_404(session_id)
    students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()
    selected_student_id = request.args.get('student_id', type=int)
    
    results = []
    term_assessment = {
        'total_registered_credits': 0.0,
        'total_earned_credits': 0.0,
        'total_earned_credit_points': 0.0,
        'tgpa': 0.0
    }
    selected_student = None

    if selected_student_id:
        selected_student = RStudent.query.get(selected_student_id)
        marks = RMark.query.filter_by(student_id=selected_student_id).join(RSubject).order_by(RSubject.code).all()
        
        processed_results = []
        total_points_for_tgpa = 0.0

        for mark in marks:
            registered_credits = mark.subject.credit if mark.subject.credit is not None else 0.0
            grade_point = mark.grade_point if mark.grade_point is not None else 0.0
            earned_credits = registered_credits if grade_point > 0 else 0.0
            earned_credit_points = grade_point * earned_credits
            remarks = 'Retake' if mark.is_retake else ''

            processed_results.append({
                'subject_code': mark.subject.code, 'subject_name': mark.subject.name,
                'registered_credits': registered_credits, 'grade_letter': mark.grade_letter,
                'grade_point': grade_point, 'earned_credits': earned_credits,
                'earned_credit_points': earned_credit_points, 'remarks': remarks
            })
            term_assessment['total_registered_credits'] += registered_credits
            term_assessment['total_earned_credits'] += earned_credits
            term_assessment['total_earned_credit_points'] += earned_credit_points
            total_points_for_tgpa += grade_point * registered_credits

        if term_assessment['total_registered_credits'] > 0:
            term_assessment['tgpa'] = total_points_for_tgpa / term_assessment['total_registered_credits']
        results = processed_results

    return render_template('rm_student_wise_result.html',
                           session=session, students=students, results=results,
                           selected_student_id=selected_student_id, selected_student=selected_student,
                           term_assessment=term_assessment)

@result_management_bp.route('/course_registration/<int:session_id>', methods=['GET', 'POST'])
@login_required
def course_registration(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    students = RStudent.query.filter_by(session_id=session_id).all()
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_subject = RSubject.query.get(selected_subject_id) if selected_subject_id else None

    registrations = {}
    if selected_subject:
        existing_regs = RMark.query.filter_by(subject_id=selected_subject.id).all()
        for reg in existing_regs:
            registrations[reg.student_id] = reg

    if request.method == 'POST':
        subject_id = int(request.form.get('subject_id'))
        student_ids_in_form = {int(k.split('_')[1]) for k in request.form if k.startswith('reg_')}
        for student in students:
            is_registered = student.id in student_ids_in_form
            is_retake = f'retake_{student.id}' in request.form
            existing_reg = RMark.query.filter_by(student_id=student.id, subject_id=subject_id).first()
            if is_registered:
                if not existing_reg:
                    new_mark = RMark(student_id=student.id, subject_id=subject_id, is_retake=is_retake)
                    db.session.add(new_mark)
                elif existing_reg.is_retake != is_retake:
                    existing_reg.is_retake = is_retake
            elif not is_registered and existing_reg:
                db.session.delete(existing_reg)
        db.session.commit()
        selected_subject = RSubject.query.get(subject_id)
        flash(f'Course registration for {selected_subject.name} updated successfully!', 'success')
        return redirect(url_for('result_management.course_registration', session_id=session_id, subject_id=subject_id))

    return render_template('rm_course_registration.html',
                           session=session, subjects=subjects, students=students,
                           selected_subject=selected_subject, registrations=registrations)

@result_management_bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = RSession.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Session and all related data deleted successfully!', 'success')
    return redirect(url_for('result_management.index'))

class PDFGenerator:
    def __init__(self, buffer, pagesize):
        self.buffer = buffer
        self.pagesize = pagesize
        self.styles = getSampleStyleSheet()
        self.page_count = 0

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_number_text = f"Page {doc.page} of {self.page_count}"
        canvas.drawRightString(doc.width + doc.leftMargin - 20, 30, page_number_text)
        canvas.restoreState()

    def build(self, elements):
        dummy_buffer = io.BytesIO()
        doc_for_count = SimpleDocTemplate(dummy_buffer, pagesize=self.pagesize, topMargin=30, bottomMargin=50, leftMargin=30, rightMargin=30)
        doc_for_count.build(elements[:])
        self.page_count = doc_for_count.page

        doc = SimpleDocTemplate(self.buffer, pagesize=self.pagesize, topMargin=30, bottomMargin=50, leftMargin=30, rightMargin=30)
        doc.build(elements, onFirstPage=self._footer, onLaterPages=self._footer)

class CourseTabulationPDF(PDFGenerator):
    def __init__(self, buffer, subject, session):
        super().__init__(buffer, pagesize=letter)
        self.subject = subject
        self.session = session

    def generate_elements(self, results):
        elements = []
        p_style_title = ParagraphStyle(name='Title', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold')
        elements.append(Paragraph("Khulna University", p_style_title))
        p_style_subtitle = ParagraphStyle(name='Subtitle', fontSize=12, alignment=TA_CENTER, fontName='Helvetica', spaceAfter=15)
        elements.append(Paragraph("Course-wise Tabulation Sheet", p_style_subtitle))

        info_style = self.styles['Normal']
        info_style.fontSize = 10
        year = "LL.M"
        discipline = "Law"
        school = "Law"

        info_data = [
            [Paragraph(f"<b>Year:</b> {year}", info_style), Paragraph(f"<b>Term:</b> {self.session.term}", info_style), Paragraph(f"<b>Session:</b> {self.session.name}", info_style)],
            [Paragraph(f"<b>Discipline:</b> {discipline}", info_style), Paragraph(f"<b>School:</b> {school}", info_style), ""],
            [Paragraph(f"<b>Course No.:</b> {self.subject.code}", info_style), Paragraph(f"<b>CH:</b> {self.subject.credit}", info_style), ""],
            [Paragraph(f"<b>Course Title:</b> {self.subject.name}", info_style), "", ""]
        ]
        info_table = Table(info_data, colWidths=['33%', '33%', '33%'])
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('SPAN', (0, 3), (-1, 3))]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        headers = ['Student\nNo.', 'Attendance\n(10)', 'Continuous\nAssessment\n(40)', 'Section A\n(25)', 'Section B\n(25)', 'Total\nMarks\n(100)', 'Grade\nPoint', 'Grade\nLetter', 'Remarks']
        table_data = [headers]
        for r in results:
            table_data.append([
                r.RStudent.student_id, r.RMark.attendance or '0.0', r.RMark.continuous_assessment or '0.0',
                r.RMark.part_a or '0.0', r.RMark.part_b or '0.0', r.RMark.total_marks or '0.0',
                f"{r.RMark.grade_point:.2f}" if r.RMark.grade_point is not None else '0.00',
                r.RMark.grade_letter or 'F',
                'Retake' if r.RMark.is_retake else ''
            ])
        col_widths = [60, 46, 60, 46, 46, 46, 38, 38, 60]
        results_table = Table(table_data, colWidths=col_widths)
        results_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(results_table)

        elements.append(Spacer(1, 40))
        sig_style = ParagraphStyle(name='Signature', fontSize=10, fontName='Helvetica', alignment=TA_CENTER, leading=18)
        sig_data = [[
            Paragraph('Signature of the First Tabulator<br/><br/>Date:', sig_style),
            Paragraph('Signature of the Second Tabulator<br/><br/>Date:', sig_style),
            Paragraph('Signature of the Chairman,<br/>Examination Committee<br/><br/>Date:', sig_style)
        ]]
        sig_table = Table(sig_data, colWidths=['33%', '33%', '33%'])
        sig_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(sig_table)
        return elements

class StudentTabulationPDF(PDFGenerator):
    def __init__(self, buffer, student, session):
        super().__init__(buffer, pagesize=letter)
        self.student = student
        self.session = session

    def generate_elements(self, results, term_assessment):
        elements = []
        p_style = ParagraphStyle(name='Title', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold')
        elements.append(Paragraph("Khulna University", p_style))
        p_style.fontSize = 12
        p_style.fontName = 'Helvetica'
        elements.append(Paragraph("Student-wise Tabulation Sheet", p_style))
        elements.append(Spacer(1,15))

        info_style = self.styles['Normal']
        info_style.fontSize = 10
        
        # Set static values as requested
        year = "LL.M"
        discipline = "Law"
        school = "Law"

        info_data = [
            [Paragraph(f"<b>Year:</b> {year}", info_style), Paragraph(f"<b>Term:</b> {self.session.term}", info_style)],
            [Paragraph(f"<b>Student No.:</b> {self.student.student_id}", info_style), Paragraph(f"<b>Name of Student:</b> {self.student.name}", info_style)],
            [Paragraph(f"<b>Discipline:</b> {discipline}", info_style), Paragraph(f"<b>Session:</b> {self.session.name}", info_style)],
            ["", Paragraph(f"<b>School:</b> {school}", info_style)]
        ]
        info_table = Table(info_data, colWidths=['50%', '50%'], hAlign='LEFT')
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        headers = ['Course No.', 'Course Title', 'Registered\nCredit\nHours', 'Letter\nGrade', 'Grade\nPoint\n(GP)', 'Earned\nCredit\nHours (CH)', 'Earned\nCredit\nPoints\n(GP*CH)', 'Remarks']
        table_data = [headers]
        for r in results:
            table_data.append([
                r['subject_code'], r['subject_name'], r['registered_credits'],
                r['grade_letter'] or '', f"{r['grade_point']:.2f}", r['earned_credits'],
                f"{r['earned_credit_points']:.2f}", r['remarks']
            ])
        col_widths = [80, 150, 55, 45, 45, 55, 55, 70]
        results_table = Table(table_data, colWidths=col_widths)
        results_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ]))
        elements.append(results_table)
        elements.append(Spacer(1, 15))

        assessment_style = self.styles['Normal']
        assessment_style.fontSize = 9
        assessment_text = f"""
            <b>Term Assessment</b><br/>
            Total Earned Credit Hours in this Term (TCH) = {term_assessment['total_earned_credits']}<br/>
            Total Registered Credit Hours in this Term (RCH) = {term_assessment['total_registered_credits']}<br/>
            Total Earned Credit Points in this Term (TCP) = {term_assessment['total_earned_credit_points']:.2f}<br/>
            TGPA = TCP/RCH = {term_assessment['tgpa']:.2f}
        """
        elements.append(Paragraph(assessment_text, assessment_style))
        elements.append(Spacer(1, 30))

        sig_style = self.styles['Normal']
        sig_style.fontSize = 9
        sig_data = [[
            Paragraph("<u>Signature of the First Tabulator</u><br/>Date:", sig_style),
            Paragraph("<u>Signature of the Second Tabulator</u><br/>Date:", sig_style),
            Paragraph("<u>Signature of the Chairman, Examination Committee</u><br/>Date:", sig_style)
        ]]
        sig_table = Table(sig_data, colWidths=['33%', '33%', '33%'])
        elements.append(sig_table)
        return elements

@result_management_bp.route('/download/course_result/<int:session_id>/<int:subject_id>')
@login_required
def download_course_result(session_id, subject_id):
    session = RSession.query.get_or_404(session_id)
    subject = RSubject.query.get_or_404(subject_id)
    results = db.session.query(RStudent, RMark).join(RMark).filter(
        RStudent.session_id == session_id,
        RMark.subject_id == subject_id
    ).order_by(RStudent.student_id).all()

    buffer = io.BytesIO()
    pdf = CourseTabulationPDF(buffer, subject, session)
    elements = pdf.generate_elements(results)
    pdf.build(elements)
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'course_result_{subject.code}.pdf', mimetype='application/pdf')

@result_management_bp.route('/download/student_result/<int:session_id>/<int:student_id>')
@login_required
def download_student_result(student_id, session_id):
    student = RStudent.query.get_or_404(student_id)
    session = RSession.query.get_or_404(session_id)
    
    marks = RMark.query.filter_by(student_id=student_id).join(RSubject).order_by(RSubject.code).all()
    
    processed_results = []
    term_assessment = {
        'total_registered_credits': 0.0, 'total_earned_credits': 0.0,
        'total_earned_credit_points': 0.0, 'tgpa': 0.0
    }
    total_points_for_tgpa = 0.0

    for mark in marks:
        registered_credits = mark.subject.credit or 0.0
        grade_point = mark.grade_point or 0.0
        earned_credits = registered_credits if grade_point > 0 else 0.0
        earned_credit_points = grade_point * earned_credits
        remarks = 'Retake' if mark.is_retake else ''
        processed_results.append({
            'subject_code': mark.subject.code, 'subject_name': mark.subject.name,
            'registered_credits': registered_credits, 'grade_letter': mark.grade_letter,
            'grade_point': grade_point, 'earned_credits': earned_credits,
            'earned_credit_points': earned_credit_points, 'remarks': remarks
        })
        term_assessment['total_registered_credits'] += registered_credits
        term_assessment['total_earned_credits'] += earned_credits
        term_assessment['total_earned_credit_points'] += earned_credit_points
        total_points_for_tgpa += grade_point * registered_credits

    if term_assessment['total_registered_credits'] > 0:
        term_assessment['tgpa'] = total_points_for_tgpa / term_assessment['total_registered_credits']

    buffer = io.BytesIO()
    pdf = StudentTabulationPDF(buffer, student, session)
    elements = pdf.generate_elements(processed_results, term_assessment)
    pdf.build(elements)

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'student_result_{student.student_id}.pdf', mimetype='application/pdf')

@result_management_bp.route('/download/all_student_results/<int:session_id>')
@login_required
def download_all_student_results(session_id):
    session = RSession.query.get_or_404(session_id)
    students = RStudent.query.filter_by(session_id=session_id).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, False) as zip_file:
        for student in students:
            # Re-use logic from single student download
            marks = RMark.query.filter_by(student_id=student.id).join(RSubject).order_by(RSubject.code).all()
            processed_results = []
            term_assessment = {'total_registered_credits': 0.0, 'total_earned_credits': 0.0, 'total_earned_credit_points': 0.0, 'tgpa': 0.0}
            total_points_for_tgpa = 0.0
            for mark in marks:
                registered_credits = mark.subject.credit or 0.0
                grade_point = mark.grade_point or 0.0
                earned_credits = registered_credits if grade_point > 0 else 0.0
                earned_credit_points = grade_point * earned_credits
                remarks = 'Retake' if mark.is_retake else ''
                processed_results.append({'subject_code': mark.subject.code, 'subject_name': mark.subject.name, 'registered_credits': registered_credits, 'grade_letter': mark.grade_letter, 'grade_point': grade_point, 'earned_credits': earned_credits, 'earned_credit_points': earned_credit_points, 'remarks': remarks})
                term_assessment['total_registered_credits'] += registered_credits
                term_assessment['total_earned_credits'] += earned_credits
                term_assessment['total_earned_credit_points'] += earned_credit_points
                total_points_for_tgpa += grade_point * registered_credits
            if term_assessment['total_registered_credits'] > 0:
                term_assessment['tgpa'] = total_points_for_tgpa / term_assessment['total_registered_credits']

            # Generate PDF in memory
            pdf_buffer = io.BytesIO()
            pdf = StudentTabulationPDF(pdf_buffer, student, session)
            elements = pdf.generate_elements(processed_results, term_assessment)
            pdf.build(elements)
            pdf_buffer.seek(0)
            
            # Add PDF to zip
            zip_file.writestr(f'student_result_{student.student_id}.pdf', pdf_buffer.getvalue())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'student_results_{session.name}.zip', mimetype='application/zip')

@result_management_bp.route('/download/all_course_results/<int:session_id>')
@login_required
def download_all_course_results(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, False) as zip_file:
        for subject in subjects:
            results = db.session.query(RStudent, RMark).join(RMark).filter(RStudent.session_id == session_id, RMark.subject_id == subject.id).order_by(RStudent.student_id).all()
            if not results:
                continue

            # Generate PDF in memory
            pdf_buffer = io.BytesIO()
            pdf = CourseTabulationPDF(pdf_buffer, subject, session)
            elements = pdf.generate_elements(results)
            pdf.build(elements)
            pdf_buffer.seek(0)
            
            # Add PDF to zip
            zip_file.writestr(f'course_result_{subject.code}.pdf', pdf_buffer.getvalue())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'course_results_{session.name}.zip', mimetype='application/zip')

from flask_login import login_required, current_user
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.units import inch
from io import BytesIO
from .models import db, RSession, RStudent, RSubject, RMark
from openpyxl import load_workbook
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
import zipfile

result_management_bp = Blueprint('result_management', __name__, template_folder='templates/result_management')

def calculate_grade(total_marks, is_retake=False):
    grade_point = 0.0
    grade_letter = 'F'
    if total_marks >= 80: grade_point, grade_letter = 4.0, 'A+'
    elif total_marks >= 75: grade_point, grade_letter = 3.75, 'A'
    elif total_marks >= 70: grade_point, grade_letter = 3.5, 'A-'
    elif total_marks >= 65: grade_point, grade_letter = 3.25, 'B+'
    elif total_marks >= 60: grade_point, grade_letter = 3.0, 'B'
    elif total_marks >= 55: grade_point, grade_letter = 2.75, 'B-'
    elif total_marks >= 50: grade_point, grade_letter = 2.5, 'C+'
    elif total_marks >= 45: grade_point, grade_letter = 2.25, 'C'
    elif total_marks >= 40: grade_point, grade_letter = 2.0, 'D'
    if is_retake and grade_letter != 'F':
        if grade_letter == 'A+': grade_point, grade_letter = 3.75, 'A'
        elif grade_letter == 'A': grade_point, grade_letter = 3.5, 'A-'
        elif grade_letter == 'A-': grade_point, grade_letter = 3.25, 'B+'
        elif grade_letter == 'B+': grade_point, grade_letter = 3.0, 'B'
        elif grade_letter == 'B': grade_point, grade_letter = 2.75, 'B-'
        elif grade_letter == 'B-': grade_point, grade_letter = 2.5, 'C+'
        elif grade_letter == 'C+': grade_point, grade_letter = 2.25, 'C'
        elif grade_letter == 'C': grade_point, grade_letter = 2.0, 'D'
    return grade_point, grade_letter

def convert_to_roman(num):
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syb = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_num = ''
    i = 0
    while num > 0:
        for _ in range(num // val[i]):
            roman_num += syb[i]
            num -= val[i]
        i += 1
    return roman_num

# --- Page Numbering Function ---
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    page_number_text = f"Page {doc.page} of {doc.doc.page_count}"
    canvas.drawRightString(letter[0] - 40, 30, page_number_text)
    canvas.restoreState()

@result_management_bp.route('/')
@login_required
def index():
    sessions = RSession.query.filter_by(is_archived=False).order_by(RSession.created_at.desc()).all()
    return render_template('rm_index.html', sessions=sessions)

@result_management_bp.route('/archived')
@login_required
def archived_sessions():
    sessions = RSession.query.filter_by(is_archived=True).order_by(RSession.created_at.desc()).all()
    return render_template('rm_archive.html', sessions=sessions)

@result_management_bp.route('/archive_session/<int:session_id>', methods=['POST'])
@login_required
def archive_session(session_id):
    session = RSession.query.get_or_404(session_id)
    session.is_archived = True
    db.session.commit()
    flash(f'Session "{session.name}" has been archived.', 'success')
    return redirect(url_for('result_management.index'))

@result_management_bp.route('/unarchive_session/<int:session_id>', methods=['POST'])
@login_required
def unarchive_session(session_id):
    session = RSession.query.get_or_404(session_id)
    session.is_archived = False
    db.session.commit()
    flash(f'Session "{session.name}" has been unarchived.', 'success')
    return redirect(url_for('result_management.archived_sessions'))

@result_management_bp.route('/add_session', methods=['GET', 'POST'])
@login_required
def add_session():
    if request.method == 'POST':
        name = request.form['name']
        term = request.form['term']
        term_roman = convert_to_roman(int(term))
        session = RSession(name=name, term=term_roman)
        db.session.add(session)
        db.session.commit()
        flash('Session added successfully!', 'success')
        return redirect(url_for('result_management.index'))
    return render_template('rm_add_session.html')

@result_management_bp.route('/add_student/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_student(session_id):
    if request.method == 'POST':
        if 'excel_file' in request.files and request.files['excel_file'].filename != '':
            file = request.files['excel_file']
            if file and file.filename.endswith('.xlsx'):
                try:
                    wb = load_workbook(file)
                    ws = wb.active
                    added_count = 0
                    skipped_count = 0

                    # --- Optimization Start ---
                    # 1. Read all student IDs from the Excel file
                    all_student_ids_from_excel = []
                    rows_to_process = []
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        student_data = (list(row) + [None]*5)[:5]
                        student_id = student_data[0]
                        if student_id:
                            all_student_ids_from_excel.append(str(student_id))
                            rows_to_process.append(student_data)

                    # 2. Find which of these students already exist in the DB in a single query
                    existing_students = db.session.query(RStudent.student_id).filter(
                        RStudent.session_id == session_id,
                        RStudent.student_id.in_(all_student_ids_from_excel)
                    ).all()
                    existing_student_ids = {str(s_id[0]) for s_id in existing_students}

                    # 3. Iterate and add only the new students
                    students_to_add = []
                    for student_id, name, year, discipline, school in rows_to_process:
                        if str(student_id) not in existing_student_ids:
                            students_to_add.append(RStudent(
                                student_id=str(student_id), name=name, year=year,
                                discipline=discipline, school=school, session_id=session_id
                            ))
                            added_count += 1
                        else:
                            skipped_count += 1
                    
                    if students_to_add:
                        db.session.bulk_save_objects(students_to_add)
                    # --- Optimization End ---
                    
                    db.session.commit()
                    flash(f'Successfully added {added_count} new students. Skipped {skipped_count} existing students.', 'success')
                except Exception as e:
                    flash(f'Error processing Excel file: {e}', 'danger')
                return redirect(url_for('result_management.add_student', session_id=session_id))
            else:
                flash('Invalid file type. Please upload a .xlsx file.', 'danger')
        else:
            student_id = request.form.get('student_id')
            name = request.form.get('name')
            if student_id and name:
                exists = RStudent.query.filter_by(student_id=student_id, session_id=session_id).first()
                if exists:
                    flash('Student with this ID already exists in this session.', 'danger')
                else:
                    student = RStudent(
                        student_id=student_id, name=name, session_id=session_id
                    )
                    db.session.add(student)
                    db.session.commit()
                    flash('Student added successfully!', 'success')
            else:
                flash('Student ID and Name are required for single add.', 'warning')
        return redirect(url_for('result_management.add_student', session_id=session_id))
    
    students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_add_student.html', session=session, students=students)

@result_management_bp.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    student = RStudent.query.get_or_404(student_id)
    if request.method == 'POST':
        student.student_id = request.form['student_id']
        student.name = request.form['name']
        student.year = request.form.get('year')
        student.discipline = request.form.get('discipline')
        student.school = request.form.get('school')
        db.session.commit()
        flash('Student updated successfully!', 'success')
        return redirect(url_for('result_management.add_student', session_id=student.session_id))
    return render_template('rm_edit_student.html', student=student)

@result_management_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    student = RStudent.query.get_or_404(student_id)
    session_id = student.session_id
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('result_management.add_student', session_id=session_id))

@result_management_bp.route('/add_subject/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_subject(session_id):
    if request.method == 'POST':
        code = request.form['code']
        name = request.form['name']
        credit = float(request.form['credit'])
        subject_type = request.form['subject_type']
        dissertation_type = request.form.get('dissertation_type') if subject_type == 'Dissertation' else None
        
        subject = RSubject(
            code=code, name=name, credit=credit, subject_type=subject_type,
            dissertation_type=dissertation_type, session_id=session_id
        )
        db.session.add(subject)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('result_management.add_subject', session_id=session_id))
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_add_subject.html', session=session, subjects=subjects)

@result_management_bp.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = RSubject.query.get_or_404(subject_id)
    session_id = subject.session_id
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('result_management.add_subject', session_id=session_id))

@result_management_bp.route('/add_marks/<int:session_id>', methods=['GET', 'POST'])
@login_required
def add_marks(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_subject = RSubject.query.get(selected_subject_id) if selected_subject_id else None

    students = []
    if selected_subject:
        registered_students_query = RStudent.query.join(RMark).filter(RMark.subject_id == selected_subject.id)
        students = registered_students_query.all()

    marks_data = {}
    if selected_subject:
        marks = RMark.query.filter_by(subject_id=selected_subject.id).all()
        for mark in marks:
            marks_data[mark.student_id] = mark

    if request.method == 'POST':
        subject_id = int(request.form.get('subject_id'))
        selected_subject = RSubject.query.get(subject_id)
        
        student_ids_on_page = {int(k.split('_')[1]) for k in request.form if k.startswith('student_')}
        
        for student_id in student_ids_on_page:
            prefix = f'student_{student_id}'
            
            if f'{prefix}_total_marks' in request.form and request.form[f'{prefix}_total_marks']:
                total_marks = float(request.form[f'{prefix}_total_marks'])
                is_retake = f'{prefix}_is_retake' in request.form

                grade_point, grade_letter = calculate_grade(total_marks, is_retake)

                existing_mark = RMark.query.filter_by(student_id=student_id, subject_id=subject_id).first()

                if existing_mark:
                    existing_mark.total_marks = total_marks
                    existing_mark.grade_point = grade_point
                    existing_mark.grade_letter = grade_letter
                    
                    if selected_subject.subject_type == 'Theory':
                        existing_mark.attendance = float(request.form.get(f'{prefix}_attendance') or 0)
                        existing_mark.continuous_assessment = float(request.form.get(f'{prefix}_continuous_assessment') or 0)
                        existing_mark.part_a = float(request.form.get(f'{prefix}_part_a') or 0)
                        existing_mark.part_b = float(request.form.get(f'{prefix}_part_b') or 0)
        
        db.session.commit()
        flash(f'Marks for {selected_subject.name} updated successfully!', 'success')
        return redirect(url_for('result_management.add_marks', session_id=session_id, subject_id=subject_id))

    return render_template('rm_add_marks.html', 
                           session=session, 
                           subjects=subjects, 
                           students=students,
                           selected_subject=selected_subject,
                           marks_data=marks_data)

@result_management_bp.route('/view_results/<int:session_id>')
@login_required
def view_results(session_id):
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_view_results.html', session=session)

@result_management_bp.route('/course_wise_result/<int:session_id>')
@login_required
def course_wise_result(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    selected_subject_id = request.args.get('subject_id', type=int)
    
    results = []
    if selected_subject_id:
        results = db.session.query(RStudent, RMark).join(RMark).filter(
            RStudent.session_id == session_id,
            RMark.subject_id == selected_subject_id
        ).all()
        
    return render_template('rm_course_wise_result.html', 
                           session=session, 
                           subjects=subjects, 
                           results=results, 
                           selected_subject_id=selected_subject_id)

@result_management_bp.route('/student_wise_result/<int:session_id>')
@login_required
def student_wise_result(session_id):
    session = RSession.query.get_or_404(session_id)
    students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()
    selected_student_id = request.args.get('student_id', type=int)
    
    results = []
    term_assessment = {
        'total_registered_credits': 0.0,
        'total_earned_credits': 0.0,
        'total_earned_credit_points': 0.0,
        'tgpa': 0.0
    }
    selected_student = None

    if selected_student_id:
        selected_student = RStudent.query.get(selected_student_id)
        marks = RMark.query.filter_by(student_id=selected_student_id).join(RSubject).order_by(RSubject.code).all()
        
        processed_results = []
        total_points_for_tgpa = 0.0

        for mark in marks:
            registered_credits = mark.subject.credit if mark.subject.credit is not None else 0.0
            grade_point = mark.grade_point if mark.grade_point is not None else 0.0
            earned_credits = registered_credits if grade_point > 0 else 0.0
            earned_credit_points = grade_point * earned_credits
            remarks = 'Retake' if mark.is_retake else ''

            processed_results.append({
                'subject_code': mark.subject.code, 'subject_name': mark.subject.name,
                'registered_credits': registered_credits, 'grade_letter': mark.grade_letter,
                'grade_point': grade_point, 'earned_credits': earned_credits,
                'earned_credit_points': earned_credit_points, 'remarks': remarks
            })
            term_assessment['total_registered_credits'] += registered_credits
            term_assessment['total_earned_credits'] += earned_credits
            term_assessment['total_earned_credit_points'] += earned_credit_points
            total_points_for_tgpa += grade_point * registered_credits

        if term_assessment['total_registered_credits'] > 0:
            term_assessment['tgpa'] = total_points_for_tgpa / term_assessment['total_registered_credits']
        results = processed_results

    return render_template('rm_student_wise_result.html',
                           session=session, students=students, results=results,
                           selected_student_id=selected_student_id, selected_student=selected_student,
                           term_assessment=term_assessment)

@result_management_bp.route('/course_registration/<int:session_id>', methods=['GET', 'POST'])
@login_required
def course_registration(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()
    students = RStudent.query.filter_by(session_id=session_id).all()
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_subject = RSubject.query.get(selected_subject_id) if selected_subject_id else None

    registrations = {}
    if selected_subject:
        existing_regs = RMark.query.filter_by(subject_id=selected_subject.id).all()
        for reg in existing_regs:
            registrations[reg.student_id] = reg

    if request.method == 'POST':
        subject_id = int(request.form.get('subject_id'))
        student_ids_in_form = {int(k.split('_')[1]) for k in request.form if k.startswith('reg_')}
        for student in students:
            is_registered = student.id in student_ids_in_form
            is_retake = f'retake_{student.id}' in request.form
            existing_reg = RMark.query.filter_by(student_id=student.id, subject_id=subject_id).first()
            if is_registered:
                if not existing_reg:
                    new_mark = RMark(student_id=student.id, subject_id=subject_id, is_retake=is_retake)
                    db.session.add(new_mark)
                elif existing_reg.is_retake != is_retake:
                    existing_reg.is_retake = is_retake
            elif not is_registered and existing_reg:
                db.session.delete(existing_reg)
        db.session.commit()
        selected_subject = RSubject.query.get(subject_id)
        flash(f'Course registration for {selected_subject.name} updated successfully!', 'success')
        return redirect(url_for('result_management.course_registration', session_id=session_id, subject_id=subject_id))

    return render_template('rm_course_registration.html',
                           session=session, subjects=subjects, students=students,
                           selected_subject=selected_subject, registrations=registrations)

@result_management_bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = RSession.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Session and all related data deleted successfully!', 'success')
    return redirect(url_for('result_management.index'))

class PDFGenerator:
    def __init__(self, buffer, pagesize):
        self.buffer = buffer
        self.pagesize = pagesize
        self.styles = getSampleStyleSheet()
        self.page_count = 0

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_number_text = f"Page {doc.page} of {self.page_count}"
        canvas.drawRightString(doc.width + doc.leftMargin - 20, 30, page_number_text)
        canvas.restoreState()

    def build(self, elements):
        dummy_buffer = io.BytesIO()
        doc_for_count = SimpleDocTemplate(dummy_buffer, pagesize=self.pagesize, topMargin=30, bottomMargin=50, leftMargin=30, rightMargin=30)
        doc_for_count.build(elements[:])
        self.page_count = doc_for_count.page

        doc = SimpleDocTemplate(self.buffer, pagesize=self.pagesize, topMargin=30, bottomMargin=50, leftMargin=30, rightMargin=30)
        doc.build(elements, onFirstPage=self._footer, onLaterPages=self._footer)

class CourseTabulationPDF(PDFGenerator):
    def __init__(self, buffer, subject, session):
        super().__init__(buffer, pagesize=letter)
        self.subject = subject
        self.session = session

    def generate_elements(self, results):
        elements = []
        p_style_title = ParagraphStyle(name='Title', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold')
        elements.append(Paragraph("Khulna University", p_style_title))
        p_style_subtitle = ParagraphStyle(name='Subtitle', fontSize=12, alignment=TA_CENTER, fontName='Helvetica', spaceAfter=15)
        elements.append(Paragraph("Course-wise Tabulation Sheet", p_style_subtitle))

        info_style = self.styles['Normal']
        info_style.fontSize = 10
        year = "LL.M"
        discipline = "Law"
        school = "Law"

        info_data = [
            [Paragraph(f"<b>Year:</b> {year}", info_style), Paragraph(f"<b>Term:</b> {self.session.term}", info_style), Paragraph(f"<b>Session:</b> {self.session.name}", info_style)],
            [Paragraph(f"<b>Discipline:</b> {discipline}", info_style), Paragraph(f"<b>School:</b> {school}", info_style), ""],
            [Paragraph(f"<b>Course No.:</b> {self.subject.code}", info_style), Paragraph(f"<b>CH:</b> {self.subject.credit}", info_style), ""],
            [Paragraph(f"<b>Course Title:</b> {self.subject.name}", info_style), "", ""]
        ]
        info_table = Table(info_data, colWidths=['33%', '33%', '33%'])
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('SPAN', (0, 3), (-1, 3))]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        headers = ['Student\nNo.', 'Attendance\n(10)', 'Continuous\nAssessment\n(40)', 'Section A\n(25)', 'Section B\n(25)', 'Total\nMarks\n(100)', 'Grade\nPoint', 'Grade\nLetter', 'Remarks']
        table_data = [headers]
        for r in results:
            table_data.append([
                r.RStudent.student_id, r.RMark.attendance or '0.0', r.RMark.continuous_assessment or '0.0',
                r.RMark.part_a or '0.0', r.RMark.part_b or '0.0', r.RMark.total_marks or '0.0',
                f"{r.RMark.grade_point:.2f}" if r.RMark.grade_point is not None else '0.00',
                r.RMark.grade_letter or 'F',
                'Retake' if r.RMark.is_retake else ''
            ])
        col_widths = [60, 46, 60, 46, 46, 46, 38, 38, 60]
        results_table = Table(table_data, colWidths=col_widths)
        results_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ]))
        elements.append(results_table)

        elements.append(Spacer(1, 40))
        sig_style = ParagraphStyle(name='Signature', fontSize=10, fontName='Helvetica', alignment=TA_CENTER, leading=18)
        sig_data = [[
            Paragraph('Signature of the First Tabulator<br/><br/>Date:', sig_style),
            Paragraph('Signature of the Second Tabulator<br/><br/>Date:', sig_style),
            Paragraph('Signature of the Chairman,<br/>Examination Committee<br/><br/>Date:', sig_style)
        ]]
        sig_table = Table(sig_data, colWidths=['33%', '33%', '33%'])
        sig_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        elements.append(sig_table)
        return elements

class StudentTabulationPDF(PDFGenerator):
    def __init__(self, buffer, student, session):
        super().__init__(buffer, pagesize=letter)
        self.student = student
        self.session = session

    def generate_elements(self, results, term_assessment):
        elements = []
        p_style = ParagraphStyle(name='Title', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold')
        elements.append(Paragraph("Khulna University", p_style))
        p_style.fontSize = 12
        p_style.fontName = 'Helvetica'
        elements.append(Paragraph("Student-wise Tabulation Sheet", p_style))
        elements.append(Spacer(1,15))

        info_style = self.styles['Normal']
        info_style.fontSize = 10
        
        # Set static values as requested
        year = "LL.M"
        discipline = "Law"
        school = "Law"

        info_data = [
            [Paragraph(f"<b>Year:</b> {year}", info_style), Paragraph(f"<b>Term:</b> {self.session.term}", info_style)],
            [Paragraph(f"<b>Student No.:</b> {self.student.student_id}", info_style), Paragraph(f"<b>Name of Student:</b> {self.student.name}", info_style)],
            [Paragraph(f"<b>Discipline:</b> {discipline}", info_style), Paragraph(f"<b>Session:</b> {self.session.name}", info_style)],
            ["", Paragraph(f"<b>School:</b> {school}", info_style)]
        ]
        info_table = Table(info_data, colWidths=['50%', '50%'], hAlign='LEFT')
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))

        headers = ['Course No.', 'Course Title', 'Registered\nCredit\nHours', 'Letter\nGrade', 'Grade\nPoint\n(GP)', 'Earned\nCredit\nHours (CH)', 'Earned\nCredit\nPoints\n(GP*CH)', 'Remarks']
        table_data = [headers]
        for r in results:
            table_data.append([
                r['subject_code'], r['subject_name'], r['registered_credits'],
                r['grade_letter'] or '', f"{r['grade_point']:.2f}", r['earned_credits'],
                f"{r['earned_credit_points']:.2f}", r['remarks']
            ])
        col_widths = [80, 150, 55, 45, 45, 55, 55, 70]
        results_table = Table(table_data, colWidths=col_widths)
        results_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black), ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'), ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ]))
        elements.append(results_table)
        elements.append(Spacer(1, 15))

        assessment_style = self.styles['Normal']
        assessment_style.fontSize = 9
        assessment_text = f"""
            <b>Term Assessment</b><br/>
            Total Earned Credit Hours in this Term (TCH) = {term_assessment['total_earned_credits']}<br/>
            Total Registered Credit Hours in this Term (RCH) = {term_assessment['total_registered_credits']}<br/>
            Total Earned Credit Points in this Term (TCP) = {term_assessment['total_earned_credit_points']:.2f}<br/>
            TGPA = TCP/RCH = {term_assessment['tgpa']:.2f}
        """
        elements.append(Paragraph(assessment_text, assessment_style))
        elements.append(Spacer(1, 30))

        sig_style = self.styles['Normal']
        sig_style.fontSize = 9
        sig_data = [[
            Paragraph("<u>Signature of the First Tabulator</u><br/>Date:", sig_style),
            Paragraph("<u>Signature of the Second Tabulator</u><br/>Date:", sig_style),
            Paragraph("<u>Signature of the Chairman, Examination Committee</u><br/>Date:", sig_style)
        ]]
        sig_table = Table(sig_data, colWidths=['33%', '33%', '33%'])
        elements.append(sig_table)
        return elements

@result_management_bp.route('/download/course_result/<int:session_id>/<int:subject_id>')
@login_required
def download_course_result(session_id, subject_id):
    session = RSession.query.get_or_404(session_id)
    subject = RSubject.query.get_or_404(subject_id)
    results = db.session.query(RStudent, RMark).join(RMark).filter(
        RStudent.session_id == session_id,
        RMark.subject_id == subject_id
    ).order_by(RStudent.student_id).all()

    buffer = io.BytesIO()
    pdf = CourseTabulationPDF(buffer, subject, session)
    elements = pdf.generate_elements(results)
    pdf.build(elements)
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'course_result_{subject.code}.pdf', mimetype='application/pdf')

@result_management_bp.route('/download/student_result/<int:session_id>/<int:student_id>')
@login_required
def download_student_result(student_id, session_id):
    student = RStudent.query.get_or_404(student_id)
    session = RSession.query.get_or_404(session_id)
    
    marks = RMark.query.filter_by(student_id=student_id).join(RSubject).order_by(RSubject.code).all()
    
    processed_results = []
    term_assessment = {
        'total_registered_credits': 0.0, 'total_earned_credits': 0.0,
        'total_earned_credit_points': 0.0, 'tgpa': 0.0
    }
    total_points_for_tgpa = 0.0

    for mark in marks:
        registered_credits = mark.subject.credit or 0.0
        grade_point = mark.grade_point or 0.0
        earned_credits = registered_credits if grade_point > 0 else 0.0
        earned_credit_points = grade_point * earned_credits
        remarks = 'Retake' if mark.is_retake else ''
        processed_results.append({
            'subject_code': mark.subject.code, 'subject_name': mark.subject.name,
            'registered_credits': registered_credits, 'grade_letter': mark.grade_letter,
            'grade_point': grade_point, 'earned_credits': earned_credits,
            'earned_credit_points': earned_credit_points, 'remarks': remarks
        })
        term_assessment['total_registered_credits'] += registered_credits
        term_assessment['total_earned_credits'] += earned_credits
        term_assessment['total_earned_credit_points'] += earned_credit_points
        total_points_for_tgpa += grade_point * registered_credits

    if term_assessment['total_registered_credits'] > 0:
        term_assessment['tgpa'] = total_points_for_tgpa / term_assessment['total_registered_credits']

    buffer = io.BytesIO()
    pdf = StudentTabulationPDF(buffer, student, session)
    elements = pdf.generate_elements(processed_results, term_assessment)
    pdf.build(elements)

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'student_result_{student.student_id}.pdf', mimetype='application/pdf')

@result_management_bp.route('/download/all_student_results/<int:session_id>')
@login_required
def download_all_student_results(session_id):
    session = RSession.query.get_or_404(session_id)
    students = RStudent.query.filter_by(session_id=session_id).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, False) as zip_file:
        for student in students:
            # Re-use logic from single student download
            marks = RMark.query.filter_by(student_id=student.id).join(RSubject).order_by(RSubject.code).all()
            processed_results = []
            term_assessment = {'total_registered_credits': 0.0, 'total_earned_credits': 0.0, 'total_earned_credit_points': 0.0, 'tgpa': 0.0}
            total_points_for_tgpa = 0.0
            for mark in marks:
                registered_credits = mark.subject.credit or 0.0
                grade_point = mark.grade_point or 0.0
                earned_credits = registered_credits if grade_point > 0 else 0.0
                earned_credit_points = grade_point * earned_credits
                remarks = 'Retake' if mark.is_retake else ''
                processed_results.append({'subject_code': mark.subject.code, 'subject_name': mark.subject.name, 'registered_credits': registered_credits, 'grade_letter': mark.grade_letter, 'grade_point': grade_point, 'earned_credits': earned_credits, 'earned_credit_points': earned_credit_points, 'remarks': remarks})
                term_assessment['total_registered_credits'] += registered_credits
                term_assessment['total_earned_credits'] += earned_credits
                term_assessment['total_earned_credit_points'] += earned_credit_points
                total_points_for_tgpa += grade_point * registered_credits
            if term_assessment['total_registered_credits'] > 0:
                term_assessment['tgpa'] = total_points_for_tgpa / term_assessment['total_registered_credits']

            # Generate PDF in memory
            pdf_buffer = io.BytesIO()
            pdf = StudentTabulationPDF(pdf_buffer, student, session)
            elements = pdf.generate_elements(processed_results, term_assessment)
            pdf.build(elements)
            pdf_buffer.seek(0)
            
            # Add PDF to zip
            zip_file.writestr(f'student_result_{student.student_id}.pdf', pdf_buffer.getvalue())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'student_results_{session.name}.zip', mimetype='application/zip')

@result_management_bp.route('/download/all_course_results/<int:session_id>')
@login_required
def download_all_course_results(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED, False) as zip_file:
        for subject in subjects:
            results = db.session.query(RStudent, RMark).join(RMark).filter(RStudent.session_id == session_id, RMark.subject_id == subject.id).order_by(RStudent.student_id).all()
            if not results:
                continue

            # Generate PDF in memory
            pdf_buffer = io.BytesIO()
            pdf = CourseTabulationPDF(pdf_buffer, subject, session)
            elements = pdf.generate_elements(results)
            pdf.build(elements)
            pdf_buffer.seek(0)
            
            # Add PDF to zip
            zip_file.writestr(f'course_result_{subject.code}.pdf', pdf_buffer.getvalue())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'course_results_{session.name}.zip', mimetype='application/zip')
