from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Frame, PageTemplate
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import inch
from io import BytesIO
from .models import db, RSession, RStudent, RSubject, RMark, RCourseRegistration
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
        name = request.form.get('name')
        term = request.form.get('term')
        year = request.form.get('year')
        
        if name and term:
            new_session = RSession(name=name, term=term, year=year)
            db.session.add(new_session)
            db.session.commit()
            flash('Session added successfully!', 'success')
            return redirect(url_for('result_management.index'))
        else:
            flash('Session Name and Term are required.', 'danger')
            
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

    # Only show students who are registered for the selected subject
    if selected_subject:
        registered_student_ids = db.session.query(RCourseRegistration.student_id).filter_by(subject_id=selected_subject.id).all()
        registered_student_ids = [sid for (sid,) in registered_student_ids]
        students = RStudent.query.filter(RStudent.id.in_(registered_student_ids)).order_by(RStudent.student_id).all()
    else:
        students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()
    
    marks_data = {}
    registrations_data = {} # To store retake status
    if selected_subject:
        for student in students:
            mark = RMark.query.filter_by(student_id=student.id, subject_id=selected_subject.id).first()
            marks_data[student.id] = mark
            
            registration = RCourseRegistration.query.filter_by(student_id=student.id, subject_id=selected_subject.id).first()
            registrations_data[student.id] = registration

    if request.method == 'POST':
        subject_id = request.form.get('subject_id', type=int)
        if not subject_id:
            flash('Please select a subject.', 'danger')
            return redirect(url_for('result_management.add_marks', session_id=session_id))

        subject = RSubject.query.get_or_404(subject_id)

        for student in students:
            existing_mark = RMark.query.filter_by(student_id=student.id, subject_id=subject.id).first()
            if existing_mark is None:
                existing_mark = RMark(student_id=student.id, subject_id=subject.id)
                db.session.add(existing_mark)
            
            # Check if the student is registered for this course as a retake
            registration = RCourseRegistration.query.filter_by(student_id=student.id, subject_id=subject.id).first()
            is_retake = registration.is_retake if registration else False
            existing_mark.is_retake = is_retake

            total_marks = 0
            if subject.subject_type == 'Theory' or subject.subject_type == 'Theory (UG)':
                attendance = request.form.get(f'attendance_{student.id}')
                continuous_assessment = request.form.get(f'continuous_assessment_{student.id}')
                part_a = request.form.get(f'part_a_{student.id}')
                part_b = request.form.get(f'part_b_{student.id}')
                
                existing_mark.attendance = float(attendance) if attendance else None
                existing_mark.continuous_assessment = float(continuous_assessment) if continuous_assessment else None
                existing_mark.part_a = float(part_a) if part_a else None
                existing_mark.part_b = float(part_b) if part_b else None
                
                total_marks = sum(filter(None, [existing_mark.attendance, existing_mark.continuous_assessment, existing_mark.part_a, existing_mark.part_b]))
            
            elif subject.subject_type == 'Sessional':
                attendance = request.form.get(f'attendance_{student.id}')
                sessional_report = request.form.get(f'sessional_report_{student.id}')
                sessional_viva = request.form.get(f'sessional_viva_{student.id}')

                existing_mark.attendance = float(attendance) if attendance else None
                existing_mark.sessional_report = float(sessional_report) if sessional_report else None
                existing_mark.sessional_viva = float(sessional_viva) if sessional_viva else None

                total_marks = sum(filter(None, [existing_mark.attendance, existing_mark.sessional_report, existing_mark.sessional_viva]))

            elif subject.subject_type == 'Dissertation':
                supervisor_assessment = request.form.get(f'supervisor_assessment_{student.id}')
                proposal_presentation = request.form.get(f'proposal_presentation_{student.id}')
                project_report = request.form.get(f'project_report_{student.id}')
                defense = request.form.get(f'defense_{student.id}')
                
                existing_mark.supervisor_assessment = float(supervisor_assessment) if supervisor_assessment else None
                existing_mark.proposal_presentation = float(proposal_presentation) if proposal_presentation else None
                existing_mark.project_report = float(project_report) if project_report else None
                existing_mark.defense = float(defense) if defense else None

                total_marks = sum(filter(None, [existing_mark.supervisor_assessment, existing_mark.proposal_presentation, existing_mark.project_report, existing_mark.defense]))
            
            existing_mark.total_marks = total_marks
            existing_mark.grade_point, existing_mark.grade_letter = calculate_grade(total_marks, is_retake=is_retake)

        db.session.commit()
        flash(f'Marks for {subject.name} saved successfully!', 'success')
        return redirect(url_for('result_management.add_marks', session_id=session_id, subject_id=subject.id))

    return render_template('rm_add_marks.html', 
                           session=session, 
                           subjects=subjects,
                           students=students,
                           selected_subject=selected_subject,
                           marks_data=marks_data,
                           registrations_data=registrations_data)

@result_management_bp.route('/view_results/<int:session_id>')
@login_required
def view_results(session_id):
    session = RSession.query.get_or_404(session_id)
    return render_template('rm_view_results.html', session=session)

@result_management_bp.route('/course_wise_result/<int:session_id>')
@login_required
def course_wise_result(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).order_by(RSubject.code).all()
    selected_subject_id = request.args.get('subject_id', type=int)
    results = []
    selected_subject = None
    if selected_subject_id:
        selected_subject = RSubject.query.get(selected_subject_id)
        
        # Define columns to select
        base_columns = [
            RStudent.student_id, RStudent.name, RMark.total_marks,
            RMark.grade_letter, RMark.grade_point, RMark.is_retake
        ]
        
        extra_columns = []
        if selected_subject:
            if selected_subject.subject_type in ['Theory', 'Theory (UG)']:
                extra_columns = [RMark.attendance, RMark.continuous_assessment, RMark.part_a, RMark.part_b]
            elif selected_subject.subject_type == 'Sessional':
                extra_columns = [RMark.attendance, RMark.sessional_report, RMark.sessional_viva]
            elif selected_subject.subject_type == 'Dissertation':
                if selected_subject.dissertation_type == 'Type1':
                    extra_columns = [RMark.supervisor_assessment, RMark.proposal_presentation]
                else:  # Type2
                    extra_columns = [RMark.supervisor_assessment, RMark.project_report, RMark.defense]
        
        all_columns = base_columns + extra_columns
        
        results = db.session.query(*all_columns)\
            .join(RMark, RStudent.id == RMark.student_id)\
            .filter(RMark.subject_id == selected_subject_id)\
            .order_by(RStudent.student_id).all()

    return render_template('rm_course_wise_result.html',
                           session=session,
                           subjects=subjects,
                           selected_subject_id=selected_subject_id,
                           selected_subject=selected_subject,
                           results=results)

@result_management_bp.route('/student_wise_result/<int:session_id>')
@login_required
def student_wise_result(session_id):
    session = RSession.query.get_or_404(session_id)
    students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()

    selected_student_id = request.args.get('student_id', type=int)
    selected_student = None
    results = []
    term_assessment = {}

    if selected_student_id:
        selected_student = RStudent.query.get(selected_student_id)
        # Fetch results for the selected student
        results = db.session.query(
            RSubject.code.label('subject_code'),
            RSubject.name.label('subject_name'),
            RSubject.credit.label('registered_credits'),
            RMark.grade_letter,
            RMark.grade_point,
            RMark.is_retake,
            RSubject.subject_type
        ).select_from(RMark)\
         .join(RStudent, RStudent.id == RMark.student_id)\
         .join(RSubject, RSubject.id == RMark.subject_id)\
         .filter(RStudent.id == selected_student_id)\
         .order_by(RSubject.code).all()

        total_registered_credits = 0
        total_earned_credits = 0
        total_earned_credit_points = 0
        
        processed_results = []
        for res in results:
            earned_credits = res.registered_credits if (res.grade_point or 0) >= 2.0 else 0
            earned_credit_points = (res.grade_point or 0) * res.registered_credits
            
            processed_results.append({
                'subject_code': res.subject_code,
                'subject_name': res.subject_name,
                'registered_credits': res.registered_credits,
                'grade_letter': res.grade_letter,
                'grade_point': res.grade_point,
                'earned_credits': earned_credits,
                'earned_credit_points': earned_credit_points,
                'remarks': 'Retake' if res.is_retake else ''
            })

            total_registered_credits += res.registered_credits
            total_earned_credits += earned_credits
            total_earned_credit_points += earned_credit_points

        tgpa = total_earned_credit_points / total_registered_credits if total_registered_credits > 0 else 0
        
        term_assessment = {
            'total_registered_credits': total_registered_credits,
            'total_earned_credits': total_earned_credits,
            'total_earned_credit_points': total_earned_credit_points,
            'tgpa': tgpa
        }
        results = processed_results
        
    return render_template('rm_student_wise_result.html',
                           session=session,
                           students=students,
                           selected_student_id=selected_student_id,
                           selected_student=selected_student,
                           results=results,
                           term_assessment=term_assessment)


@result_management_bp.route('/course_registration/<int:session_id>', methods=['GET', 'POST'])
@login_required
def course_registration(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).order_by(RSubject.code).all()
    students = RStudent.query.filter_by(session_id=session_id).order_by(RStudent.student_id).all()

    selected_subject_id = request.args.get('subject_id', type=int)
    selected_subject = RSubject.query.get(selected_subject_id) if selected_subject_id else None

    registrations = {}
    if selected_subject:
        # Load existing registrations for the selected subject
        existing_regs = db.session.query(RCourseRegistration).filter_by(subject_id=selected_subject.id).all()
        for reg in existing_regs:
            registrations[reg.student_id] = reg

    if request.method == 'POST':
        subject_id = int(request.form.get('subject_id'))
        if not subject_id:
            flash('A subject must be selected.', 'danger')
            return redirect(url_for('result_management.course_registration', session_id=session_id))
        
        # Get all student IDs that were submitted (i.e., whose checkboxes could have been checked)
        students_on_page = RStudent.query.filter_by(session_id=session_id).all()
        student_ids_on_page = {s.id for s in students_on_page}

        # First, delete all existing registrations for this subject for the students shown on the page
        db.session.query(RCourseRegistration).filter(
            RCourseRegistration.subject_id == subject_id,
            RCourseRegistration.student_id.in_(student_ids_on_page)
        ).delete(synchronize_session=False)

        # Now, add back the ones that were checked in the form
        for student_id in student_ids_on_page:
            if f'reg_{student_id}' in request.form:
                is_retake = f'retake_{student_id}' in request.form
                new_reg = RCourseRegistration(
                    student_id=student_id,
                    subject_id=subject_id,
                    is_retake=is_retake
                )
                db.session.add(new_reg)

                # Sync the is_retake flag with the corresponding RMark record
                mark = RMark.query.filter_by(student_id=student_id, subject_id=subject_id).first()
                if mark:
                    mark.is_retake = is_retake
                    # Recalculate grade if total_marks exists
                    if mark.total_marks is not None:
                        mark.grade_point, mark.grade_letter = calculate_grade(mark.total_marks, is_retake=is_retake)
            else:
                 # If a student is unregistered, ensure their mark record also has is_retake as False
                mark = RMark.query.filter_by(student_id=student_id, subject_id=subject_id).first()
                if mark and mark.is_retake:
                    mark.is_retake = False
                    if mark.total_marks is not None:
                        mark.grade_point, mark.grade_letter = calculate_grade(mark.total_marks, is_retake=False)

        db.session.commit()
        flash('Course registration updated successfully!', 'success')
        return redirect(url_for('result_management.course_registration', session_id=session_id, subject_id=subject_id))

    return render_template('rm_course_registration.html', 
                           session=session, 
                           students=students, 
                           subjects=subjects,
                           selected_subject=selected_subject,
                           registrations=registrations)


@result_management_bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    session = RSession.query.get_or_404(session_id)
    db.session.delete(session)
    db.session.commit()
    flash('Session and all related data deleted successfully.', 'success')
    return redirect(url_for('result_management.index'))


class PDFGenerator:
    def __init__(self, buffer, pagesize):
        self.buffer = buffer
        if pagesize == 'A4':
            self.pagesize = A4
        elif pagesize == 'Letter':
            self.pagesize = letter
        self.doc = SimpleDocTemplate(buffer, pagesize=self.pagesize)
        self.story = []

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_number_text = f"Page {doc.page} of {doc.doc.page_count}"
        canvas.drawRightString(self.pagesize[0] - inch, 0.5 * inch, page_number_text)
        canvas.restoreState()

    def build(self, elements):
        # A two-pass approach to get total page numbers for the footer
        
        # First pass
        doc_temp = SimpleDocTemplate(BytesIO(), pagesize=self.pagesize)
        frame = Frame(doc_temp.leftMargin, doc_temp.bottomMargin, doc_temp.width, doc_temp.height, id='normal')
        template = PageTemplate(id='main_temp', frames=[frame])
        doc_temp.addPageTemplates([template])
        doc_temp.build(elements)
        self.total_pages = doc_temp.page

        # Second pass (actual build)
        frame = Frame(self.doc.leftMargin, self.doc.bottomMargin, self.doc.width, self.doc.height, id='normal')
        template = PageTemplate(id='main', frames=[frame], onPage=self._footer)
        self.doc.addPageTemplates([template])
        self.doc.build(elements)

class CourseTabulationPDF(PDFGenerator):
    def __init__(self, buffer, subject, session):
        super().__init__(buffer, pagesize='A4')
        self.subject = subject
        self.session = session
        self.doc.title = f"Course_Result_{subject.code}"

    def generate_elements(self, results):
        styles = getSampleStyleSheet()
        # Custom styles
        styles.add(ParagraphStyle(name='Center', alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='Right', alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name='Left', alignment=TA_LEFT))
        styles.add(ParagraphStyle(name='Line_Data', parent=styles['Normal'], alignment=TA_CENTER, leading=14))
        
        # Center align headers
        styles['h1'].alignment = TA_CENTER
        styles['h2'].alignment = TA_CENTER
        
        elements = []
        
        # Header
        elements.append(Paragraph("Khulna University", styles['h1']))
        elements.append(Paragraph("Course-wise Tabulation Sheet", styles['h2']))
        elements.append(Spacer(1, 0.2*inch))

        # Info Table
        info_data = [
            [
                Paragraph(f"<b>Year:</b> {self.session.year or 'N/A'}<br/><b>Discipline:</b> Law<br/><b>Course No.:</b> {self.subject.code}<br/><b>Course Title:</b> {self.subject.name}", styles['Left']),
                Paragraph(f"<b>Term:</b> {self.session.term}<br/><b>School:</b> Law<br/><b>CH:</b> {self.subject.credit:.1f}<br/><br/><b>Session:</b> {self.session.name}", styles['Left'])
            ]
        ]
        info_table = Table(info_data, colWidths=[4.5*inch, 2.5*inch])
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.2*inch))

        # Results Table
        table_headers = ['Student\nNo.', 'Attendance\n(10)', 'Continuous\nAssessment\n(40)', 'Section A\n(25)', 'Section B\n(25)', 'Total\nMarks\n(100)', 'Grade\nPoint', 'Grade\nLetter', 'Remarks']
        
        # Base headers
        base_headers = ['Student\nNo.']
        specific_headers = []
        
        # Specific headers based on subject type
        if self.subject.subject_type in ['Theory', 'Theory (UG)']:
            specific_headers = ['Attendance\n(10)', 'C.A.\n(40)', 'Sec. A\n(25)', 'Sec. B\n(25)']
        elif self.subject.subject_type == 'Sessional':
            specific_headers = ['Attendance\n(10)', 'Report\n(60)', 'Viva\n(30)']
        elif self.subject.subject_type == 'Dissertation':
            if self.subject.dissertation_type == 'Type1':
                specific_headers = ['Supervisor\n(70)', 'Presentation\n(30)']
            else:
                specific_headers = ['Supervisor\n(50)', 'Report\n(25)', 'Defense\n(25)']
        
        end_headers = ['Total\nMarks\n(100)', 'Grade\nPoint', 'Grade\nLetter', 'Remarks']
        table_headers = base_headers + specific_headers + end_headers
        data = [table_headers]

        for res in results:
            row_data = [res.student_id]
            
            # Unpack the rest of the data dynamically
            marks_data = list(res)[6:] # Get the specific mark components
            
            for mark in marks_data:
                 row_data.append(f"{mark:.1f}" if mark is not None else '')

            row_data.extend([
                f"{res.total_marks:.2f}" if res.total_marks is not None else '',
                f"{res.grade_point:.2f}" if res.grade_point is not None else '',
                res.grade_letter or '',
                'Retake' if res.is_retake else ''
            ])
            data.append(row_data)

        # Dynamic column widths
        base_widths = [1.1*inch]
        specific_widths = [0.8*inch] * len(specific_headers)
        end_widths = [0.7*inch, 0.7*inch, 0.7*inch, 0.8*inch]
        col_widths = base_widths + specific_widths + end_widths
        
        table = Table(data, colWidths=col_widths, rowHeights=0.5*inch)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table.setStyle(style)
        elements.append(table)
        elements.append(Spacer(1, 0.5*inch))
        
        # Signature section
        signature_data = [
            [Paragraph('-----------------------', styles['Center']), Paragraph('-----------------------', styles['Center']), Paragraph('-----------------------', styles['Center'])],
            [Paragraph('Signature of Scrutinizer', styles['Center']), Paragraph('Signature of Tabulator', styles['Center']), Paragraph('Signature of the Head', styles['Center'])]
        ]
        
        signature_table = Table(signature_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
        signature_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(signature_table)
        
        return elements

class StudentTabulationPDF(PDFGenerator):
    def __init__(self, buffer, student, session):
        super().__init__(buffer)
        self.student = student
        self.session = session
        self.page_count = 0
        self.doc.title = f"Tabulation_{student.student_id}"

    def _footer(self, canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        page_num_text = f"Page {doc.page} of {self.page_count}"
        canvas.drawCentredString(letter[0]/2.0, 0.5 * inch, page_num_text)
        canvas.restoreState()

    def generate_pdf(self, results, term_assessment):
        elements = self.generate_elements(results, term_assessment)
        
        # Use a temporary buffer to do a "dry run" of the build, which allows
        # us to count the total number of pages.
        from io import BytesIO
        temp_buffer = BytesIO()
        temp_doc = SimpleDocTemplate(temp_buffer, pagesize=letter)
        temp_doc.build(elements)
        self.page_count = temp_doc.page

        # Now, build the real document, passing the footer function which now
        # has access to the total page count.
        self.doc.build(elements, onFirstPage=self._footer, onLaterPages=self._footer)

    def generate_elements(self, results, term_assessment):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='Center', parent=styles['Normal'], alignment=TA_CENTER))
        styles.add(ParagraphStyle(name='Left', parent=styles['Normal'], alignment=TA_LEFT))
        styles['h1'].alignment = TA_CENTER
        styles['h3'].alignment = TA_CENTER

        elements = []
        
        # Header
        elements.append(Paragraph("Khulna University", styles['h1']))
        elements.append(Paragraph("Student-wise Tabulation Sheet", styles['h3']))
        elements.append(Spacer(1, 0.2*inch))
        
        # Student Info Table
        year_text = self.session.year or (self.student.year or 'N/A')
        info_data = [
            [
                Paragraph(f"<b>Year:</b> {year_text}<br/><b>Student No.:</b> {self.student.student_id}<br/><b>Discipline:</b> {self.student.discipline or 'Law'}", styles['Left']),
                Paragraph(f"<b>Term:</b> {self.session.term}<br/><b>Name of Student:</b> {self.student.name}<br/><b>Session:</b> {self.session.name}<br/><b>School:</b> {self.student.school or 'Law'}", styles['Left'])
            ]
        ]
        info_table = Table(info_data, colWidths=[3.5*inch, 3.5*inch])
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (0, 0), (-1, -1), 'LEFT')]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.2*inch))

        # Results Table
        headers = ['Course No.', 'Course Title', 'Registered<br/>Credit<br/>Hours', 'Letter<br/>Grade', 'Grade<br/>Point<br/>(GP)', 'Earned<br/>Credit<br/>Hours (CH)', 'Earned<br/>Credit<br/>Points<br/>(GP*CH)', 'Remarks']
        data = [[]]
        for h in headers:
            data[0].append(Paragraph(h, styles['Center']))

        for res in results:
            data.append([
                Paragraph(res['subject_code'], styles['Center']),
                Paragraph(res['subject_name'], styles['Normal']),
                Paragraph(f"{res['registered_credits']:.1f}", styles['Center']),
                Paragraph(res['grade_letter'] or '', styles['Center']),
                Paragraph(f"{res['grade_point']:.2f}" if res['grade_point'] is not None else '', styles['Center']),
                Paragraph(f"{res['earned_credits']:.1f}", styles['Center']),
                Paragraph(f"{res['earned_credit_points']:.2f}", styles['Center']),
                Paragraph(res['remarks'], styles['Center'])
            ])

        col_widths = [1.0*inch, 2.0*inch, 0.7*inch, 0.6*inch, 0.6*inch, 0.7*inch, 0.7*inch, 0.7*inch]
        table = Table(data, colWidths=col_widths)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'), # Course title left aligned
        ])
        table.setStyle(style)
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Term Assessment
        assessment_text = f"""
        <b>Term Assessment</b><br/>
        Total Earned Credit Hours in this Term (TCH) = {term_assessment['total_earned_credits']:.1f}<br/>
        Total Registered Credit Hours in this Term (RCH) = {term_assessment['total_registered_credits']:.1f}<br/>
        Total Earned Credit Points in this Term (TCP) = {term_assessment['total_earned_credit_points']:.2f}<br/>
        <b>TGPA = TCP/RCH = {term_assessment['tgpa']:.2f}</b>
        """
        elements.append(Paragraph(assessment_text, styles['Normal']))
        elements.append(Spacer(1, 0.5*inch))

        # Signature section
        signature_data = [
            [
                Paragraph('<u>Signature of the First Tabulator</u><br/>Date:', styles['Center']),
                Paragraph('<u>Signature of the Second Tabulator</u><br/>Date:', styles['Center']),
                Paragraph('<u>Signature of the Chairman, Examination<br/>Committee</u><br/>Date:', styles['Center'])
            ]
        ]
        signature_table = Table(signature_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
        signature_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(signature_table)
        
        return elements


@result_management_bp.route('/download/course_result/<int:session_id>/<int:subject_id>')
@login_required
def download_course_result(session_id, subject_id):
    subject = RSubject.query.get_or_404(subject_id)
    session = RSession.query.get_or_404(session_id)

    # Define columns to select
    base_columns = [
        RStudent.student_id, RStudent.name, RMark.total_marks,
        RMark.grade_letter, RMark.grade_point, RMark.is_retake
    ]
    
    extra_columns = []
    if subject:
        if subject.subject_type in ['Theory', 'Theory (UG)']:
            extra_columns = [RMark.attendance, RMark.continuous_assessment, RMark.part_a, RMark.part_b]
        elif subject.subject_type == 'Sessional':
            extra_columns = [RMark.attendance, RMark.sessional_report, RMark.sessional_viva]
        elif subject.subject_type == 'Dissertation':
            if subject.dissertation_type == 'Type1':
                extra_columns = [RMark.supervisor_assessment, RMark.proposal_presentation]
            else:  # Type2
                extra_columns = [RMark.supervisor_assessment, RMark.project_report, RMark.defense]
    
    all_columns = base_columns + extra_columns
    
    results = db.session.query(*all_columns)\
        .join(RMark, RStudent.id == RMark.student_id)\
        .filter(RMark.subject_id == subject_id)\
        .order_by(RStudent.student_id).all()

    buffer = BytesIO()
    pdf = CourseTabulationPDF(buffer, subject, session)
    elements = pdf.generate_elements(results)
    pdf.doc.build(elements)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f'Course_{subject.code}_Result.pdf', mimetype='application/pdf')

@result_management_bp.route('/download/student_result/<int:session_id>/<int:student_id>')
@login_required
def download_student_result(session_id, student_id):
    student = RStudent.query.get_or_404(student_id)
    session = RSession.query.get_or_404(session_id)

    # Re-use the logic from student_wise_result
    results_query = db.session.query(
        RSubject.code.label('subject_code'),
        RSubject.name.label('subject_name'),
        RSubject.credit.label('registered_credits'),
        RMark.grade_letter, RMark.grade_point, RMark.is_retake, RSubject.subject_type
    ).select_from(RMark).join(RStudent, RStudent.id == RMark.student_id).join(RSubject, RSubject.id == RMark.subject_id)\
    .filter(RStudent.id == student_id).order_by(RSubject.code).all()
        
    total_registered_credits, total_earned_credits, total_earned_credit_points = 0, 0, 0
    processed_results = []
    for res in results_query:
        earned_credits = res.registered_credits if (res.grade_point or 0) >= 2.0 else 0
        earned_credit_points = (res.grade_point or 0) * res.registered_credits
        processed_results.append({
            'subject_code': res.subject_code, 'subject_name': res.subject_name,
            'registered_credits': res.registered_credits, 'grade_letter': res.grade_letter,
            'grade_point': res.grade_point, 'earned_credits': earned_credits,
            'earned_credit_points': earned_credit_points,
            'remarks': 'Retake' if res.is_retake else ''
        })
        total_registered_credits += res.registered_credits
        total_earned_credits += earned_credits
        total_earned_credit_points += earned_credit_points

    tgpa = total_earned_credit_points / total_registered_credits if total_registered_credits > 0 else 0
    term_assessment = {
        'total_registered_credits': total_registered_credits, 'total_earned_credits': total_earned_credits,
        'total_earned_credit_points': total_earned_credit_points, 'tgpa': tgpa
    }

    buffer = BytesIO()
    pdf = StudentTabulationPDF(buffer, student, session)
    pdf.generate_pdf(processed_results, term_assessment)
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'Student_{student.student_id}_Tabulation.pdf', mimetype='application/pdf')


@result_management_bp.route('/download/all_student_results/<int:session_id>')
@login_required
def download_all_student_results(session_id):
    session = RSession.query.get_or_404(session_id)
    students = RStudent.query.filter_by(session_id=session_id).all()
    
    if not students:
        flash('No students in this session to generate results for.', 'warning')
        return redirect(url_for('result_management.student_wise_result', session_id=session_id))

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zf:
        for student in students:
            # Re-use logic from download_student_result
            results_query = db.session.query(
                RSubject.code.label('subject_code'), RSubject.name.label('subject_name'), RSubject.credit.label('registered_credits'),
                RMark.grade_letter, RMark.grade_point, RMark.is_retake, RSubject.subject_type
            ).select_from(RMark).join(RStudent, RStudent.id == RMark.student_id).join(RSubject, RSubject.id == RMark.subject_id)\
            .filter(RStudent.id == student.id).order_by(RSubject.code).all()

            if not results_query: continue

            total_registered_credits, total_earned_credits, total_earned_credit_points = 0, 0, 0
            processed_results = []
            for res in results_query:
                earned_credits = res.registered_credits if (res.grade_point or 0) >= 2.0 else 0
                earned_credit_points = (res.grade_point or 0) * res.registered_credits
                processed_results.append({
                    'subject_code': res.subject_code, 'subject_name': res.subject_name, 'registered_credits': res.registered_credits,
                    'grade_letter': res.grade_letter, 'grade_point': res.grade_point, 'earned_credits': earned_credits,
                    'earned_credit_points': earned_credit_points, 'remarks': 'Retake' if res.is_retake else ''
                })
                total_registered_credits += res.registered_credits
                total_earned_credits += earned_credits
                total_earned_credit_points += earned_credit_points
            
            tgpa = total_earned_credit_points / total_registered_credits if total_registered_credits > 0 else 0
            term_assessment = {
                'total_registered_credits': total_registered_credits, 'total_earned_credits': total_earned_credits,
                'total_earned_credit_points': total_earned_credit_points, 'tgpa': tgpa
            }
            
            pdf_buffer = BytesIO()
            pdf = StudentTabulationPDF(pdf_buffer, student, session)
            pdf.generate_pdf(processed_results, term_assessment)
            pdf_buffer.seek(0)
            zf.writestr(f'Student_{student.student_id}_Tabulation.pdf', pdf_buffer.read())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'All_Student_Results_{session.name}.zip', mimetype='application/zip')

@result_management_bp.route('/download/all_course_results/<int:session_id>')
@login_required
def download_all_course_results(session_id):
    session = RSession.query.get_or_404(session_id)
    subjects = RSubject.query.filter_by(session_id=session_id).all()

    if not subjects:
        flash('No subjects in this session to generate results for.', 'warning')
        return redirect(url_for('result_management.course_wise_result', session_id=session_id))
        
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zf:
        for subject in subjects:
            results = db.session.query(
                RStudent.student_id, RStudent.name, RMark.total_marks,
                RMark.grade_letter, RMark.grade_point
            ).join(RMark, RStudent.id == RMark.student_id)\
            .filter(RMark.subject_id == subject.id).order_by(RStudent.student_id).all()

            if not results: continue

            pdf_buffer = BytesIO()
            pdf = CourseTabulationPDF(pdf_buffer, subject, session)
            elements = pdf.generate_elements(results)
            pdf.doc.build(elements)
            pdf_buffer.seek(0)
            zf.writestr(f'Course_{subject.code}_Result.pdf', pdf_buffer.read())

    zip_buffer.seek(0)
    return send_file(zip_buffer, as_attachment=True, download_name=f'All_Course_Results_{session.name}.zip', mimetype='application/zip')
