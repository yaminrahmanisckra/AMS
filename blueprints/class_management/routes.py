from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, Response, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, text
from .models import (
    db,
    Teacher,
    Session,
    ClassStudent,
    ClassAttendance,
    ClassSplitInvite,
    CourseReview,
    EvaluationInvite,
    EvaluationSubmission,
    ExamScrutinizerInvite,
    ExamPaperEvaluation,
    StudentFeedbackLink,
    StudentFeedbackResponse,
    CourseOutline,
)
from models import User  # Import the User model from the new models file
try:
    from blueprints.student_management.models import Student
except ImportError:
    Student = None

try:
    from blueprints.course_management.models import Curriculum, Course, CurriculumYearTerm, CourseSessionAssignment, StudentCourseRegistration
except ImportError:
    Curriculum = None
    CourseSessionAssignment = None
    Course = None
    CurriculumYearTerm = None
    StudentCourseRegistration = None
import pandas as pd
import os
from datetime import datetime, date
import secrets
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from collections import Counter, defaultdict
from reportlab.lib.units import inch
import io
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import json
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
# docx imports moved to lazy imports (only when needed) to prevent startup hang
# from docx import Document
# from docx.shared import Pt, Inches
# from docx.oxml.ns import qn
# from docx.oxml import OxmlElement
# from docx.enum.text import WD_ALIGN_PARAGRAPH
from uuid import uuid4
from role_utils import has_teacher_privileges, is_admin, parse_roles

# WeasyPrint lazy import - only import when needed to prevent startup hang
# Module-level import removed because it causes startup hang on macOS
# This prevents the app from hanging during startup
_WEASYPRINT_HTML = None
_WEASYPRINT_AVAILABLE = None

def _get_weasyprint_html():
    """Lazy import WeasyPrint HTML - only import when actually needed"""
    global _WEASYPRINT_HTML, _WEASYPRINT_AVAILABLE
    
    if _WEASYPRINT_AVAILABLE is None:
        # First time - try to import
        import logging
        import os
        import platform
        import ctypes
        from ctypes import util as ctypes_util
        
        logger = logging.getLogger(__name__)
        
        # Setup library paths for macOS BEFORE importing WeasyPrint
        if platform.system() == 'Darwin':
            homebrew_lib_path = '/opt/homebrew/lib'
            if os.path.exists(homebrew_lib_path):
                # Set environment variables
                os.environ['DYLD_FALLBACK_LIBRARY_PATH'] = f"{homebrew_lib_path}:{os.environ.get('DYLD_FALLBACK_LIBRARY_PATH', '')}"
                os.environ['PKG_CONFIG_PATH'] = f"/opt/homebrew/lib/pkgconfig:{os.environ.get('PKG_CONFIG_PATH', '')}"
                
                # Monkey-patch ctypes.util.find_library
                original_find_library = ctypes_util.find_library
                def patched_find_library(name):
                    lib_mappings = {
                        'gobject-2.0-0': 'libgobject-2.0.0.dylib',
                        'gobject-2.0': 'libgobject-2.0.dylib',
                    }
                    if name in lib_mappings:
                        lib_path = os.path.join(homebrew_lib_path, lib_mappings[name])
                        if os.path.exists(lib_path):
                            return lib_path
                    for pattern in [f'lib{name}.dylib', f'lib{name}.0.dylib']:
                        lib_path = os.path.join(homebrew_lib_path, pattern)
                        if os.path.exists(lib_path):
                            return lib_path
                    result = original_find_library(name)
                    return result if result else None
                
                ctypes_util.find_library = patched_find_library
                
                # Pre-load libraries
                try:
                    lib_path = os.path.join(homebrew_lib_path, 'libgobject-2.0.0.dylib')
                    if os.path.exists(lib_path):
                        ctypes.CDLL(lib_path, mode=ctypes.RTLD_GLOBAL)
                except:
                    pass
        
        try:
            logger.info("Attempting to import WeasyPrint (lazy import)...")
            from weasyprint import HTML
            _WEASYPRINT_HTML = HTML
            _WEASYPRINT_AVAILABLE = True
            logger.info("✓ WeasyPrint imported successfully (lazy import)")
        except ImportError as e:
            _WEASYPRINT_AVAILABLE = False
            _WEASYPRINT_HTML = None
            logger.error(f"✗ WeasyPrint ImportError: {e}")
            logger.warning("PDF generation features will be disabled.")
        except Exception as e:
            _WEASYPRINT_AVAILABLE = False
            _WEASYPRINT_HTML = None
            logger.error(f"✗ WeasyPrint import error: {e}", exc_info=True)
            logger.warning("PDF generation features will be disabled.")
    
    if _WEASYPRINT_AVAILABLE and _WEASYPRINT_HTML is None:
        # Retry if somehow HTML is None but available is True
        try:
            from weasyprint import HTML
            _WEASYPRINT_HTML = HTML
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to re-import WeasyPrint: {e}")
            _WEASYPRINT_AVAILABLE = False
    
    return _WEASYPRINT_HTML if _WEASYPRINT_AVAILABLE else None

def _is_weasyprint_available():
    """Check if WeasyPrint is available (lazy check)"""
    if _WEASYPRINT_AVAILABLE is None:
        _get_weasyprint_html()  # Trigger lazy import
    return _WEASYPRINT_AVAILABLE is True


COURSE_REVIEW_GRADE_ROWS = [
    {'key': 'grade_a_plus', 'scale': '80% and above', 'letter': 'A+'},
    {'key': 'grade_a', 'scale': '75% to less than 80%', 'letter': 'A'},
    {'key': 'grade_a_minus', 'scale': '70% to less than 75%', 'letter': 'A-'},
    {'key': 'grade_b_plus', 'scale': '65% to less than 70%', 'letter': 'B+'},
    {'key': 'grade_b', 'scale': '60% to less than 65%', 'letter': 'B'},
    {'key': 'grade_b_minus', 'scale': '55% to less than 60%', 'letter': 'B-'},
    {'key': 'grade_c_plus', 'scale': '50% to less than 55%', 'letter': 'C+'},
    {'key': 'grade_c', 'scale': '45% to less than 50%', 'letter': 'C'},
    {'key': 'grade_d', 'scale': '40% to less than 45%', 'letter': 'D'},
    {'key': 'grade_f', 'scale': 'Less than 40%', 'letter': 'F'},
    {'key': 'grade_i', 'scale': 'Incomplete', 'letter': 'I'},
    {'key': 'grade_w', 'scale': 'Withdrawal', 'letter': 'W'},
]

COURSE_REVIEW_COMMENT_FIELDS = [
    {'key': 'comment_student_questionnaires', 'label': '1) Student (Course Evaluation) Questionnaires:'},
    {'key': 'comment_external_examiners', 'label': '2) External Examiners or Moderators (if any):'},
    {'key': 'comment_curriculum', 'label': '3) Curriculum: Comment on the continuing appropriateness of the Course curriculum in relation to the intended learning outcomes and its compliance with the National Qualification Framework'},
    {'key': 'comment_assessment', 'label': '4) Assessment: Comment on the continuing effectiveness of method(s) of assessment in relation to the intended learning outcomes (Course objectives)'},
    {'key': 'comment_enhancement', 'label': '5) Enhancement: Comment on the implementation of changes proposed in earlier Faculty Course Review Reports'},
    {'key': 'comment_future_changes', 'label': "6) Outline any changes in the future delivery or structure of the Course that this semester/term's experience may prompt"},
]

SCOPE_FULL = 'full'
SCOPE_PART_A = 'part_a'
SCOPE_PART_B = 'part_b'
SPLIT_PARTS = {SCOPE_PART_A, SCOPE_PART_B}
COURSE_SCOPE_LABELS = {
    SCOPE_FULL: 'Full Course',
    SCOPE_PART_A: 'Part A',
    SCOPE_PART_B: 'Part B',
}

def _generate_feedback_code():
    """Generate a short, URL-friendly code for feedback access."""
    while True:
        raw = secrets.token_urlsafe(8)
        code = ''.join(ch for ch in raw if ch.isalnum()).upper()
        code = code[:10]
        if len(code) < 6:
            continue
        if not StudentFeedbackLink.query.filter_by(access_code=code).first():
            return code

class_management_bp = Blueprint(
    'class_management', __name__,
    template_folder='templates',
    static_folder='static'
)


@class_management_bp.before_request
def restrict_to_teaching_roles():
    if not current_user.is_authenticated:
        return
    
    # Allow student view scores route for all authenticated users
    if request.endpoint == 'class_management.student_view_scores':
        return
    
    if has_teacher_privileges(current_user):
        return
    flash('Class Management is available only to teaching staff.', 'danger')
    return redirect(url_for('index'))


def _ensure_current_teacher():
    """Return a Teacher instance for the logged-in user, creating one if needed."""
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if teacher:
        return teacher

    base = (current_user.full_name or 'teacher').split(' ')[0].lower()
    base = ''.join(ch for ch in base if ch.isalnum()) or 'teacher'
    base = base[:10]
    candidate = base
    counter = 1
    while Teacher.query.filter_by(short_name=candidate).first():
        suffix = str(counter)
        candidate = f"{base[:10-len(suffix)]}{suffix}"
        counter += 1

    teacher = Teacher(name=current_user.full_name, short_name=candidate)
    db.session.add(teacher)
    db.session.commit()
    return teacher


def _get_related_sessions(session, include_archived=False):
    """Return all sessions that belong to the same split group."""
    if not session or not session.split_group_id:
        return [session] if session else []

    query = Session.query.filter_by(split_group_id=session.split_group_id)
    if not include_archived:
        query = query.filter_by(archived=False)
    related = query.order_by(Session.id.asc()).all()
    return related or [session]


def _carry_on_assessment_marks(class_student, session):
    """Carry on previous assessment marks for retake students if carry_on is enabled in registration"""
    if not StudentCourseRegistration or not Student:
        return
    
    try:
        # Get student record from Students Management
        student_record = Student.query.filter_by(student_id=class_student.student_id).first()
        if not student_record:
            return
        
        # Find registration for this course and session
        registration = StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            course_code=session.course_code,
            academic_session=session.academic_session,
            year=session.year,
            term=session.term
        ).first()
        
        if not registration or not registration.carry_on:
            return
        
        # Only carry on for retake/re-retake students
        if registration.remark not in ['Retake', 'Re-retake']:
            return
        
        # Find previous session with same course_code and student_id
        # Look for sessions with different academic_session/year/term
        previous_sessions = Session.query.filter(
            Session.course_code == session.course_code,
            Session.id != session.id,
            Session.archived == False
        ).order_by(Session.academic_session.desc(), Session.created_at.desc()).all()
        
        for prev_session in previous_sessions:
            # Find student in previous session
            prev_student = ClassStudent.query.filter_by(
                session_id=prev_session.id,
                student_id=class_student.student_id
            ).first()
            
            if prev_student:
                # Copy assessment marks
                if prev_student.assessment1 is not None:
                    class_student.assessment1 = prev_student.assessment1
                if prev_student.assessment2 is not None:
                    class_student.assessment2 = prev_student.assessment2
                if prev_student.assessment3 is not None:
                    class_student.assessment3 = prev_student.assessment3
                if prev_student.assessment4 is not None:
                    class_student.assessment4 = prev_student.assessment4
                
                current_app.logger.info(
                    f'Carried on assessment marks for student {class_student.student_id} '
                    f'from session {prev_session.id} to session {session.id}'
                )
                break  # Only carry from the most recent previous session
    except Exception as e:
        current_app.logger.error(f'Error carrying on assessment marks: {str(e)}', exc_info=True)


def _replicate_student_to_peers(session, source_student, *, old_identifier=None):
    """Create or update a student record across split peer sessions."""
    if not session or not session.split_group_id:
        return

    peer_sessions = [s for s in _get_related_sessions(session) if s.id != session.id]
    for peer in peer_sessions:
        identifier = old_identifier or source_student.student_id
        peer_student = ClassStudent.query.filter_by(session_id=peer.id, student_id=identifier).first()
        if not peer_student:
            peer_student = ClassStudent(
                student_id=source_student.student_id,
                name=source_student.name,
                session_id=peer.id,
                teacher_id=peer.teacher_id
            )
            db.session.add(peer_student)
        else:
            peer_student.student_id = source_student.student_id
            peer_student.name = source_student.name


def _delete_student_from_peers(session, student_identifier):
    """Remove a student from all peer sessions within the split group."""
    if not session or not session.split_group_id:
        return

    for peer in _get_related_sessions(session):
        if peer.id == session.id:
            continue
        peer_student = ClassStudent.query.filter_by(session_id=peer.id, student_id=student_identifier).first()
        if peer_student:
            db.session.delete(peer_student)


def _gather_split_student_map(session):
    """Return related sessions and a map of student_id -> [ClassStudent,...]."""
    related_sessions = _get_related_sessions(session)
    session_ids = [s.id for s in related_sessions if s]
    if not session_ids:
        return related_sessions, {}

    students = ClassStudent.query.filter(ClassStudent.session_id.in_(session_ids)).all()
    student_map = defaultdict(list)
    for stu in students:
        student_map[stu.student_id].append(stu)
    return related_sessions, student_map


def _recalculate_assessment_totals(session):
    """Recompute assessment aggregates across split sessions."""
    if not session or session.course_type != 'theory':
        return

    _, student_map = _gather_split_student_map(session)
    for entries in student_map.values():
        marks = []
        for entry in entries:
            for idx in range(1, 5):
                value = getattr(entry, f'assessment{idx}')
                if value is not None:
                    marks.append(value)
        marks.sort(reverse=True)

        if session.category == 'pg':
            if marks:
                best = marks[:3] if len(marks) >= 3 else marks
                avg = sum(best) / len(best)
                # Convert best 3 sum to 40 marks scale: always use 30 as max (sum / 30) * 40
                best_sum = sum(best)
                total_40 = int(round((best_sum / 30) * 40))  # Round for PG courses
                avg_value = round(avg, 2)
            else:
                avg_value = None
                total_40 = None
            for entry in entries:
                entry.assessment_avg = avg_value
                entry.assessment_total_40 = total_40
                entry.assessment_total = None
        else:
            if marks:
                best = marks[:3] if len(marks) >= 3 else marks
                total = sum(best)  # Keep fraction for UG courses, no rounding
            else:
                total = None
            for entry in entries:
                entry.assessment_total = total
                entry.assessment_avg = None
                entry.assessment_total_40 = None


def _collect_combined_assessment_marks(session):
    """Return a map of student_id -> list of assessment marks across split sessions."""
    _, student_map = _gather_split_student_map(session)
    marks_map = {}
    for student_id, entries in student_map.items():
        values = []
        for entry in entries:
            for idx in range(1, 5):
                val = getattr(entry, f'assessment{idx}')
                if val is not None:
                    values.append(val)
        marks_map[student_id] = values
    return marks_map


def _build_combined_assessment_values(session):
    """
    Combine assessment values from all related sessions in a split course.
    
    Returns:
        value_map: {student_id: {1: val1, 2: val2, 3: val3, 4: val4}}
        ug_best3: {student_id: best3_total}
        pg_avg_map: {student_id: average}
        pg_total_map: {student_id: total_40_scale}
    """
    # Step 1: Get all related sessions (if split course)
    if session.split_group_id:
        related_sessions = Session.query.filter_by(
            split_group_id=session.split_group_id,
            archived=False
        ).all()
    else:
        related_sessions = [session]
    
    if not related_sessions:
        return {}, {}, {}, {}
    
    # Step 2: Get ALL ClassStudent records from ALL related sessions
    session_ids = [s.id for s in related_sessions]
    all_class_students = ClassStudent.query.filter(
        ClassStudent.session_id.in_(session_ids)
    ).all()
    
    # Step 3: Group by student_id (STRING) - same student from different sessions
    # Structure: {student_id: [ClassStudent_from_session_A, ClassStudent_from_session_B, ...]}
    student_groups = defaultdict(list)
    for cs in all_class_students:
        student_groups[cs.student_id].append(cs)
    
    # Step 4: Build combined values for each student
    value_map = {}
    ug_best3 = {}
    pg_avg_map = {}
    pg_total_map = {}
    
    for student_id, student_records in student_groups.items():
        # Initialize: {1: None, 2: None, 3: None, 4: None}
        combined = {1: None, 2: None, 3: None, 4: None}
        
        # Combine values from ALL records (sessions)
        # Example: Part A session has assessment1=10, assessment2=5
        #          Part B session has assessment3=7, assessment4=8
        # Result: {1: 10, 2: 5, 3: 7, 4: 8}
        for record in student_records:
            for idx in [1, 2, 3, 4]:
                val = getattr(record, f'assessment{idx}', None)
                # Set value if it exists and we don't have one yet
                if val is not None and combined[idx] is None:
                    try:
                        combined[idx] = float(val)
                    except (ValueError, TypeError):
                        pass
        
        value_map[student_id] = combined
        
        # Step 5: Calculate Best 3 / PG Total
        valid_marks = [v for v in combined.values() if v is not None]
        valid_marks.sort(reverse=True)  # Descending
        
        if session.category == 'pg':
            if valid_marks:
                best = valid_marks[:3] if len(valid_marks) >= 3 else valid_marks
                avg = sum(best) / len(best)
                pg_avg_map[student_id] = round(avg, 2)
                best_sum = sum(best)
                pg_total_map[student_id] = int(round((best_sum / 30) * 40))  # Round for PG courses
            else:
                pg_avg_map[student_id] = None
                pg_total_map[student_id] = None
        else:
            # UG: Best 3 total
            if valid_marks:
                best = valid_marks[:3] if len(valid_marks) >= 3 else valid_marks
                ug_best3[student_id] = sum(best)  # Keep fraction for UG courses, no rounding
            else:
                ug_best3[student_id] = None
    
    return value_map, ug_best3, pg_avg_map, pg_total_map


def _get_editable_assessment_indices(session):
    """Return which assessment inputs current teacher can edit."""
    if session.course_scope == SCOPE_PART_A:
        return {1, 2}
    if session.course_scope == SCOPE_PART_B:
        return {3, 4}
    return {1, 2, 3, 4}


def _calculate_attendance_mark_from_percentage(percentage):
    """Convert attendance percentage to marks."""
    if percentage >= 90:
        return 10
    if percentage >= 85:
        return 9
    if percentage >= 80:
        return 8
    if percentage >= 75:
        return 7
    if percentage >= 70:
        return 6
    if percentage >= 65:
        return 5
    if percentage >= 60:
        return 4
    return 0


def _build_attendance_summary(session):
    """Aggregate attendance across split sessions."""
    related_sessions = _get_related_sessions(session)
    session_ids = [s.id for s in related_sessions if s]
    if not session_ids:
        return {'total_classes': 0, 'per_student': {}, 'per_session_totals': defaultdict(int), 'related_sessions': related_sessions}

    attendance_records = ClassAttendance.query.filter(
        ClassAttendance.session_id.in_(session_ids)
    ).order_by(ClassAttendance.date.asc(), ClassAttendance.id.asc()).all()

    students = ClassStudent.query.filter(ClassStudent.session_id.in_(session_ids)).all()
    student_lookup = {stu.id: stu for stu in students}

    per_student_counts = defaultdict(lambda: {'present': 0})
    per_session_date_counts = defaultdict(lambda: defaultdict(int))

    for record in attendance_records:
        per_session_date_counts[(record.session_id, record.date)][record.student_id] += 1
        student = student_lookup.get(record.student_id)
        if not student:
            continue
        if record.is_present:
            per_student_counts[student.student_id]['present'] += 1
        per_student_counts[student.student_id]['records'] = per_student_counts[student.student_id].get('records', 0) + 1

    per_session_totals = defaultdict(int)
    total_classes = 0
    for (session_id, _), counts in per_session_date_counts.items():
        class_count = max(counts.values()) if counts else 0
        total_classes += class_count
        per_session_totals[session_id] += class_count

    per_student_result = {}
    for student in students:
        stats = per_student_counts.get(student.student_id, {'present': 0, 'records': 0})
        percentage = (stats['present'] / total_classes * 100) if total_classes else 0
        per_student_result[student.student_id] = {
            'present': stats['present'],
            'percentage': percentage,
            'marks': _calculate_attendance_mark_from_percentage(percentage)
        }

    return {
        'total_classes': total_classes,
        'per_student': per_student_result,
        'per_session_totals': per_session_totals,
        'related_sessions': related_sessions
    }


def _build_split_context(session, attendance_summary=None):
    """Prepare metadata for templates about split courses."""
    if not session or not session.split_group_id or session.course_scope == SCOPE_FULL:
        return None

    peer_info = []
    for peer in _get_related_sessions(session, include_archived=True):
        if not peer or peer.id == session.id:
            continue
        peer_info.append({
            'id': peer.id,
            'teacher_name': peer.teacher.name if peer.teacher else '—',
            'teacher_short': peer.teacher.short_name if peer.teacher else '',
            'course_scope': COURSE_SCOPE_LABELS.get(peer.course_scope, 'Part')
        })

    context = {
        'scope_label': COURSE_SCOPE_LABELS.get(session.course_scope, 'Part'),
        'peers': peer_info
    }

    if attendance_summary:
        totals = attendance_summary.get('per_session_totals', {})
        context['class_totals'] = []
        for related in attendance_summary.get('related_sessions', []):
            if not related:
                continue
            context['class_totals'].append({
                'session_id': related.id,
                'teacher_name': related.teacher.name if related.teacher else '—',
                'teacher_short': related.teacher.short_name if related.teacher else '',
                'classes': totals.get(related.id, 0),
                'is_current': related.id == session.id
            })
        context['total_classes'] = attendance_summary.get('total_classes', 0)

    return context


# Create uploads folder if it doesn't exist
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@class_management_bp.route('/')
@login_required
def index():
    """Main dashboard for class management"""
    teacher = _ensure_current_teacher()
    sessions = Session.query.filter_by(
        teacher_id=teacher.id,
        archived=False
    ).order_by(Session.created_at.desc()).all()

    current_app.logger.info(f'Loading index for teacher {teacher.id} ({teacher.name}). Found {len(sessions)} sessions.')
    for s in sessions:
        current_app.logger.debug(f'Session: ID={s.id}, Name={s.course_name}, Archived={s.archived}, Teacher={s.teacher_id}')
    
    # Update sessions with academic_session and batch from CourseSessionAssignment if available
    # Also sync all assignments with curriculum year-term config if missing
    if CourseSessionAssignment and Curriculum and CurriculumYearTerm:
        try:
            # First, update all assignments that are missing batch/academic_session from curriculum year-term config
            all_assignments = CourseSessionAssignment.query.all()
            assignment_update_count = 0
            for assignment in all_assignments:
                if assignment.curriculum_id and (not assignment.batch or not assignment.academic_session):
                    try:
                        curriculum = Curriculum.query.get(assignment.curriculum_id)
                        if curriculum:
                            year_term_config = curriculum.get_year_term_config(assignment.year, assignment.term)
                            if year_term_config:
                                updated = False
                                if not assignment.batch and year_term_config.batch and year_term_config.batch != 'None':
                                    assignment.batch = year_term_config.batch
                                    updated = True
                                    current_app.logger.info(f'Updated assignment {assignment.id} batch from year-term config: {year_term_config.batch}')
                                if not assignment.academic_session and year_term_config.academic_session:
                                    assignment.academic_session = year_term_config.academic_session
                                    updated = True
                                    current_app.logger.info(f'Updated assignment {assignment.id} academic_session from year-term config: {year_term_config.academic_session}')
                                
                                if updated:
                                    assignment_update_count += 1
                    except Exception as assign_error:
                        current_app.logger.warning(f'Error updating assignment {assignment.id}: {assign_error}')
            
            if assignment_update_count > 0:
                db.session.commit()
                current_app.logger.info(f'Updated {assignment_update_count} assignments with batch/academic_session from curriculum year-term config')
            
            # Now update sessions with academic_session from assignments
            updated_count = 0
            for session in sessions:
                # Find CourseSessionAssignment for this session
                assignment = CourseSessionAssignment.query.filter_by(session_id=session.id).first()
                if assignment:
                    # Update academic_session if assignment has it and session doesn't
                    if assignment.academic_session and not session.academic_session:
                        session.academic_session = assignment.academic_session
                        updated_count += 1
                        current_app.logger.info(f'Updated session {session.id} ({session.course_name}) with academic_session: {assignment.academic_session}')
                    elif assignment.academic_session and session.academic_session != assignment.academic_session:
                        # Update if different
                        session.academic_session = assignment.academic_session
                        updated_count += 1
                        current_app.logger.info(f'Updated session {session.id} ({session.course_name}) academic_session from {session.academic_session} to {assignment.academic_session}')
            
            if updated_count > 0:
                db.session.commit()
                current_app.logger.info(f'Updated {updated_count} sessions with academic_session from CourseSessionAssignment')
        except Exception as e:
            current_app.logger.error(f'Error updating sessions from CourseSessionAssignment: {str(e)}', exc_info=True)
            db.session.rollback()

    split_context_map = {session.id: _build_split_context(session) for session in sessions if session.split_group_id}
    # Get teachers excluding Head of the Discipline
    from role_utils import get_teachers_excluding_head
    teachers = get_teachers_excluding_head()
    pending_split_invites = ClassSplitInvite.query.filter_by(invited_teacher_id=teacher.id, status='pending').order_by(ClassSplitInvite.created_at.desc()).all()
    
    # Get all batches from Students Management for the dropdown
    batches = []
    if Student:
        try:
            all_batches = db.session.query(Student.batch).distinct().filter(Student.batch.isnot(None)).order_by(Student.batch.desc()).all()
            batches = [batch[0] for batch in all_batches]
        except Exception:
            batches = []
    
    # Build assignment map for template to access batch and academic_session from CourseSessionAssignment
    assignment_map = {}
    if CourseSessionAssignment and Course:
        try:
            for session in sessions:
                # Try to find assignment by session_id first
                assignment = CourseSessionAssignment.query.filter_by(session_id=session.id).first()
                
                # If not found by session_id, try to find by course_code, teacher_id, year, term
                if not assignment and session.course_code and session.teacher_id and session.year and session.term:
                    try:
                        # Try to match by course_code, teacher_id, year, term
                        # First try exact match
                        assignment = CourseSessionAssignment.query.filter_by(
                            teacher_id=session.teacher_id,
                            year=session.year,
                            term=session.term
                        ).join(Course, CourseSessionAssignment.course_id == Course.id).filter(
                            Course.course_code == session.course_code
                        ).first()
                        
                        # If not found, try without section matching (for full course sessions)
                        if not assignment:
                            assignment = CourseSessionAssignment.query.filter_by(
                                teacher_id=session.teacher_id,
                                year=session.year,
                                term=session.term
                            ).join(Course, CourseSessionAssignment.course_id == Course.id).filter(
                                Course.course_code == session.course_code
                            ).filter(
                                or_(
                                    CourseSessionAssignment.section.is_(None),
                                    CourseSessionAssignment.section == ''
                                )
                            ).first()
                        
                        # If found, update the session_id to link them
                        if assignment and not assignment.session_id:
                            assignment.session_id = session.id
                            assignment.session_created = True
                            try:
                                db.session.commit()
                                current_app.logger.info(f'Linked assignment {assignment.id} to session {session.id} for course {session.course_code}')
                            except Exception as commit_error:
                                db.session.rollback()
                                current_app.logger.warning(f'Could not link assignment {assignment.id} to session {session.id}: {commit_error}')
                    except Exception as query_error:
                        current_app.logger.warning(f'Error querying assignment for session {session.id}: {query_error}')
                
                if assignment:
                    # If assignment doesn't have batch/academic_session, try to get from curriculum year-term config
                    batch = assignment.batch
                    academic_session = assignment.academic_session
                    
                    if Curriculum and CurriculumYearTerm and (not batch or not academic_session):
                        try:
                            if assignment.curriculum_id:
                                curriculum = Curriculum.query.get(assignment.curriculum_id)
                                if curriculum:
                                    year_term_config = curriculum.get_year_term_config(assignment.year, assignment.term)
                                    if year_term_config:
                                        if not batch and year_term_config.batch and year_term_config.batch != 'None':
                                            batch = year_term_config.batch
                                            assignment.batch = batch
                                            current_app.logger.info(f'Updated assignment {assignment.id} batch from year-term config: {batch}')
                                        if not academic_session and year_term_config.academic_session:
                                            academic_session = year_term_config.academic_session
                                            assignment.academic_session = academic_session
                                            current_app.logger.info(f'Updated assignment {assignment.id} academic_session from year-term config: {academic_session}')
                                        
                                        if (not assignment.batch and batch) or (not assignment.academic_session and academic_session):
                                            try:
                                                db.session.commit()
                                            except Exception as commit_error:
                                                db.session.rollback()
                                                current_app.logger.warning(f'Could not update assignment {assignment.id}: {commit_error}')
                        except Exception as config_error:
                            current_app.logger.warning(f'Error getting year-term config for assignment {assignment.id}: {config_error}')
                    
                    assignment_map[session.id] = {
                        'batch': batch or '',
                        'academic_session': academic_session or ''
                    }
                    # Also update session's academic_session if assignment has it and session doesn't
                    if academic_session and not session.academic_session:
                        try:
                            session.academic_session = academic_session
                            db.session.commit()
                            current_app.logger.info(f'Updated session {session.id} academic_session from assignment: {academic_session}')
                        except Exception as update_error:
                            db.session.rollback()
                            current_app.logger.warning(f'Could not update session {session.id} academic_session: {update_error}')
                    
                    # Auto-add students from batch if session has no students but batch is available
                    if batch and batch.strip() and batch != 'None' and Student:
                        try:
                            existing_students_count = ClassStudent.query.filter_by(session_id=session.id).count()
                            if existing_students_count == 0:
                                current_app.logger.info(f'Session {session.id} has no students but batch {batch} is available. Attempting to add students...')
                                students_from_batch = Student.query.filter_by(batch=batch).all()
                                if students_from_batch:
                                    added_count = 0
                                    for student in students_from_batch:
                                        # Check if student is registered for this course (finalized registration only)
                                        if StudentCourseRegistration and session.course_code and session.academic_session and session.year and session.term:
                                            registration = StudentCourseRegistration.query.filter_by(
                                                student_id=student.id,
                                                course_code=session.course_code,
                                                academic_session=session.academic_session,
                                                year=session.year,
                                                term=session.term,
                                                status='finalized'
                                            ).first()
                                            
                                            if not registration:
                                                current_app.logger.info(f'Student {student.student_id} ({student.name}) not registered for course {session.course_code}, skipping...')
                                                continue
                                        
                                        class_student = ClassStudent(
                                            student_id=student.student_id,
                                            name=student.name,
                                            session_id=session.id,
                                            teacher_id=session.teacher_id
                                        )
                                        db.session.add(class_student)
                                        db.session.flush()  # Flush to get class_student.id before carry on
                                        
                                        # Carry on assessment marks if enabled in registration
                                        _carry_on_assessment_marks(class_student, session)
                                        
                                        # Replicate to peer sessions for split courses
                                        _replicate_student_to_peers(session, class_student)
                                        
                                        added_count += 1
                                    
                                    if added_count > 0:
                                        db.session.commit()
                                        current_app.logger.info(f'Successfully added {added_count} students from batch {batch} to session {session.id}')
                                else:
                                    current_app.logger.warning(f'No students found in batch {batch} for session {session.id}')
                        except Exception as auto_add_error:
                            db.session.rollback()
                            current_app.logger.error(f'Error auto-adding students to session {session.id} from batch {batch}: {auto_add_error}', exc_info=True)
        except Exception as e:
            current_app.logger.error(f'Error building assignment map: {str(e)}', exc_info=True)
            db.session.rollback()

    return render_template(
        'class_management/index.html',
        sessions=sessions,
        teacher=teacher,
        teacher_display_name=(getattr(current_user, 'full_name', '') or teacher.name or current_user.username),
        teachers=teachers,
        course_scope_labels=COURSE_SCOPE_LABELS,
        split_context_map=split_context_map,
        pending_split_invites=pending_split_invites,
        batches=batches,
        assignment_map=assignment_map
    )

@class_management_bp.route('/create_session', methods=['POST'])
@login_required
def create_session():
    """Create a new session"""
    try:
        teacher = _ensure_current_teacher()
        batch = request.form.get('batch', '').strip()
        curriculum_id = request.form.get('curriculum_id', type=int)
        year = request.form.get('year', '').strip()
        term = request.form.get('term', '').strip()
        academic_session = request.form.get('academic_session', '').strip()
        course_id = request.form.get('course_id', type=int)
        course_code = request.form.get('course_code', '').strip()
        course_name = request.form.get('course_name', '').strip()
        course_type = request.form.get('course_type', 'theory')
        category = request.form.get('category', 'ug')
        course_scope = request.form.get('course_scope', SCOPE_FULL)
        partner_teacher_id = request.form.get('partner_teacher_id')
        
        current_app.logger.info(f'Creating session - batch: {batch}, curriculum_id: {curriculum_id}, year: {year}, term: {term}, course_name: {course_name}, course_code: {course_code}')
        
        # If course_id is provided, fetch course details from Course model
        if course_id and Course:
            course = Course.query.get(course_id)
            if course:
                course_code = course.course_code
                course_name = course.course_name
                course_type = course.course_type.lower()
                category = course.category
                current_app.logger.info(f'Fetched course details from Course model: {course_code} - {course_name}')
        
        if not year or not term:
            flash('Year and term are required!', 'error')
            current_app.logger.warning(f'Missing year or term - year: {year}, term: {term}')
            return redirect(url_for('class_management.index'))
        
        if not course_code or not course_name:
            flash('Course code and course name are required!', 'error')
            current_app.logger.warning(f'Missing course_code or course_name - code: {course_code}, name: {course_name}')
            return redirect(url_for('class_management.index'))

        if course_scope not in COURSE_SCOPE_LABELS:
            flash('Invalid course scope selection.', 'error')
            return redirect(url_for('class_management.index'))

        # Prevent more than two teachers (Part A & Part B) from taking the same course simultaneously
        active_sessions = Session.query.filter(
            Session.course_code == course_code,
            Session.archived.is_(False)
        ).all()
        full_exists = any(s.course_scope == SCOPE_FULL for s in active_sessions)
        part_a_exists = any(s.course_scope == SCOPE_PART_A for s in active_sessions)
        part_b_exists = any(s.course_scope == SCOPE_PART_B for s in active_sessions)

        if full_exists:
            flash('This course already has a full-course session. Delete the existing session before assigning another teacher.', 'error')
            return redirect(url_for('class_management.index'))

        if part_a_exists and part_b_exists:
            flash('Both Part A and Part B are already assigned to teachers. Delete an existing section before adding another teacher.', 'error')
            return redirect(url_for('class_management.index'))

        if course_scope == SCOPE_FULL and (part_a_exists or part_b_exists):
            flash('This course is already split between teachers. Delete the split sections before creating a full-course session.', 'error')
            return redirect(url_for('class_management.index'))

        if course_scope == SCOPE_PART_A and part_a_exists:
            flash('Part A is already assigned to another teacher. Delete the existing Part A session before reassigning.', 'error')
            return redirect(url_for('class_management.index'))

        if course_scope == SCOPE_PART_B and part_b_exists:
            flash('Part B is already assigned to another teacher. Delete the existing Part B session before reassigning.', 'error')
            return redirect(url_for('class_management.index'))

        if course_scope == SCOPE_FULL:
            session_obj = Session(
                year=year,
                term=term,
                academic_session=academic_session,
                course_code=course_code,
                course_name=course_name,
                teacher_id=teacher.id,
                course_type=course_type,
                category=category,
                course_scope=SCOPE_FULL
            )
            db.session.add(session_obj)
            db.session.flush()  # Get session ID before commit
            
            # Automatically add students from Students Management based on batch
            if batch and Student:
                try:
                    students_from_batch = Student.query.filter_by(batch=batch).all()
                    added_count = 0
                    skipped_count = 0
                    
                    # Get existing student IDs for this session to avoid duplicates
                    existing_student_ids = set()
                    
                    for student in students_from_batch:
                        # Check if already exists
                        existing = ClassStudent.query.filter_by(
                            session_id=session_obj.id,
                            student_id=student.student_id
                        ).first()
                        
                        if existing:
                            skipped_count += 1
                            continue
                        
                        class_student = ClassStudent(
                            student_id=student.student_id,
                            name=student.name,
                            session_id=session_obj.id,
                            teacher_id=teacher.id
                        )
                        db.session.add(class_student)
                        db.session.flush()  # Flush to get class_student.id before carry on
                        
                        # Carry on assessment marks if enabled in registration
                        _carry_on_assessment_marks(class_student, session_obj)
                        
                        _replicate_student_to_peers(session_obj, class_student)
                        added_count += 1
                    
                    db.session.commit()
                    
                    if added_count > 0:
                        flash(f'Session created successfully! Automatically added {added_count} students from batch {batch}.', 'success')
                    else:
                        flash('Session created successfully!', 'success')
                        if skipped_count > 0:
                            flash(f'Note: {skipped_count} students were already in the session.', 'info')
                except Exception as e:
                    db.session.rollback()
                    current_app.logger.error(f'Error auto-adding students: {str(e)}', exc_info=True)
                    db.session.commit()  # Commit session even if student addition fails
                    flash('Session created successfully, but there was an error adding students automatically.', 'warning')
            else:
                db.session.commit()
                flash('Session created successfully!', 'success')
            
            current_app.logger.info(f'Session created successfully - ID: {session_obj.id}, Name: {course_name}')
            return redirect(url_for('class_management.index'))

        # Handle split course (Part A/B)
        counterpart_scope = SCOPE_PART_B if course_scope == SCOPE_PART_A else SCOPE_PART_A

        try:
            partner_teacher_id_int = int(partner_teacher_id) if partner_teacher_id else None
        except (TypeError, ValueError):
            partner_teacher_id_int = None

        partner_teacher = None
        if partner_teacher_id_int:
            partner_teacher = Teacher.query.get(partner_teacher_id_int)

        if not partner_teacher:
            flash('Please select the teacher who will take the other part.', 'error')
            return redirect(url_for('class_management.index'))

        if partner_teacher.id == teacher.id:
            flash('Please assign a different teacher for the other part.', 'error')
            return redirect(url_for('class_management.index'))

        split_group_id = str(uuid4())

        current_session = Session(
            year=year,
            term=term,
            academic_session=academic_session,
            course_code=course_code,
            course_name=course_name,
            teacher_id=teacher.id,
            course_type=course_type,
            category=category,
            course_scope=course_scope,
            split_group_id=split_group_id
        )
        db.session.add(current_session)
        db.session.flush()

        invite = ClassSplitInvite(
            split_group_id=split_group_id,
            inviter_session_id=current_session.id,
            inviter_teacher_id=teacher.id,
            invited_teacher_id=partner_teacher.id,
            invited_scope=counterpart_scope,
            status='pending'
        )
        db.session.add(invite)
        
        # Automatically add students from Students Management based on batch
        if batch and Student:
            try:
                students_from_batch = Student.query.filter_by(batch=batch).all()
                added_count = 0
                skipped_count = 0
                not_registered_count = 0
                
                for student in students_from_batch:
                    # Check if already exists
                    existing = ClassStudent.query.filter_by(
                        session_id=current_session.id,
                        student_id=student.student_id
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Check if student is registered for this course (finalized registration only)
                    if StudentCourseRegistration and current_session.course_code and current_session.academic_session and current_session.year and current_session.term:
                        registration = StudentCourseRegistration.query.filter_by(
                            student_id=student.id,
                            course_code=current_session.course_code,
                            academic_session=current_session.academic_session,
                            year=current_session.year,
                            term=current_session.term,
                            status='finalized'
                        ).first()
                        
                        if not registration:
                            not_registered_count += 1
                            current_app.logger.info(f'Student {student.student_id} ({student.name}) not registered for course {current_session.course_code}, skipping...')
                            continue
                    
                    class_student = ClassStudent(
                        student_id=student.student_id,
                        name=student.name,
                        session_id=current_session.id,
                        teacher_id=teacher.id
                    )
                    db.session.add(class_student)
                    db.session.flush()  # Flush to get class_student.id before carry on
                    
                    # Carry on assessment marks if enabled in registration
                    _carry_on_assessment_marks(class_student, current_session)
                    
                    _replicate_student_to_peers(current_session, class_student)
                    added_count += 1
                
                # Commit session, invite, and students together
                db.session.commit()
                
                if added_count > 0:
                    message = f'Split course created. Invitation sent. Automatically added {added_count} students from batch {batch}.'
                    if not_registered_count > 0:
                        message += f' Skipped {not_registered_count} student(s) not registered for this course.'
                    flash(message, 'success')
                else:
                    flash('Split course created. Invitation sent to the selected teacher.', 'success')
                    if skipped_count > 0:
                        flash(f'Note: {skipped_count} students were already in the session.', 'info')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f'Error auto-adding students to split course: {str(e)}', exc_info=True)
                # Still commit the session and invite even if student addition fails
                db.session.add(current_session)
                db.session.add(invite)
                db.session.commit()
                flash('Split course created. Invitation sent, but there was an error adding students automatically.', 'warning')
        else:
            # Commit session and invite
            db.session.commit()
            flash('Split course created. Invitation sent to the selected teacher.', 'success')
        
        current_app.logger.info(f'Split session created successfully - ID: {current_session.id}, Name: {course_name}')
        return redirect(url_for('class_management.index'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating session: {str(e)}', exc_info=True)
        flash(f'Error creating session: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))


@class_management_bp.route('/split_invites/<int:invite_id>/accept', methods=['POST'])
@login_required
def accept_split_invite(invite_id):
    teacher = _ensure_current_teacher()
    invite = ClassSplitInvite.query.get_or_404(invite_id)
    if invite.invited_teacher_id != teacher.id:
        flash('You are not authorized to respond to this invitation.', 'error')
        return redirect(url_for('class_management.index'))
    if invite.status != 'pending':
        flash('This invitation has already been processed.', 'info')
        return redirect(url_for('class_management.index'))

    inviter_session = Session.query.get(invite.inviter_session_id)
    if not inviter_session:
        invite.status = 'declined'
        invite.responded_at = datetime.utcnow()
        db.session.commit()
        flash('The original course is no longer available.', 'error')
        return redirect(url_for('class_management.index'))

    new_session = Session(
        year=inviter_session.year,
        term=inviter_session.term,
        academic_session=inviter_session.academic_session,
        course_code=inviter_session.course_code,
        course_name=inviter_session.course_name,
        teacher_id=teacher.id,
        course_type=inviter_session.course_type,
        category=inviter_session.category,
        course_scope=invite.invited_scope,
        split_group_id=invite.split_group_id
    )
    db.session.add(new_session)
    db.session.flush()

    inviter_students = ClassStudent.query.filter_by(session_id=inviter_session.id).all()
    for stu in inviter_students:
        clone = ClassStudent(
            student_id=stu.student_id,
            name=stu.name,
            session_id=new_session.id,
            teacher_id=teacher.id
        )
        db.session.add(clone)

    invite.status = 'accepted'
    invite.responded_at = datetime.utcnow()
    db.session.commit()
    flash('Invitation accepted. The course has been added to your dashboard.', 'success')
    return redirect(url_for('class_management.index'))


@class_management_bp.route('/split_invites/<int:invite_id>/decline', methods=['POST'])
@login_required
def decline_split_invite(invite_id):
    teacher = _ensure_current_teacher()
    invite = ClassSplitInvite.query.get_or_404(invite_id)
    if invite.invited_teacher_id != teacher.id:
        flash('You are not authorized to respond to this invitation.', 'error')
        return redirect(url_for('class_management.index'))
    if invite.status != 'pending':
        flash('This invitation has already been processed.', 'info')
        return redirect(url_for('class_management.index'))

    invite.status = 'declined'
    invite.responded_at = datetime.utcnow()
    db.session.commit()
    flash('Invitation declined.', 'info')
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/upload_students/<int:session_id>', methods=['POST'])
@login_required
def upload_students(session_id):
    """Upload students from Excel file"""
    teacher = _ensure_current_teacher()
    
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
                teacher_id=session.teacher_id or teacher.id
            )
            db.session.add(student)
            _replicate_student_to_peers(session, student)
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
                                is_double_class=is_double_class,
                                split_meta=_build_split_context(session))
    except Exception as e:
        current_app.logger.error(f"Error loading attendance page for session {session_id}: {e}")
        flash(f'Error loading attendance page: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))

@class_management_bp.route('/view_attendance/<int:session_id>')
@login_required
def view_attendance(session_id):
    """View attendance for a session and display a detailed report."""
    session = Session.query.get_or_404(session_id)
    
    # Check user permissions: admin/head can view any session, regular teachers only their own
    user_roles = set(parse_roles(getattr(current_user, 'role', '')))
    if getattr(current_user, 'active_role', None):
        user_roles = set(parse_roles(current_user.active_role))
    can_view_all = is_admin(current_user) or 'head' in user_roles or 'dean' in user_roles
    
    # If not admin/head, check if this session belongs to the current teacher
    if not can_view_all:
        current_teacher = _ensure_current_teacher()
        if not current_teacher or session.teacher_id != current_teacher.id:
            flash('You do not have permission to view attendance for this session.', 'danger')
            return redirect(url_for('class_management.index'))
    
    attendance_summary = _build_attendance_summary(session)
    part_total_classes = None
    if session.course_scope in SPLIT_PARTS:
        part_total_classes = attendance_summary.get('per_session_totals', {}).get(session.id, 0)
    
    # Check if this is a split course
    is_split_course = session.split_group_id and session.course_scope in SPLIT_PARTS
    related_sessions = []
    if is_split_course:
        related_sessions = _get_related_sessions(session, include_archived=True)
    
    # For split courses, prepare separate attendance data for each teacher
    teacher_attendance_data = []
    if is_split_course and related_sessions:
        # Check user permissions: admin/head can see all parts, regular teachers only their own
        user_roles = set(parse_roles(getattr(current_user, 'role', '')))
        if getattr(current_user, 'active_role', None):
            user_roles = set(parse_roles(current_user.active_role))
        can_view_all = is_admin(current_user) or 'head' in user_roles or 'dean' in user_roles
        
        # Get current teacher if not admin/head
        current_teacher = None
        if not can_view_all:
            current_teacher = _ensure_current_teacher()
        
        # Get all students from all related sessions (for marks calculation)
        all_session_ids = [s.id for s in related_sessions]
        all_students = ClassStudent.query.filter(ClassStudent.session_id.in_(all_session_ids)).order_by(ClassStudent.student_id).all()
        student_lookup = {stu.student_id: stu for stu in all_students}
        
        # Get combined attendance summary for marks (this stays the same)
        agg_student_map = attendance_summary.get('per_student', {})
        agg_total_classes = attendance_summary.get('total_classes', 0)
        
        # Prepare data for each teacher/session (filtered by permissions)
        for related_session in related_sessions:
            # Skip if user doesn't have permission to view this session
            if not can_view_all:
                if not current_teacher or related_session.teacher_id != current_teacher.id:
                    continue
            session_students = ClassStudent.query.filter_by(session_id=related_session.id).order_by(ClassStudent.student_id).all()
            session_attendance_records = ClassAttendance.query.filter_by(session_id=related_session.id).order_by(ClassAttendance.date, ClassAttendance.id).all()
            
            if not session_attendance_records:
                continue
            
            # Build attendance data for this session
            attendance_by_date = defaultdict(list)
            for record in session_attendance_records:
                attendance_by_date[record.date].append(record)
            
            daily_class_counts = {}
            for date, records in attendance_by_date.items():
                student_counts_on_date = defaultdict(int)
                for record in records:
                    student_counts_on_date[record.student_id] += 1
                daily_class_counts[date] = max(student_counts_on_date.values()) if student_counts_on_date else 0
            
            headers_with_meta = []
            sorted_dates = sorted(daily_class_counts.keys())
            for date in sorted_dates:
                count = daily_class_counts.get(date, 0)
                if count == 1:
                    headers_with_meta.append({'label': date.strftime('%b %d, %Y'), 'date': date.strftime('%Y-%m-%d'), 'slot': 1})
                else:
                    for i in range(1, count + 1):
                        headers_with_meta.append({'label': f"{date.strftime('%b %d')} ({i})", 'date': date.strftime('%Y-%m-%d'), 'slot': i})
            
            student_report_data = []
            for student in session_students:
                student_records = [r for r in session_attendance_records if r.student_id == student.id]
                # Use combined stats for marks calculation
                agg_stats = agg_student_map.get(student.student_id, {'present': 0, 'percentage': 0, 'marks': 0})
                
                attendance_row = []
                student_attendance_by_date = defaultdict(list)
                for r in student_records:
                    student_attendance_by_date[r.date].append(r)
                
                for date in sorted_dates:
                    records_for_date = student_attendance_by_date[date]
                    num_classes_on_day = daily_class_counts.get(date, 0)
                    for i in range(num_classes_on_day):
                        cell = {
                            'status': '-',
                            'date': date.strftime('%Y-%m-%d'),
                            'slot': i + 1
                        }
                        if i < len(records_for_date):
                            record = records_for_date[i]
                            cell['status'] = 'P' if record.is_present else 'A'
                            cell['record_id'] = record.id
                        attendance_row.append(cell)
                
                student_data = {
                    'info': student,
                    'attendance_row': attendance_row,
                    'total_classes': agg_total_classes,  # Combined total for marks
                    'present_count': agg_stats['present'],  # Combined present count
                    'percentage': f"{agg_stats['percentage']:.2f}%",  # Combined percentage
                    'marks': agg_stats['marks']  # Combined marks
                }
                student_report_data.append(student_data)
            
            teacher_attendance_data.append({
                'session': related_session,
                'teacher_name': related_session.teacher.name if related_session.teacher else 'Unknown',
                'teacher_short': related_session.teacher.short_name if related_session.teacher else '',
                'scope_label': COURSE_SCOPE_LABELS.get(related_session.course_scope, 'Part'),
                'headers_with_meta': headers_with_meta,
                'student_report_data': student_report_data,
                'part_total_classes': attendance_summary.get('per_session_totals', {}).get(related_session.id, 0),
                'unique_dates': sorted(attendance_by_date.keys(), reverse=True)  # For delete modal
            })
        
        # Get unique dates from all sessions for delete modal
        all_attendance_records = ClassAttendance.query.filter(ClassAttendance.session_id.in_(all_session_ids)).all()
        attendance_by_date_all = defaultdict(list)
        for record in all_attendance_records:
            attendance_by_date_all[record.date].append(record)
        unique_dates_for_modal = sorted(attendance_by_date_all.keys(), reverse=True)
        
        return render_template(
            'class_management/view_attendance.html',
            session=session,
            headers=[],
            headers_with_meta=[],
            student_report_data=[],
            unique_dates=unique_dates_for_modal,
            split_meta=_build_split_context(session, attendance_summary),
            attendance_summary=attendance_summary,
            part_total_classes=part_total_classes,
            is_split_course=True,
            teacher_attendance_data=teacher_attendance_data
        )
    
    # Non-split course: original logic
    students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
    all_attendance_records = ClassAttendance.query.filter_by(session_id=session_id).order_by(ClassAttendance.date, ClassAttendance.id).all()
    student_lookup = {stu.id: stu for stu in students}

    headers_with_meta = []
    if not all_attendance_records:
        return render_template(
            'class_management/view_attendance.html',
            session=session,
            students=students,
            headers=[],
            headers_with_meta=headers_with_meta,
            student_report_data=[],
            unique_dates=[],
            split_meta=_build_split_context(session, attendance_summary),
            attendance_summary=attendance_summary,
            part_total_classes=part_total_classes,
            is_split_course=False,
            teacher_attendance_data=[]
        )

    attendance_by_date = defaultdict(list)
    for record in all_attendance_records:
        attendance_by_date[record.date].append(record)

    unique_dates_for_modal = sorted(attendance_by_date.keys(), reverse=True)

    daily_class_counts = {}
    for date, records in attendance_by_date.items():
        student_counts_on_date = defaultdict(int)
        for record in records:
            student_counts_on_date[record.student_id] += 1
        daily_class_counts[date] = max(student_counts_on_date.values()) if student_counts_on_date else 0

    headers = []
    headers_with_meta = []
    sorted_dates = sorted(daily_class_counts.keys())
    for date in sorted_dates:
        count = daily_class_counts.get(date, 0)
        if count == 1:
            headers.append(date.strftime('%b %d, %Y'))
            headers_with_meta.append({'label': date.strftime('%b %d, %Y'), 'date': date.strftime('%Y-%m-%d'), 'slot': 1})
        else:
            for i in range(1, count + 1):
                headers.append(f"{date.strftime('%b %d')} ({i})")
                headers_with_meta.append({'label': f"{date.strftime('%b %d')} ({i})", 'date': date.strftime('%Y-%m-%d'), 'slot': i})

    student_report_data = []
    agg_student_map = attendance_summary.get('per_student', {})
    agg_total_classes = attendance_summary.get('total_classes', sum(daily_class_counts.values()))

    for student in students:
        student_records = [r for r in all_attendance_records if r.student_id == student.id]
        agg_stats = agg_student_map.get(student.student_id, {'present': 0, 'percentage': 0, 'marks': 0})

        attendance_row = []
        student_attendance_by_date = defaultdict(list)
        for r in student_records:
            student_attendance_by_date[r.date].append(r)

        for date in sorted_dates:
            records_for_date = student_attendance_by_date[date]
            num_classes_on_day = daily_class_counts.get(date, 0)
            for i in range(num_classes_on_day):
                cell = {
                    'status': '-',
                    'date': date.strftime('%Y-%m-%d'),
                    'slot': i + 1
                }
                if i < len(records_for_date):
                    record = records_for_date[i]
                    cell['status'] = 'P' if record.is_present else 'A'
                    cell['record_id'] = record.id
                attendance_row.append(cell)

        student_data = {
            'info': student,
            'attendance_row': attendance_row,
            'total_classes': agg_total_classes,
            'present_count': agg_stats['present'],
            'percentage': f"{agg_stats['percentage']:.2f}%",
            'marks': agg_stats['marks']
        }
        student_report_data.append(student_data)

    unique_headers_with_metadata = []
    header_index = 0
    for date in sorted_dates:
        count = daily_class_counts.get(date, 0)
        if count <= 1:
            unique_headers_with_metadata.append({'label': date.strftime('%b %d, %Y'), 'date': date.strftime('%Y-%m-%d'), 'slot': 1})
        else:
            for i in range(1, count + 1):
                unique_headers_with_metadata.append({'label': f"{date.strftime('%b %d')} ({i})", 'date': date.strftime('%Y-%m-%d'), 'slot': i})
    return render_template(
        'class_management/view_attendance.html',
        session=session,
        headers=headers,
        headers_with_meta=unique_headers_with_metadata,
        student_report_data=student_report_data,
        unique_dates=unique_dates_for_modal,
        split_meta=_build_split_context(session, attendance_summary),
        attendance_summary=attendance_summary,
        part_total_classes=part_total_classes,
        is_split_course=False,
        teacher_attendance_data=[]
    )


@class_management_bp.route('/toggle_attendance_record/<int:record_id>', methods=['POST'])
@login_required
def toggle_attendance_record(record_id):
    record = ClassAttendance.query.get_or_404(record_id)
    session = Session.query.get_or_404(record.session_id)
    teacher = _ensure_current_teacher()
    if session.teacher_id != teacher.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    record.is_present = not record.is_present
    db.session.commit()

    attendance_summary = _build_attendance_summary(session)
    student_public_id = record.student.student_id
    student_stats = attendance_summary.get('per_student', {}).get(student_public_id, {'present': 0, 'percentage': 0, 'marks': 0})

    return jsonify({
        'success': True,
        'status': 'P' if record.is_present else 'A',
        'present_count': student_stats.get('present', 0),
        'percentage': f"{student_stats.get('percentage', 0):.2f}%",
        'marks': student_stats.get('marks', 0),
        'student_db_id': record.student_id
    })

@class_management_bp.route('/students/<int:session_id>')
@login_required
def students_list(session_id):
    """View students list for a session"""
    session = Session.query.get_or_404(session_id)
    students = ClassStudent.query.filter_by(session_id=session_id).all()
    
    # Get all batches for filter dropdown
    batches = []
    if Student:
        try:
            all_batches = db.session.query(Student.batch).distinct().filter(Student.batch.isnot(None)).order_by(Student.batch.desc()).all()
            batches = [batch[0] for batch in all_batches]
        except Exception:
            batches = []
    
    return render_template('class_management/students_list.html', 
                         session=session, students=students,
                         split_meta=_build_split_context(session),
                         batches=batches)

@class_management_bp.route('/api/students', methods=['GET'])
@login_required
def get_students_for_selection():
    """Get students from Students Management for selection (AJAX)"""
    try:
        if not Student:
            current_app.logger.warning('Student model not available in get_students_for_selection')
            return jsonify({'success': False, 'message': 'Students Management module not available'}), 503
        
        batch_filter = request.args.get('batch', '').strip()
        search = request.args.get('search', '').strip()
        
        current_app.logger.info(f'Fetching students - batch: {batch_filter}, search: {search}')
        
        query = Student.query
        
        if batch_filter:
            query = query.filter(Student.batch == batch_filter)
        
        if search:
            query = query.filter(
                or_(
                    Student.name.ilike(f'%{search}%'),
                    Student.student_id.ilike(f'%{search}%')
                )
            )
        
        # Increase limit to show more students (or remove limit entirely)
        students = query.order_by(Student.student_id.asc()).limit(500).all()
        
        current_app.logger.info(f'Found {len(students)} students')
        
        return jsonify({
            'success': True,
            'students': [{
                'id': s.id,
                'student_id': s.student_id,
                'name': s.name,
                'batch': s.batch,
                'email': s.email,
                'phone': s.phone
            } for s in students]
        })
    except Exception as e:
        current_app.logger.error(f'Error in get_students_for_selection: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'message': f'Error loading students: {str(e)}'}), 500

@class_management_bp.route('/api/curricula', methods=['GET'])
@login_required
def get_curricula_by_batch():
    """Get curricula applicable to a specific batch (AJAX)"""
    if not Curriculum:
        current_app.logger.error('Curriculum model not available')
        return jsonify({'success': False, 'message': 'Curriculum Management module not available'}), 503
    
    batch = request.args.get('batch', '').strip()
    if not batch:
        return jsonify({'success': False, 'message': 'Batch is required'}), 400
    
    try:
        # Find curricula where the batch is in applicable_batches
        all_curricula = Curriculum.query.all()
        applicable_curricula = []
        
        # Normalize the input batch
        normalized_batch = str(batch).strip()
        current_app.logger.info(f'Searching curricula for batch: {normalized_batch}, Total curricula: {len(all_curricula)}')
        
        for curriculum in all_curricula:
            batches_list = curriculum.get_batches_list()
            current_app.logger.debug(f'Curriculum {curriculum.id} ({curriculum.name}) has batches: {batches_list}')
            
            # Check if the batch matches any batch in the list
            for b in batches_list:
                if str(b).strip() == normalized_batch:
                    applicable_curricula.append({
                        'id': curriculum.id,
                        'name': curriculum.name,
                        'date': curriculum.date
                    })
                    current_app.logger.info(f'Found matching curriculum: {curriculum.name} (ID: {curriculum.id})')
                    break  # Found a match, no need to check other batches for this curriculum
        
        current_app.logger.info(f'Found {len(applicable_curricula)} applicable curricula for batch {normalized_batch}')
        
        return jsonify({
            'success': True,
            'curricula': applicable_curricula,
            'batch_searched': normalized_batch,
            'total_curricula_checked': len(all_curricula),
            'debug': {
                'batch_received': batch,
                'normalized_batch': normalized_batch,
                'applicable_count': len(applicable_curricula)
            }
        })
    except Exception as e:
        current_app.logger.error(f'Error in get_curricula_by_batch: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error fetching curricula: {str(e)}',
            'error': str(e)
        }), 500

@class_management_bp.route('/api/curriculum/<int:curriculum_id>/years-terms', methods=['GET'])
@login_required
def get_years_terms_by_curriculum(curriculum_id):
    """Get distinct (display) years and terms from courses in a curriculum (AJAX)"""
    if not Course:
        return jsonify({'success': False, 'message': 'Course Management module not available'}), 503
    
    Curriculum.query.get_or_404(curriculum_id)
    courses = Course.query.filter_by(curriculum_id=curriculum_id, offered=True).all()  # Only offered courses
    
    years = sorted({c.display_year for c in courses if getattr(c, 'display_year', None)}, key=lambda x: x or '')
    terms = sorted({c.display_term for c in courses if getattr(c, 'display_term', None)}, key=lambda x: x or '')
    
    return jsonify({
        'success': True,
        'years': years,
        'terms': terms
    })

@class_management_bp.route('/api/courses', methods=['GET'])
@login_required
def get_courses_by_filters():
    """Get courses filtered by curriculum, year, and term (AJAX)"""
    if not Course:
        return jsonify({'success': False, 'message': 'Course Management module not available'}), 503
    
    curriculum_id = request.args.get('curriculum_id', type=int)
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()
    
    query = Course.query.filter_by(offered=True)  # Only show offered courses
    if curriculum_id:
        query = query.filter_by(curriculum_id=curriculum_id)
    
    courses = query.order_by(Course.course_name.asc()).all()
    
    if year:
        courses = [c for c in courses if c.display_year == year]
    if term:
        courses = [c for c in courses if c.display_term == term]

    # Filter only Theory courses
    courses = [c for c in courses if (c.course_type or '').lower() == 'theory']
    
    return jsonify({
        'success': True,
        'courses': [{
            'id': c.id,
            'course_code': c.course_code,
            'course_name': c.course_name,
            'year': c.display_year,
            'term': c.display_term,
            'credit': c.credit,
            'course_type': c.course_type,
            'category': c.category
        } for c in courses]
    })

@class_management_bp.route('/api/academic-sessions', methods=['GET'])
@login_required
def get_academic_sessions():
    """Get academic sessions from CurriculumYearTerm based on curriculum, year, and term (AJAX)"""
    if not CurriculumYearTerm:
        return jsonify({'success': False, 'message': 'Course Management module not available'}), 503
    
    curriculum_id = request.args.get('curriculum_id', type=int)
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()
    
    if not curriculum_id or not year or not term:
        return jsonify({
            'success': True,
            'academic_sessions': []
        })
    
    # Fetch academic session from CurriculumYearTerm
    config = CurriculumYearTerm.query.filter_by(
        curriculum_id=curriculum_id,
        year=year,
        term=term
    ).first()
    
    academic_sessions = []
    if config and config.academic_session:
        academic_sessions.append(config.academic_session)
    
    # Also fetch distinct academic sessions from all CurriculumYearTerm for this curriculum/year/term
    # in case there are multiple entries (shouldn't happen due to unique constraint, but for safety)
    all_sessions = db.session.query(CurriculumYearTerm.academic_session).filter_by(
        curriculum_id=curriculum_id,
        year=year,
        term=term
    ).filter(CurriculumYearTerm.academic_session.isnot(None)).distinct().all()
    
    unique_sessions = sorted({s[0] for s in all_sessions if s[0]})
    
    return jsonify({
        'success': True,
        'academic_sessions': unique_sessions
    })

@class_management_bp.route('/add_student/<int:session_id>', methods=['POST'])
@login_required
def add_student(session_id):
    """Add students to a session from Students Management"""
    session = Session.query.get_or_404(session_id)
    teacher = _ensure_current_teacher()
    
    # Handle AJAX request (multiple students)
    if request.is_json:
        if not Student:
            return jsonify({'success': False, 'message': 'Students Management module not available'}), 503
        
        data = request.get_json()
        student_ids = data.get('student_ids', [])
        
        if not student_ids:
            return jsonify({'success': False, 'message': 'No students selected!'}), 400
        
        added_count = 0
        skipped_count = 0
        not_registered_count = 0
        
        # Get existing student IDs in this session
        existing_student_ids = {s.student_id for s in ClassStudent.query.filter_by(session_id=session_id).all()}
        
        for student_id in student_ids:
            # Get student from Students Management
            student = Student.query.get(student_id)
            if not student:
                continue
            
            # Check if already in session
            if student.student_id in existing_student_ids:
                skipped_count += 1
                continue
            
            # Check if student is registered for this course (finalized registration only)
            if StudentCourseRegistration and session.course_code and session.academic_session and session.year and session.term:
                registration = StudentCourseRegistration.query.filter_by(
                    student_id=student.id,
                    course_code=session.course_code,
                    academic_session=session.academic_session,
                    year=session.year,
                    term=session.term,
                    status='finalized'
                ).first()
                
                if not registration:
                    not_registered_count += 1
                    current_app.logger.info(f'Student {student.student_id} ({student.name}) not registered for course {session.course_code}, skipping...')
                    continue
            
            class_student = ClassStudent(
                student_id=student.student_id,
                name=student.name,
                session_id=session.id,
                teacher_id=session.teacher_id or teacher.id
            )
            db.session.add(class_student)
            db.session.flush()  # Flush to get class_student.id before carry on
            
            # Carry on assessment marks if enabled in registration
            _carry_on_assessment_marks(class_student, session)
            
            _replicate_student_to_peers(session, class_student)
            existing_student_ids.add(student.student_id)
            added_count += 1
        
        try:
            db.session.commit()
            message = f'Successfully added {added_count} student(s).'
            if skipped_count > 0:
                message += f' Skipped {skipped_count} existing student(s).'
            if not_registered_count > 0:
                message += f' Skipped {not_registered_count} student(s) not registered for this course.'
            return jsonify({'success': True, 'message': message})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'Error adding students: {str(e)}'}), 500
    
    # Handle form submission (backward compatibility)
    student_id = request.form.get('student_id')
    name = request.form.get('name')
    
    if not student_id or not name:
        flash('Student ID and name are required!', 'error')
        return redirect(url_for('class_management.students_list', session_id=session_id))
    
    # Check if already exists
    existing = ClassStudent.query.filter_by(session_id=session_id, student_id=student_id).first()
    if existing:
        flash('Student already exists in this session!', 'error')
        return redirect(url_for('class_management.students_list', session_id=session_id))
    
    student = ClassStudent(
        student_id=student_id,
        name=name,
        session_id=session.id,
        teacher_id=session.teacher_id or teacher.id
    )
    db.session.add(student)
    db.session.flush()  # Flush to get student.id before carry on
    
    # Carry on assessment marks if enabled in registration
    _carry_on_assessment_marks(student, session)
    
    _replicate_student_to_peers(session, student)
    db.session.commit()
    flash('Student added successfully!', 'success')
    return redirect(url_for('class_management.students_list', session_id=session_id))

@class_management_bp.route('/edit_student/<int:student_id>', methods=['POST'])
@login_required
def edit_student(student_id):
    """Edit a student"""
    student = ClassStudent.query.get_or_404(student_id)
    session = student.session
    old_identifier = student.student_id
    student.student_id = request.form.get('student_id')
    student.name = request.form.get('name')
    _replicate_student_to_peers(session, student, old_identifier=old_identifier)
    db.session.commit()
    flash('Student updated successfully!', 'success')
    return redirect(url_for('class_management.students_list', session_id=student.session_id))

@class_management_bp.route('/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student(student_id):
    """Delete a student"""
    student = ClassStudent.query.get_or_404(student_id)
    session_id = student.session_id
    session = student.session
    student_identifier = student.student_id
    db.session.delete(student)
    _delete_student_from_peers(session, student_identifier)
    db.session.commit()
    flash('Student deleted successfully!', 'success')
    return redirect(url_for('class_management.students_list', session_id=session_id))

@class_management_bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
def delete_session(session_id):
    """Delete a session - using direct database connection to completely bypass SQLAlchemy"""
    import sqlite3
    import os
    
    # Get database path - use the same logic as app.py
    basedir = os.path.abspath(os.path.dirname(__file__))
    # Go up: blueprints/class_management -> blueprints -> root
    root_dir = os.path.abspath(os.path.join(basedir, '..', '..'))
    db_path = os.path.join(root_dir, 'instance', 'academic_management.db')
    
    if not os.path.exists(db_path):
        flash('Database not found.', 'danger')
        return redirect(url_for('class_management.index'))
    
    # CRITICAL: Do NOT load Session object with SQLAlchemy - use raw SQL only
    # Loading it would cause SQLAlchemy to track it and try to update relationships
    
    try:
        # Use direct SQLite connection - completely isolated from SQLAlchemy
        # Use isolation_level=None for autocommit to ensure immediate execution
        conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
        cursor = conn.cursor()
        
        # Disable foreign key checks to avoid any constraint issues
        cursor.execute('PRAGMA foreign_keys = OFF')
        
        # Verify session exists (without loading into SQLAlchemy)
        cursor.execute('SELECT id FROM class_session WHERE id = ?', (session_id,))
        if not cursor.fetchone():
            conn.close()
            flash('Session not found.', 'danger')
            return redirect(url_for('class_management.index'))
        
        # CRITICAL: Delete course_outline FIRST using raw SQL
        # This must happen before SQLAlchemy can interfere
        cursor.execute('DELETE FROM course_outline WHERE session_id = ?', (session_id,))
        deleted_count = cursor.rowcount
        current_app.logger.info(f'Deleted {deleted_count} course_outline records for session {session_id}')
        
        # Delete other related records
        cursor.execute('DELETE FROM class_attendance WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM class_student WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM course_review WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM evaluation_invite WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM evaluation_submission WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM student_feedback_link WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM class_split_invite WHERE inviter_session_id = ?', (session_id,))
        
        # Finally delete the session itself
        cursor.execute('DELETE FROM class_session WHERE id = ?', (session_id,))
        
        # Re-enable foreign keys
        cursor.execute('PRAGMA foreign_keys = ON')
        
        conn.close()
        
        # Clear SQLAlchemy session to remove any stale objects
        try:
            db.session.rollback()
            db.session.expunge_all()
        except:
            pass
        
        flash('Session deleted successfully!', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting session {session_id}: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        flash(f'Error deleting session: {str(e)}', 'danger')
    
    return redirect(url_for('class_management.index'))

@class_management_bp.route('/course_file/<int:session_id>')
@login_required
def course_file(session_id):
    """Course file management page"""
    session = Session.query.get_or_404(session_id)
    
    # Get or create course outline
    course_outline = None
    try:
        course_outline = CourseOutline.query.filter_by(session_id=session_id).first()
        if not course_outline:
            teacher = Teacher.query.filter_by(name=current_user.full_name).first()
            if teacher:
                # Ensure all columns exist before creating
                try:
                    db.create_all()
                except Exception as e:
                    current_app.logger.warning(f"Could not create all tables/columns: {e}")
                
                course_outline = CourseOutline(session_id=session_id, teacher_id=teacher.id)
                db.session.add(course_outline)
                db.session.commit()
    except Exception as e:
        # If table doesn't exist, create it
        current_app.logger.warning(f"CourseOutline table might not exist: {e}")
        try:
            db.create_all()
            # Try again after creating tables
            teacher = Teacher.query.filter_by(name=current_user.full_name).first()
            if teacher:
                course_outline = CourseOutline(session_id=session_id, teacher_id=teacher.id)
                db.session.add(course_outline)
                db.session.commit()
        except Exception as e2:
            current_app.logger.error(f"Error creating CourseOutline: {e2}")
            flash('Course outline feature is not available. Please ensure database migration is complete.', 'warning')
    
    # Get course data from curriculum if available
    course_data = None
    try:
        if Course:
            course_data = Course.query.filter_by(course_code=session.course_code).first()
    except:
        pass
    
    return render_template('class_management/course_file.html', 
                         session=session, 
                         course_outline=course_outline,
                         course_data=course_data)

@class_management_bp.route('/course_file/<int:session_id>/save', methods=['POST'])
@login_required
def save_course_outline(session_id):
    """Save course outline data"""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    
    if not teacher or teacher.id != session.teacher_id:
        flash('You are not authorized to edit this course outline.', 'danger')
        return redirect(url_for('class_management.course_file', session_id=session_id))
    
    course_outline = CourseOutline.query.filter_by(session_id=session_id).first()
    if not course_outline:
        course_outline = CourseOutline(session_id=session_id, teacher_id=teacher.id)
        db.session.add(course_outline)
    
    # Ensure all columns exist (for database migrations)
    try:
        db.create_all()  # This will add missing columns if database supports it
    except Exception as e:
        current_app.logger.warning(f"Could not create all tables/columns: {e}")
    
    # Save all form data as JSON
    data = request.get_json() if request.is_json else request.form.to_dict()
    
    if 'course_objectives' in data:
        course_outline.course_objectives = json.dumps(data.get('course_objectives', [])) if isinstance(data.get('course_objectives'), list) else data.get('course_objectives')
    if 'course_summary' in data:
        course_outline.course_summary = data.get('course_summary')
    if 'prerequisites' in data:
        course_outline.prerequisites = data.get('prerequisites')
    if 'contact_hours' in data:
        course_outline.contact_hours = data.get('contact_hours')
    if 'cie_marks' in data:
        course_outline.cie_marks = data.get('cie_marks')
    if 'smee_marks' in data:
        course_outline.smee_marks = data.get('smee_marks')
    # Try to set new fields, but handle if columns don't exist yet
    try:
        if 'course_content_summary' in data:
            course_outline.course_content_summary = data.get('course_content_summary')
        if 'clo_plo_mapping' in data:
            course_outline.clo_plo_mapping = data.get('clo_plo_mapping')
        if 'evaluation_policy' in data:
            course_outline.evaluation_policy = json.dumps(data.get('evaluation_policy', {})) if isinstance(data.get('evaluation_policy'), dict) else data.get('evaluation_policy')
        if 'cie_breakdown' in data:
            course_outline.cie_breakdown = json.dumps(data.get('cie_breakdown', {})) if isinstance(data.get('cie_breakdown'), dict) else data.get('cie_breakdown')
        if 'smee_breakdown' in data:
            course_outline.smee_breakdown = json.dumps(data.get('smee_breakdown', {})) if isinstance(data.get('smee_breakdown'), dict) else data.get('smee_breakdown')
    except AttributeError:
        # Columns don't exist yet - will be added by migration
        current_app.logger.warning("Some course_outline columns don't exist yet. Please run migration.")
    if 'lesson_plan' in data:
        course_outline.lesson_plan = json.dumps(data.get('lesson_plan', [])) if isinstance(data.get('lesson_plan'), list) else data.get('lesson_plan')
    if 'assessment_strategy' in data:
        course_outline.assessment_strategy = json.dumps(data.get('assessment_strategy', {})) if isinstance(data.get('assessment_strategy'), dict) else data.get('assessment_strategy')
    if 'assessment_techniques' in data:
        course_outline.assessment_techniques = json.dumps(data.get('assessment_techniques', [])) if isinstance(data.get('assessment_techniques'), list) else data.get('assessment_techniques')
    if 'rubrics' in data:
        course_outline.rubrics = json.dumps(data.get('rubrics', [])) if isinstance(data.get('rubrics'), list) else data.get('rubrics')
    if 'grading_policy' in data:
        course_outline.grading_policy = json.dumps(data.get('grading_policy', [])) if isinstance(data.get('grading_policy'), list) else data.get('grading_policy')
    if 'textbooks' in data:
        course_outline.textbooks = json.dumps(data.get('textbooks', [])) if isinstance(data.get('textbooks'), list) else data.get('textbooks')
    if 'reference_books' in data:
        course_outline.reference_books = json.dumps(data.get('reference_books', [])) if isinstance(data.get('reference_books'), list) else data.get('reference_books')
    if 'other_resources' in data:
        course_outline.other_resources = json.dumps(data.get('other_resources', [])) if isinstance(data.get('other_resources'), list) else data.get('other_resources')
    try:
        if 'course_file_components' in data:
            course_outline.course_file_components = json.dumps(data.get('course_file_components', [])) if isinstance(data.get('course_file_components'), list) else data.get('course_file_components')
    except AttributeError:
        current_app.logger.warning("course_file_components column doesn't exist yet.")
    if 'make_up_procedures' in data:
        course_outline.make_up_procedures = data.get('make_up_procedures')
    if 'other_issues' in data:
        course_outline.other_issues = json.dumps(data.get('other_issues', {})) if isinstance(data.get('other_issues'), dict) else data.get('other_issues')
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True, 'message': 'Course outline saved successfully!'})
    flash('Course outline saved successfully!', 'success')
    return redirect(url_for('class_management.course_file', session_id=session_id))

@class_management_bp.route('/course_file/<int:session_id>/outline/generate-ai', methods=['POST'])
@login_required
def generate_weekly_plan_ai(session_id):
    """Generate weekly plan using AI"""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    
    if not teacher or teacher.id != session.teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    course_name = data.get('course_name', '')
    course_code = data.get('course_code', '')
    course_summary = data.get('course_summary', '')
    course_objectives = data.get('course_objectives', [])
    contact_hours = int(data.get('contact_hours', 56))
    
    # Simple AI-based weekly plan generation
    # This is a basic implementation - you can integrate with OpenAI API, etc.
    try:
        # Calculate number of weeks (assuming 3-4 hours per week)
        weeks_needed = max(12, contact_hours // 3)  # Minimum 12 weeks
        
        lesson_plan = []
        
        # Generate weekly plan based on course content
        if course_data := Course.query.filter_by(course_code=session.course_code).first():
            # Use course content from syllabus
            content_a = course_data.content_section_a or ''
            content_b = course_data.content_section_b or ''
            clos = course_data.get_clos_list()
            
            # Split content into topics
            topics_a = [line.strip() for line in content_a.split('\n') if line.strip() and not line.strip().startswith('#')]
            topics_b = [line.strip() for line in content_b.split('\n') if line.strip() and not line.strip().startswith('#')]
            all_topics = topics_a + topics_b
            
            # Distribute topics across weeks
            topics_per_week = max(1, len(all_topics) // weeks_needed) if all_topics else 1
            
            for week_num in range(1, weeks_needed + 1):
                week_topics = all_topics[(week_num-1)*topics_per_week:week_num*topics_per_week] if all_topics else [f'Week {week_num} Topic']
                
                lesson_plan.append({
                    'week': f'Week {week_num}',
                    'date': '',  # User can fill this
                    'topic': ', '.join(week_topics) if week_topics else f'Topic {week_num}',
                    'outcome': f'Students will understand {week_topics[0] if week_topics else "the topic"}' if week_topics else '',
                    'teaching_assessment': 'Lecture, Discussion, Q&A',
                    'clo_alignment': ', '.join([str(i+1) for i in range(min(3, len(clos)))]) if clos else '1'
                })
        else:
            # Generate generic plan
            for week_num in range(1, weeks_needed + 1):
                lesson_plan.append({
                    'week': f'Week {week_num}',
                    'date': '',
                    'topic': f'Topic {week_num}: {course_name or "Course Content"}' if week_num == 1 else f'Topic {week_num}',
                    'outcome': f'Students will be able to understand and apply concepts from week {week_num}',
                    'teaching_assessment': 'Lecture, Discussion, Practice',
                    'clo_alignment': '1, 2'
                })
        
        return jsonify({
            'success': True,
            'lesson_plan': lesson_plan,
            'message': f'Generated {len(lesson_plan)} weeks of lesson plan'
        })
    except Exception as e:
        current_app.logger.error(f"Error generating AI plan: {e}")
        return jsonify({
            'success': False,
            'message': f'Error generating plan: {str(e)}'
        }), 500

@class_management_bp.route('/course_file/<int:session_id>/outline/edit')
@login_required
def edit_course_outline(session_id):
    """Edit course outline page"""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    
    if not teacher or teacher.id != session.teacher_id:
        flash('You are not authorized to edit this course outline.', 'danger')
        return redirect(url_for('class_management.course_file', session_id=session_id))
    
    course_outline = CourseOutline.query.filter_by(session_id=session_id).first()
    if not course_outline:
        course_outline = CourseOutline(session_id=session_id, teacher_id=teacher.id)
        db.session.add(course_outline)
        db.session.commit()
    
    # Get course data from curriculum
    course_data = None
    try:
        if Course:
            course_data = Course.query.filter_by(course_code=session.course_code).first()
    except:
        pass
    
    # Parse JSON fields
    outline_data = {
        'course_objectives': json.loads(course_outline.course_objectives) if course_outline.course_objectives else [],
        'course_content_summary': course_outline.course_content_summary or '',
        'clo_plo_mapping': course_outline.clo_plo_mapping or '',
        'lesson_plan': json.loads(course_outline.lesson_plan) if course_outline.lesson_plan else [],
        'assessment_strategy': json.loads(course_outline.assessment_strategy) if course_outline.assessment_strategy else {},
        'assessment_techniques': json.loads(course_outline.assessment_techniques) if course_outline.assessment_techniques else [],
        'rubrics': json.loads(course_outline.rubrics) if course_outline.rubrics else [],
        'grading_policy': json.loads(course_outline.grading_policy) if course_outline.grading_policy else [],
        'textbooks': json.loads(course_outline.textbooks) if course_outline.textbooks else [],
        'reference_books': json.loads(course_outline.reference_books) if course_outline.reference_books else [],
        'other_resources': json.loads(course_outline.other_resources) if course_outline.other_resources else [],
        'course_file_components': json.loads(course_outline.course_file_components) if course_outline.course_file_components else [],
        'other_issues': json.loads(course_outline.other_issues) if course_outline.other_issues else {},
    }
    
    return render_template('class_management/edit_course_outline.html',
                         session=session,
                         course_outline=course_outline,
                         course_data=course_data,
                         outline_data=outline_data)

def _generate_course_outline_docx(session_id):
    """Generate course outline as DOCX document"""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    
    if not teacher or teacher.id != session.teacher_id:
        flash('You are not authorized to download this course outline.', 'danger')
        return redirect(url_for('class_management.course_file', session_id=session_id))
    
    course_outline = CourseOutline.query.filter_by(session_id=session_id).first()
    if not course_outline:
        flash('Course outline not found. Please create it first.', 'warning')
        return redirect(url_for('class_management.course_file', session_id=session_id))
    
    # Get course data
    course_data = None
    try:
        if Course:
            course_data = Course.query.filter_by(course_code=session.course_code).first()
    except:
        pass
    
    # Parse JSON fields
    course_objectives = json.loads(course_outline.course_objectives) if course_outline.course_objectives else []
    lesson_plan = json.loads(course_outline.lesson_plan) if course_outline.lesson_plan else []
    textbooks = json.loads(course_outline.textbooks) if course_outline.textbooks else []
    reference_books = json.loads(course_outline.reference_books) if course_outline.reference_books else []
    other_resources = json.loads(course_outline.other_resources) if course_outline.other_resources else []
    
    # Lazy import docx to prevent startup hang
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    # Create DOCX document
    doc = Document()
    
    # Cover Page
    cover_para = doc.add_paragraph()
    cover_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cover_para.add_run('Course Outline')
    run.font.size = Pt(18)
    run.font.bold = True
    
    if session.course_code:
        code_para = doc.add_paragraph()
        code_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = code_para.add_run(session.course_code + ':')
        run.font.size = Pt(16)
        run.font.bold = True
    
    if session.course_name:
        name_para = doc.add_paragraph()
        name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = name_para.add_run(session.course_name.upper())
        run.font.size = Pt(20)
        run.font.bold = True
    
    doc.add_page_break()
    
    # Part A: Introduction
    doc.add_heading('PART A: INTRODUCTION', level=1)
    
    # Course Identification Table
    info_table = doc.add_table(rows=1, cols=2)
    info_table.style = 'Table Grid'
    info_table.cell(0, 0).text = 'Course No:'
    info_table.cell(0, 1).text = session.course_code or '—'
    # Add more rows...
    
    # Course Objectives
    if course_objectives:
        doc.add_heading('Course Objectives', level=2)
        for obj in course_objectives:
            doc.add_paragraph(obj, style='List Bullet')
    
    # Course Summary
    if course_outline.course_summary:
        doc.add_heading('Course Summary', level=2)
        doc.add_paragraph(course_outline.course_summary)
    
    # Lesson Plan
    if lesson_plan:
        doc.add_page_break()
        doc.add_heading('Class Schedule/Lesson Plan/Weekly plan', level=1)
        lesson_table = doc.add_table(rows=1, cols=7)
        lesson_table.style = 'Table Grid'
        headers = ['Week', 'Date', 'Topic', 'Specific Outcome', 'Suggested Activities', 'Teaching and Assessment', 'Alignment with CLO']
        for i, header in enumerate(headers):
            lesson_table.cell(0, i).text = header
            lesson_table.cell(0, i).paragraphs[0].runs[0].font.bold = True
        
        for lesson in lesson_plan:
            row = lesson_table.add_row().cells
            row[0].text = lesson.get('week', '')
            row[1].text = lesson.get('date', '')
            row[2].text = lesson.get('topic', '')
            row[3].text = lesson.get('outcome', '')
            row[4].text = lesson.get('activities', '')
            row[5].text = lesson.get('teaching_assessment', '')
            row[6].text = lesson.get('clo_alignment', '')
    
    # Learning Resources
    if textbooks or reference_books or other_resources:
        doc.add_page_break()
        doc.add_heading('PART D: LEARNING RESOURCES', level=1)
        
        if textbooks:
            doc.add_heading('Textbooks', level=2)
            for book in textbooks:
                doc.add_paragraph(book, style='List Bullet')
        
        if reference_books:
            doc.add_heading('Reference Books', level=2)
            for book in reference_books:
                doc.add_paragraph(book, style='List Bullet')
        
        if other_resources:
            doc.add_heading('Other Resources', level=2)
            for resource in other_resources:
                doc.add_paragraph(resource, style='List Bullet')
    
    # Save to buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_data = buffer.getvalue()
    buffer.close()
    
    filename = f"course_outline_{session.course_code or 'course'}.docx"
    return Response(
        docx_data,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(docx_data)),
        },
    )

def _generate_course_outline_pdf(session_id):
    """Generate course outline as PDF document"""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    
    if not teacher or teacher.id != session.teacher_id:
        flash('You are not authorized to download this course outline.', 'danger')
        return redirect(url_for('class_management.course_file', session_id=session_id))
    
    course_outline = CourseOutline.query.filter_by(session_id=session_id).first()
    if not course_outline:
        flash('Course outline not found. Please create it first.', 'warning')
        return redirect(url_for('class_management.course_file', session_id=session_id))
    
    # Parse JSON fields
    course_objectives = json.loads(course_outline.course_objectives) if course_outline.course_objectives else []
    lesson_plan = json.loads(course_outline.lesson_plan) if course_outline.lesson_plan else []
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=18, spaceAfter=12)
    story.append(Paragraph('Course Outline', title_style))
    story.append(Spacer(1, 0.2*inch))
    
    if session.course_code:
        code_style = ParagraphStyle('Code', parent=styles['Normal'], alignment=TA_CENTER, fontSize=14, spaceAfter=6)
        story.append(Paragraph(f"{session.course_code}:", code_style))
    
    if session.course_name:
        name_style = ParagraphStyle('Name', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=16, spaceAfter=12)
        story.append(Paragraph(session.course_name.upper(), name_style))
    
    story.append(PageBreak())
    
    # Part A
    story.append(Paragraph('PART A: INTRODUCTION', styles['Heading1']))
    story.append(Spacer(1, 0.1*inch))
    
    if course_objectives:
        story.append(Paragraph('Course Objectives', styles['Heading2']))
        for obj in course_objectives:
            story.append(Paragraph(f"• {obj}", styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
    
    # Lesson Plan Table
    if lesson_plan:
        story.append(PageBreak())
        story.append(Paragraph('Class Schedule/Lesson Plan/Weekly plan', styles['Heading1']))
        story.append(Spacer(1, 0.1*inch))
        
        table_data = [['Week', 'Date', 'Topic', 'Specific Outcome', 'Teaching & Assessment', 'CLO']]
        for lesson in lesson_plan:
            table_data.append([
                lesson.get('week', ''),
                lesson.get('date', ''),
                lesson.get('topic', ''),
                lesson.get('outcome', ''),
                lesson.get('teaching_assessment', ''),
                lesson.get('clo_alignment', '')
            ])
        
        lesson_table = Table(table_data, colWidths=[0.8*inch, 1.2*inch, 1.5*inch, 1.8*inch, 1.5*inch, 0.7*inch])
        lesson_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(lesson_table)
    
    doc.build(story)
    buffer.seek(0)
    pdf_data = buffer.getvalue()
    buffer.close()
    
    filename = f"course_outline_{session.course_code or 'course'}.pdf"
    return Response(
        pdf_data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(pdf_data)),
        },
    )

@class_management_bp.route('/course_file/<int:session_id>/outline/download/docx')
@login_required
def download_course_outline_docx(session_id):
    """Download course outline as DOCX"""
    return _generate_course_outline_docx(session_id)

@class_management_bp.route('/course_file/<int:session_id>/outline/download/pdf')
@login_required
def download_course_outline_pdf(session_id):
    """Download course outline as PDF"""
    return _generate_course_outline_pdf(session_id)

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

@class_management_bp.route('/edit_session/<int:session_id>', methods=['GET', 'POST'])
@login_required
def edit_session(session_id):
    """Edit a session"""
    session = Session.query.get_or_404(session_id)
    
    if request.method == 'POST':
        try:
            session.year = request.form.get('year')
            session.term = request.form.get('term')
            session.academic_session = request.form.get('academic_session')
            session.course_code = request.form.get('course_code')
            session.course_name = request.form.get('course_name')
            session.course_type = request.form.get('course_type', 'theory')
            session.category = request.form.get('category', 'ug')
            
            if not session.year or not session.term:
                flash('Year and term are required!', 'error')
                return redirect(url_for('class_management.edit_session', session_id=session_id))
            
            db.session.commit()
            flash('Session updated successfully!', 'success')
            return redirect(url_for('class_management.index'))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating session {session_id}: {e}")
            flash(f'Error updating session: {str(e)}', 'error')
            return redirect(url_for('class_management.edit_session', session_id=session_id))
    
    return render_template('class_management/edit_session.html', session=session)

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
    
    # Build assignment map for template to access batch and academic_session from CourseSessionAssignment
    assignment_map = {}
    if CourseSessionAssignment and Course:
        try:
            for session in archived_sessions:
                # Try to find assignment by session_id first
                assignment = CourseSessionAssignment.query.filter_by(session_id=session.id).first()
                
                # If not found by session_id, try to find by course_code, teacher_id, year, term
                if not assignment and session.course_code and session.teacher_id and session.year and session.term:
                    try:
                        # Try to match by course_code, teacher_id, year, term
                        assignment = CourseSessionAssignment.query.filter_by(
                            teacher_id=session.teacher_id,
                            year=session.year,
                            term=session.term
                        ).join(Course, CourseSessionAssignment.course_id == Course.id).filter(
                            Course.course_code == session.course_code
                        ).first()
                        
                        # If not found, try without section matching (for full course sessions)
                        if not assignment:
                            assignment = CourseSessionAssignment.query.filter_by(
                                teacher_id=session.teacher_id,
                                year=session.year,
                                term=session.term
                            ).join(Course, CourseSessionAssignment.course_id == Course.id).filter(
                                Course.course_code == session.course_code
                            ).filter(
                                or_(
                                    CourseSessionAssignment.section.is_(None),
                                    CourseSessionAssignment.section == ''
                                )
                            ).first()
                    except Exception as query_error:
                        current_app.logger.warning(f'Error querying assignment for archived session {session.id}: {query_error}')
                
                if assignment:
                    # If assignment doesn't have batch/academic_session, try to get from curriculum year-term config
                    batch = assignment.batch
                    academic_session = assignment.academic_session
                    
                    if Curriculum and CurriculumYearTerm and (not batch or not academic_session):
                        try:
                            if assignment.curriculum_id:
                                curriculum = Curriculum.query.get(assignment.curriculum_id)
                                if curriculum:
                                    year_term_config = curriculum.get_year_term_config(assignment.year, assignment.term)
                                    if year_term_config:
                                        if not batch and year_term_config.batch and year_term_config.batch != 'None':
                                            batch = year_term_config.batch
                                        if not academic_session and year_term_config.academic_session:
                                            academic_session = year_term_config.academic_session
                        except Exception as config_error:
                            current_app.logger.warning(f'Error getting year-term config for assignment {assignment.id}: {config_error}')
                    
                    assignment_map[session.id] = {
                        'batch': batch or '',
                        'academic_session': academic_session or ''
                    }
        except Exception as e:
            current_app.logger.error(f'Error building assignment map for archived sessions: {str(e)}', exc_info=True)
    
    return render_template('class_management/archive.html', 
                         sessions=archived_sessions, 
                         assignment_map=assignment_map if assignment_map else {})

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
    try:
        # Import error handler for detailed logging
        from error_handler import log_error
        
        current_app.logger.info(f"Starting Excel generation for session {session_id}")
        
        # Check if required modules are available
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            current_app.logger.info("Required modules available for Excel")
        except ImportError as e:
            current_app.logger.error(f"Missing required module for Excel: {e}")
            flash(f'Missing required module for Excel: {e}', 'error')
            return redirect(url_for('class_management.index'))
            
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
        attendance_summary = _build_attendance_summary(session)
        combined_assessment_map = _collect_combined_assessment_marks(session)
        attendance_summary = _build_attendance_summary(session)
        combined_assessment_map = _collect_combined_assessment_marks(session)
        attendance_summary = _build_attendance_summary(session)
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

        # Prepare structured data for Excel
        local_classes_held = sum(daily_class_counts.values())
        data_rows = []

        agg_student_map = attendance_summary.get('per_student', {})
        agg_total_classes = attendance_summary.get('total_classes', local_classes_held)

        for index, student in enumerate(students, start=1):
            student_attendance_records = [r for r in all_attendance_records if r.student_id == student.id]
            agg_stats = agg_student_map.get(student.student_id, {'present': 0, 'percentage': 0, 'marks': 0})
            present_count = agg_stats['present']
            percentage = agg_stats['percentage']
            marks = agg_stats['marks']
            
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

            data_rows.append({
                'serial': index,
                'student_id': student.student_id,
                'name': student.name,
                'attendance': attendance_statuses,
                'total_classes': agg_total_classes,
                'present': present_count,
                'percentage': percentage,
                'marks': marks
            })

        # Create workbook with styled layout
        wb = Workbook()
        ws = wb.active
        ws.title = 'Attendance Report'

        total_columns = 3 + len(headers) + 4  # SL + ID + Name + attendance + summary columns
        last_column_letter = get_column_letter(total_columns)

        # Title row
        ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=total_columns)
        title_cell = ws.cell(row=1, column=2)
        title_cell.value = 'Attendance Sheet'
        title_cell.font = Font(size=16, bold=True)
        title_cell.alignment = Alignment(horizontal='center', vertical='center')

        # Subject information
        subject_text = 'Subject: '
        if session.course_code and session.course_name:
            subject_text += f"{session.course_code} {session.course_name}"
        elif session.course_name:
            subject_text += session.course_name
        elif session.course_code:
            subject_text += session.course_code
        else:
            subject_text += 'N/A'

        ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=total_columns)
        subject_cell = ws.cell(row=2, column=2)
        subject_cell.value = subject_text
        subject_cell.font = Font(bold=True)
        subject_cell.alignment = Alignment(horizontal='left', vertical='center')

        # Additional metadata row
        teacher_name = None
        if session.teacher and getattr(session.teacher, 'name', None):
            teacher_name = session.teacher.name
        else:
            teacher_name = getattr(current_user, 'full_name', None) or getattr(current_user, 'username', 'N/A')

        metadata_items = [
            f"Year: {session.year or 'N/A'}",
            f"Term: {session.term or 'N/A'}",
            f"Session: {session.academic_session or 'N/A'}",
            f"Course Teacher: {teacher_name}"
        ]

        metadata_start_col = 2
        for item in metadata_items:
            if metadata_start_col > total_columns:
                break
            cell = ws.cell(row=3, column=metadata_start_col)
            cell.value = item
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='left', vertical='center')
            metadata_start_col += 4

        # Header row for table
        header_row = 5
        headers_for_sheet = ['Sl', 'Student ID', 'Name'] + headers + ['Total Classes', 'Present', 'Percentage', 'Marks']

        header_fill = PatternFill(start_color='D8E4BC', end_color='D8E4BC', fill_type='solid')
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        for col_index, header_label in enumerate(headers_for_sheet, start=1):
            cell = ws.cell(row=header_row, column=col_index)
            cell.value = header_label
            cell.font = Font(bold=True)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=False, text_rotation=90, shrink_to_fit=False)
            cell.border = thin_border

        # Data rows
        data_start_row = header_row + 1
        attendance_start_col = 4
        percentage_col = attendance_start_col + len(headers) + 2  # Serial(1) + ID(2) + Name(3) + attendance + Total + Present => +2, Percentage column index
        marks_col = percentage_col + 1

        for row_offset, row_data in enumerate(data_rows):
            row_number = data_start_row + row_offset
            ws.cell(row=row_number, column=1, value=row_data['serial']).alignment = Alignment(horizontal='center')
            ws.cell(row=row_number, column=2, value=row_data['student_id']).alignment = Alignment(horizontal='center')
            ws.cell(row=row_number, column=3, value=row_data['name']).alignment = Alignment(horizontal='left')

            for idx, status in enumerate(row_data['attendance']):
                cell = ws.cell(row=row_number, column=attendance_start_col + idx, value=status)
                cell.alignment = Alignment(horizontal='center', vertical='center')

            total_col = attendance_start_col + len(headers)
            ws.cell(row=row_number, column=total_col, value=row_data['total_classes']).alignment = Alignment(horizontal='center')
            ws.cell(row=row_number, column=total_col + 1, value=row_data['present']).alignment = Alignment(horizontal='center')

            percentage_cell = ws.cell(row=row_number, column=percentage_col, value=(row_data['percentage'] / 100 if agg_total_classes else 0))
            percentage_cell.number_format = '0.00%'
            percentage_cell.alignment = Alignment(horizontal='center')

            ws.cell(row=row_number, column=marks_col, value=row_data['marks']).alignment = Alignment(horizontal='center')

        # Apply borders to data cells
        max_row = max(header_row, data_start_row + len(data_rows) - 1)
        for row in ws.iter_rows(min_row=header_row, max_row=max_row, min_col=1, max_col=total_columns):
            for cell in row:
                cell.border = thin_border

        # Auto fit all columns based on content - exact fit without extra space
        for col_idx in range(1, total_columns + 1):
            column_letter = get_column_letter(col_idx)
            max_length = 0
            
            # Check all cells in this column to find maximum content length
            for row in ws.iter_rows(min_col=col_idx, max_col=col_idx, values_only=False):
                for cell in row:
                    if cell.value is not None:
                        # Calculate exact length of cell content
                        cell_value = str(cell.value)
                        # Count actual character length
                        actual_length = len(cell_value)
                        max_length = max(max_length, actual_length)
            
            # Set column width to exact content width with minimal padding
            # openpyxl column width is in character units (approximate)
            if max_length > 0:
                # Very minimal padding: 0.5-1 character for readability
                # For narrow columns (like attendance P/A), use less padding
                if max_length <= 2:  # Single character columns (P, A, -)
                    adjusted_width = max_length + 0.5
                else:
                    adjusted_width = max_length + 1.0
            else:
                # If column is completely empty, set minimal width
                adjusted_width = 2
            
            ws.column_dimensions[column_letter].width = adjusted_width

        ws.freeze_panes = ws.cell(row=data_start_row, column=attendance_start_col)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        current_app.logger.info(f"Excel generated successfully for session {session_id}")
        
        # Use Response instead of send_file for better cPanel compatibility
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="attendance_report_{session.course_name}_{date.today()}.xlsx"',
                'Content-Length': str(len(output.getvalue()))
            }
        )
        
    except Exception as e:
        # Log detailed error information
        log_error(e, {
            'session_id': session_id,
            'function': 'download_attendance_excel',
            'user': current_user.username if current_user.is_authenticated else 'Anonymous'
        })
        
        current_app.logger.error(f"Error generating Excel for session {session_id}: {e}")
        flash(f'Error generating Excel: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))

@class_management_bp.route('/download_pdf_report/<int:session_id>')
@login_required
def download_pdf_report(session_id):
    """Generate and download a PDF summary report with headers and page numbers."""
    try:
        # Import error handler for detailed logging
        from error_handler import log_error
        from flask import Response
        
        current_app.logger.info(f"Starting PDF generation for session {session_id}")
        
        # Check if required modules are available
        try:
            import reportlab
            import pandas
            current_app.logger.info("Required modules available")
        except ImportError as e:
            current_app.logger.error(f"Missing required module: {e}")
            flash(f'Missing required module: {e}', 'error')
            return redirect(url_for('class_management.index'))
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
        combined_values, combined_best3, combined_pg_avg, combined_pg_total = _build_combined_assessment_values(session)
        attendance_summary = _build_attendance_summary(session)
        combined_assessment_map = _collect_combined_assessment_marks(session)

        buffer = io.BytesIO()
        
        # Define margins
        top_margin = 2.5 * inch
        bottom_margin = 0.7 * inch
        
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=0.5*inch, leftMargin=0.5*inch,
                                topMargin=top_margin, bottomMargin=bottom_margin)
        
        elements = []
        
        # --- Data Calculation ---
        student_data_for_pdf = []
        per_student_attendance = attendance_summary.get('per_student', {})
        for student in students:
            attendance_stats = per_student_attendance.get(student.student_id, {'marks': 0})
            attendance_marks = attendance_stats.get('marks', 0)

            if session.course_type == 'sessional':
                # For sessional courses, keep report and viva separate
                sessional_report = int(round(student.sessional_report or 0))
                sessional_viva = int(round(student.sessional_viva or 0))
                student_data_for_pdf.append({
                    'id': student.student_id,
                    'attendance': attendance_marks,
                    'sessional_report': sessional_report,
                    'sessional_viva': sessional_viva
                })
            else:
                # For theory courses, use combined assessment
                assessment_marks_display = 0
                if session.course_type == 'theory':
                    if session.category == 'pg':
                        assessment_marks_display = combined_pg_total.get(student.student_id) or 0  # Already rounded
                    else:
                        # UG: Keep fraction in assessment page, but round for result generation
                        ug_total = combined_best3.get(student.student_id) or 0
                        assessment_marks_display = int(round(ug_total)) if ug_total else 0  # Round for result generation

                student_data_for_pdf.append({
                    'id': student.student_id,
                    'attendance': attendance_marks,
                    'assessment': assessment_marks_display
                })

        # --- Table Creation ---
        if session.course_type == 'sessional':
            # For sessional courses: separate columns for Report and Viva
            table_data = [['ID', 'Attendance (10)', 'Sessional Report (60)', 'Sessional Viva (30)']]
            for s_data in student_data_for_pdf:
                table_data.append([
                    s_data['id'], 
                    s_data['attendance'], 
                    s_data['sessional_report'],
                    s_data['sessional_viva']
                ])
            table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 2*inch, 2*inch], repeatRows=0)
        else:
            # For theory courses: single assessment column
            assessment_header_text = "Continuous Assessment (30)"
            if session.course_type == 'theory' and session.category == 'pg':
                assessment_header_text = "Continuous Assessment (40)"
            
            table_data = [['ID', 'Attendance (10)', assessment_header_text]]
            for s_data in student_data_for_pdf:
                table_data.append([s_data['id'], s_data['attendance'], s_data['assessment']])
            table = Table(table_data, colWidths=[2*inch, 2*inch, 2.5*inch], repeatRows=0)
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
        
        # --- PDF Build with header/footer ---
        def _draw_header_footer(canvas_obj, doc_obj, include_header=False):
            canvas_obj.saveState()
            width, height = doc_obj.pagesize
            if include_header:
                canvas_obj.setFont('Helvetica-Bold', 18)
                canvas_obj.drawCentredString(width / 2.0, height - 1.0 * inch, "Khulna University")

                canvas_obj.setFont('Helvetica', 12)
                canvas_obj.drawCentredString(width / 2.0, height - 1.35 * inch, "Law Discipline")
                canvas_obj.drawCentredString(width / 2.0, height - 1.60 * inch, "Continuous Assessment and Attendance Marks")

                canvas_obj.setFont('Helvetica-Bold', 10)
                course_info = f"Course: {session.course_name} ({session.course_code or 'N/A'})  |  Type: {session.course_type.capitalize()}"
                year_term_info = f"Year: {session.year}, Term: {session.term}  |  Session: {session.academic_session}"
                canvas_obj.drawCentredString(width / 2.0, height - 1.95 * inch, course_info)
                canvas_obj.drawCentredString(width / 2.0, height - 2.15 * inch, year_term_info)

            canvas_obj.setFont('Helvetica', 9)
            page_text = f"Page {doc_obj.page}"
            canvas_obj.drawRightString(width - 0.5 * inch, 0.5 * inch, page_text)
            canvas_obj.restoreState()

        def first_page(canvas_obj, doc_obj):
            _draw_header_footer(canvas_obj, doc_obj, include_header=True)

        def later_pages(canvas_obj, doc_obj):
            _draw_header_footer(canvas_obj, doc_obj, include_header=False)

        doc.build(elements, onFirstPage=first_page, onLaterPages=later_pages)
        
        buffer.seek(0)
        filename = f"Report_{session.course_name}_{session.year}.pdf"
        
        current_app.logger.info(f"PDF generated successfully for session {session_id}")
        
        # Use Response instead of send_file for better cPanel compatibility
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(buffer.getvalue()))
            }
        )
    except Exception as e:
        # Log detailed error information
        log_error(e, {
            'session_id': session_id,
            'function': 'download_pdf_report',
            'user': current_user.username if current_user.is_authenticated else 'Anonymous'
        })
        
        current_app.logger.error(f"Error generating PDF for session {session_id}: {e}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))


@class_management_bp.route('/download_attendance_sheet/<int:session_id>')
@login_required
def download_attendance_sheet(session_id):
    try:
        from error_handler import log_error
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        session = Session.query.get_or_404(session_id)
        attendance_summary = _build_attendance_summary(session)

        related_sessions = _get_related_sessions(session, include_archived=True)
        session_ids = [s.id for s in related_sessions if s]
        attendance_records = ClassAttendance.query.filter(
            ClassAttendance.session_id.in_(session_ids)
        ).order_by(ClassAttendance.date.asc(), ClassAttendance.id.asc()).all()

        attendance_by_date = defaultdict(list)
        for record in attendance_records:
            attendance_by_date[record.date].append(record)

        daily_class_counts = {}
        for date, records in attendance_by_date.items():
            student_counts = defaultdict(int)
            for r in records:
                student_counts[r.student_id] += 1
            daily_class_counts[date] = max(student_counts.values()) if student_counts else 0

        sorted_dates = sorted(daily_class_counts.keys())
        headers = []
        header_keys = []
        for date in sorted_dates:
            count = daily_class_counts.get(date, 0)
            if count <= 1:
                # Full date format: "Nov 20, 2025" or "20 Nov 2025"
                headers.append(date.strftime('%b %d, %Y'))
                header_keys.append((date, 1))
            else:
                for i in range(1, count + 1):
                    # Full date format with session: "Nov 20, 2025 (1)"
                    headers.append(f"{date.strftime('%b %d, %Y')} ({i})")
                    header_keys.append((date, i))

        if not headers:
            flash('No attendance data to download.', 'warning')
            return redirect(url_for('class_management.view_attendance', session_id=session_id))

        students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()

        # Prepare data for template
        data_rows = []
        agg_student_map = attendance_summary.get('per_student', {})
        total_classes = attendance_summary.get('total_classes', sum(daily_class_counts.values()))

        for idx, student in enumerate(students, start=1):
            student_records = [r for r in attendance_records if r.student_id == student.id]
            student_attendance_by_date = defaultdict(list)
            for r in student_records:
                student_attendance_by_date[r.date].append(r)
            attendance_list = []
            for date, slot in header_keys:
                records_for_date = student_attendance_by_date[date]
                if len(records_for_date) >= slot:
                    attendance_list.append('P' if records_for_date[slot-1].is_present else 'A')
                else:
                    attendance_list.append('-')
            agg_stats = agg_student_map.get(student.student_id, {'present': 0, 'percentage': 0, 'marks': 0})
            data_rows.append({
                'idx': idx,
                'student_id': str(student.student_id),
                'name': student.name,
                'attendance': attendance_list,
                'total_classes': str(total_classes),
                'present_days': str(agg_stats['present']),
                'percentage': f"{agg_stats['percentage']:.2f}",
                'marks': str(agg_stats['marks'])
            })

        # Format course scope label
        scope_label = 'Full'
        if session.course_scope == 'part_a':
            scope_label = 'Part A'
        elif session.course_scope == 'part_b':
            scope_label = 'Part B'
        elif session.course_scope:
            scope_label = session.course_scope.replace('_', ' ').title()

        buffer = io.BytesIO()
        # Landscape orientation with minimal margins for maximum space
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(letter), 
            leftMargin=0.15*inch, 
            rightMargin=0.15*inch, 
            topMargin=0.2*inch, 
            bottomMargin=0.15*inch
        )
        styles = getSampleStyleSheet()
        elements = []

        # Create custom centered styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=14,
            textColor=colors.HexColor('#000000'),
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        meta_style = ParagraphStyle(
            'CustomMeta',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#000000'),
            spaceAfter=4,
            alignment=TA_LEFT,
            fontName='Helvetica',
            leftIndent=5
        )

        # Build header text - Excel style
        header_text = "Attendance Sheet"
        
        # Build metadata - Excel style (separate lines)
        course_code = session.course_code or ''
        course_name = session.course_name or ''
        if course_code and course_name:
            subject_text = f"Subject: {course_code} {course_name}"
        elif course_name:
            subject_text = f"Subject: {course_name}"
        elif course_code:
            subject_text = f"Subject: {course_code}"
        else:
            subject_text = "Subject: N/A"
        
        teacher_name = session.teacher.name if session.teacher else 'N/A'
        year_text = f"Year: {session.year}" if session.year else "Year: N/A"
        term_text = f"Term: {session.term}" if session.term else "Term: N/A"
        
        session_text = ""
        if session.academic_session:
            session_text = f"Session: {session.academic_session}"
        session_text += f" Course Teacher: {teacher_name}" if session_text else f"Course Teacher: {teacher_name}"

        elements.append(Spacer(1, 5))
        elements.append(Paragraph(header_text, title_style))
        elements.append(Paragraph(subject_text, meta_style))
        elements.append(Paragraph(year_text, meta_style))
        elements.append(Paragraph(term_text, meta_style))
        elements.append(Paragraph(session_text, meta_style))
        elements.append(Spacer(1, 5))

        # Create styles for text wrapping
        name_style = ParagraphStyle(
            'NameStyle',
            parent=styles['Normal'],
            fontSize=6,
            leading=7,
            alignment=0,  # LEFT
            wordWrap='CJK'
        )
        
        # Header row
        header_row = ['SI', 'Student ID', 'Name']
        for h in headers:
            header_row.append(h)
        header_row.extend(['Total Classes', 'Present', 'Percentage', 'Marks'])
        
        # Convert name column to Paragraph objects for text wrapping
        table_data = [header_row]
        for row in data_rows:
            wrapped_row = [str(row['idx']), str(row['student_id']), Paragraph(row['name'], name_style)]
            wrapped_row.extend(row['attendance'])
            wrapped_row.extend([row['total_classes'], row['present_days'], f"{row['percentage']}%", row['marks']])
            table_data.append(wrapped_row)

        # Calculate dynamic column widths - optimized for ONE page with rotated headers
        available_width = doc.width
        si_width = 0.15*inch
        student_id_width = 0.35*inch
        name_width = 0.5*inch
        summary_col_width = 0.3*inch
        summary_total_width = summary_col_width * 4

        # Calculate remaining width for attendance columns
        fixed_width = si_width + student_id_width + name_width + summary_total_width
        remaining_width = max(0.15*inch, available_width - fixed_width)
        
        # Distribute remaining width among attendance columns - narrow for rotated headers
        if len(headers) > 0:
            attendance_col_width = max(0.1*inch, remaining_width / len(headers))
        else:
            attendance_col_width = 0.1*inch

        column_widths = (
            [si_width, student_id_width, name_width] +
            [attendance_col_width] * len(headers) +
            [summary_col_width] * 4
        )

        # Ensure total width fits within available width
        total_width = sum(column_widths)
        if total_width > available_width * 0.95:
            scale_factor = (available_width * 0.95) / total_width
            column_widths = [w * scale_factor for w in column_widths]
        
        table = Table(table_data, repeatRows=1, colWidths=column_widths, hAlign='CENTER')
        
        # Build table style - optimized for ONE page with rotated headers
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#D8E4BC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTSIZE', (0, 0), (-1, 0), 6),  # Header font
            ('FONTSIZE', (0, 1), (-1, -1), 5),  # Data font
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ])
        
        # Rotate attendance header columns (-90 degrees) to save horizontal space
        if len(headers) > 0:
            attendance_start_col = 3
            attendance_end_col = 3 + len(headers) - 1
            table_style.add('TEXTROTATION', (attendance_start_col, 0), (attendance_end_col, 0), -90)
            table_style.add('FONTSIZE', (attendance_start_col, 0), (attendance_end_col, 0), 5.5)
            table_style.add('TOPPADDING', (attendance_start_col, 0), (attendance_end_col, 0), 50)
            table_style.add('BOTTOMPADDING', (attendance_start_col, 0), (attendance_end_col, 0), 50)
            table_style.add('LEFTPADDING', (attendance_start_col, 0), (attendance_end_col, 0), 1)
            table_style.add('RIGHTPADDING', (attendance_start_col, 0), (attendance_end_col, 0), 1)
        
        table.setStyle(table_style)
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)

        filename = f"attendance_sheet_{session.course_code or session.id}.pdf"
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename=\"{filename}\"',
                'Content-Length': str(len(buffer.getvalue()))
            }
        )
    except Exception as e:
        log_error(e, {
            'session_id': session_id,
            'function': 'download_attendance_sheet',
            'user': current_user.username if current_user.is_authenticated else 'Anonymous'
        })
        current_app.logger.error(f"Error generating attendance sheet PDF for session {session_id}: {e}")
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('class_management.view_attendance', session_id=session_id))

@class_management_bp.route('/download_attendance_sheet_weasyprint/<int:session_id>')
@login_required
def download_attendance_sheet_weasyprint(session_id):
    """Generate attendance sheet PDF using WeasyPrint in legal landscape format."""
    # Lazy import WeasyPrint - only when actually needed
    HTML = _get_weasyprint_html()
    if HTML is None:
        from error_handler import log_error
        error_msg = 'Error generating PDF: WeasyPrint is not available. '
        error_msg += 'Please ensure WeasyPrint dependencies are installed. '
        error_msg += 'On macOS, run: brew install cairo pango gdk-pixbuf gobject-introspection'
        flash(error_msg, 'error')
        current_app.logger.error("WeasyPrint not available for PDF generation")
        current_app.logger.error(f"Current availability status: {_WEASYPRINT_AVAILABLE}")
        return redirect(url_for('class_management.view_attendance', session_id=session_id))
    
    try:
        from error_handler import log_error
        
        session = Session.query.get_or_404(session_id)
        attendance_summary = _build_attendance_summary(session)
        
        # Get related sessions for split courses
        related_sessions = _get_related_sessions(session, include_archived=True)
        session_ids = [s.id for s in related_sessions if s]
        attendance_records = ClassAttendance.query.filter(
            ClassAttendance.session_id.in_(session_ids)
        ).order_by(ClassAttendance.date.asc(), ClassAttendance.id.asc()).all()
        
        attendance_by_date = defaultdict(list)
        for record in attendance_records:
            attendance_by_date[record.date].append(record)
        
        daily_class_counts = {}
        for date, records in attendance_by_date.items():
            student_counts = defaultdict(int)
            for r in records:
                student_counts[r.student_id] += 1
            daily_class_counts[date] = max(student_counts.values()) if student_counts else 0
        
        sorted_dates = sorted(daily_class_counts.keys())
        headers = []
        header_keys = []
        for date in sorted_dates:
            count = daily_class_counts.get(date, 0)
            if count <= 1:
                headers.append(date.strftime('%b %d'))
                header_keys.append((date, 1))
            else:
                for i in range(1, count + 1):
                    headers.append(f"{date.strftime('%b %d')} ({i})")
                    header_keys.append((date, i))
        
        if not headers:
            flash('No attendance data to download.', 'warning')
            return redirect(url_for('class_management.view_attendance', session_id=session_id))
        
        students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
        
        # Prepare data for template
        data_rows = []
        agg_student_map = attendance_summary.get('per_student', {})
        total_classes = attendance_summary.get('total_classes', sum(daily_class_counts.values()))
        
        for idx, student in enumerate(students, start=1):
            # Filter records for this specific student
            student_records = [r for r in attendance_records if r.student_id == student.id]
            # Sort student records by date and id to ensure correct order
            student_records.sort(key=lambda x: (x.date, x.id))
            
            student_attendance_by_date = defaultdict(list)
            for r in student_records:
                student_attendance_by_date[r.date].append(r)
            
            # Sort records by id for each date to ensure correct slot order
            for date in student_attendance_by_date:
                student_attendance_by_date[date].sort(key=lambda x: x.id)
            
            attendance_list = []
            for date, slot in header_keys:
                records_for_date = student_attendance_by_date.get(date, [])
                if len(records_for_date) >= slot:
                    # Records are already sorted by id, so slot-1 index is correct
                    record = records_for_date[slot-1]
                    # Explicitly check is_present value - use bool() to ensure proper conversion
                    is_present_value = bool(record.is_present) if record.is_present is not None else False
                    status = 'P' if is_present_value else 'A'
                    attendance_list.append(status)
                else:
                    attendance_list.append('-')
            agg_stats = agg_student_map.get(student.student_id, {'present': 0, 'percentage': 0, 'marks': 0})
            data_rows.append({
                'idx': idx,
                'student_id': str(student.student_id),
                'name': student.name,
                'attendance': attendance_list,
                'total_classes': str(total_classes),
                'present_days': str(agg_stats['present']),
                'percentage': f"{agg_stats['percentage']:.2f}",
                'marks': str(agg_stats['marks'])
            })
        
        # Get assignment data for Session, Year, Term, Course Teacher
        assignment = None
        if CourseSessionAssignment:
            assignment = CourseSessionAssignment.query.filter_by(session_id=session_id).first()
            # If not found by session_id, try to find by course_code, teacher_id, year, term
            if not assignment and session.course_code and session.teacher_id and session.year and session.term:
                try:
                    if Course:
                        assignment = CourseSessionAssignment.query.filter_by(
                            teacher_id=session.teacher_id,
                            year=session.year,
                            term=session.term
                        ).join(Course, CourseSessionAssignment.course_id == Course.id).filter(
                            Course.course_code == session.course_code
                        ).first()
                except Exception as query_error:
                    current_app.logger.warning(f'Error querying CourseSessionAssignment: {query_error}')
        
        # Get course information
        course_code = session.course_code or ''
        course_name = session.course_name or ''
        
        # Get session, year, term, course teacher
        academic_session = ''
        if assignment and assignment.academic_session:
            academic_session = assignment.academic_session
        elif session.academic_session:
            academic_session = session.academic_session
        
        year = session.year or ''
        term = session.term or ''
        
        course_teacher = 'N/A'
        if assignment and assignment.teacher:
            course_teacher = assignment.teacher.name
        elif session.teacher:
            course_teacher = session.teacher.name
        
        # Render template
        html_content = render_template(
            'class_management/attendance_sheet_weasyprint.html',
            course_code=course_code,
            course_name=course_name,
            academic_session=academic_session,
            year=year,
            term=term,
            course_teacher=course_teacher,
            headers=headers,
            data_rows=data_rows
        )
        
        # Generate PDF with WeasyPrint (lazy import already done above)
        try:
            pdf_buffer = io.BytesIO()
            HTML(string=html_content).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
        except Exception as e:
            current_app.logger.error(f"Error generating PDF with WeasyPrint: {e}", exc_info=True)
            flash(f'Error generating PDF: {str(e)}', 'error')
            return redirect(url_for('class_management.view_attendance', session_id=session_id))
        
        filename = f"attendance_sheet_{course_code or session.id}.pdf"
        
        current_app.logger.info(f"WeasyPrint PDF generated successfully for session {session_id}")
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(pdf_buffer.getvalue()))
            }
        )
        
    except Exception as e:
        log_error(e, {
            'session_id': session_id,
            'function': 'download_attendance_sheet_weasyprint',
            'user': current_user.username if current_user.is_authenticated else 'Anonymous'
        })
        current_app.logger.error(f"Error generating WeasyPrint attendance sheet PDF for session {session_id}: {e}", exc_info=True)
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('class_management.view_attendance', session_id=session_id))

@class_management_bp.route('/assessment/<int:session_id>', methods=['GET', 'POST'])
@login_required
def assessment(session_id):
    """Assessment management for a session"""
    try:
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).all()
        is_split_theory = session.course_type == 'theory' and session.course_scope in SPLIT_PARTS
        editable_indices = _get_editable_assessment_indices(session)
        current_teacher = _ensure_current_teacher()
        
        # Load reveal status
        import json
        reveal_status = {}
        if session.assessment_revealed:
            try:
                reveal_status = json.loads(session.assessment_revealed)
            except:
                reveal_status = {}
        current_teacher_reveals = reveal_status.get(str(current_teacher.id), {})
        
        # Default attendance marks to revealed if not set
        if 'attendance' not in current_teacher_reveals:
            current_teacher_reveals['attendance'] = True
            # Save the default if session doesn't have reveal status yet
            if str(current_teacher.id) not in reveal_status:
                reveal_status[str(current_teacher.id)] = current_teacher_reveals
                session.assessment_revealed = json.dumps(reveal_status)
                db.session.commit()
        
        if request.method == 'POST':
            try:
                import json
                if session.course_type == 'theory':
                    for student in students:
                        # Load existing absent status
                        absent_status = {}
                        if student.assessment_absent:
                            try:
                                absent_status = json.loads(student.assessment_absent)
                            except:
                                absent_status = {}
                        
                        for i in range(1, 5):
                            if i in editable_indices:
                                absent_key = f'absent_{i}_{student.id}'
                                is_absent = absent_key in request.form
                                absent_status[f'assessment{i}'] = is_absent
                                
                                if is_absent:
                                    setattr(student, f'assessment{i}', None)
                                else:
                                    value = request.form.get(f'assessment{i}_{student.id}')
                                    setattr(student, f'assessment{i}', float(value) if value else None)
                        
                        # Save absent status
                        student.assessment_absent = json.dumps(absent_status) if absent_status else None
                    _recalculate_assessment_totals(session)

                elif session.course_type == 'sessional' and session.category == 'ug':
                    for student in students:
                        # Load existing absent status
                        absent_status = {}
                        if student.assessment_absent:
                            try:
                                absent_status = json.loads(student.assessment_absent)
                            except:
                                absent_status = {}
                        
                        report_absent_key = f'sessional_absent_report_{student.id}'
                        viva_absent_key = f'sessional_absent_viva_{student.id}'
                        
                        report_absent = report_absent_key in request.form
                        viva_absent = viva_absent_key in request.form
                        
                        absent_status['sessional_report'] = report_absent
                        absent_status['sessional_viva'] = viva_absent
                        
                        if report_absent:
                            student.sessional_report = None
                        else:
                            report = request.form.get(f'sessional_report_{student.id}')
                            student.sessional_report = float(report) if report else None
                        
                        if viva_absent:
                            student.sessional_viva = None
                        else:
                            viva = request.form.get(f'sessional_viva_{student.id}')
                            student.sessional_viva = float(viva) if viva else None
                        
                        # Save absent status
                        student.assessment_absent = json.dumps(absent_status) if absent_status else None
                else:
                    flash('Unsupported course type for assessment entry.', 'error')
                    return redirect(url_for('class_management.assessment', session_id=session_id))


                db.session.commit()
                flash('Assessment marks saved successfully!', 'success')
                return redirect(url_for('class_management.assessment', session_id=session_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Error saving assessment: {str(e)}', 'error')
                return redirect(url_for('class_management.assessment', session_id=session_id))
        
        # Build combined assessment values from all related sessions (for split courses)
        combined_assessment_values, combined_best3, combined_pg_avg, combined_pg_total = _build_combined_assessment_values(session)
        
        # Debug logging for split courses
        if session.split_group_id:
            current_app.logger.info(f"Assessment page - Session {session_id}: split_group_id={session.split_group_id}, course_scope={session.course_scope}, editable_indices={editable_indices}")
            if students:
                first_student = students[0]
                first_vals = combined_assessment_values.get(first_student.student_id, {})
                current_app.logger.info(f"First student {first_student.student_id} combined values: A1={first_vals.get(1)}, A2={first_vals.get(2)}, A3={first_vals.get(3)}, A4={first_vals.get(4)}")
        
        # Build absent status map for template - combine from all related sessions for split courses
        import json
        absent_status_map = {}
        
        # Get all related sessions for split courses
        related_sessions, student_map = _gather_split_student_map(session)
        all_student_records = []
        
        # Collect all student records from related sessions
        for student_id, entries in student_map.items():
            for entry in entries:
                all_student_records.append(entry)
        
        # Build absent status map combining from all sessions
        for student in students:
            absent_status = {}
            # Start with current student's absent status
            if student.assessment_absent:
                try:
                    absent_status = json.loads(student.assessment_absent)
                except:
                    absent_status = {}
            
            # For split courses, also check absent status from related sessions for the same student_id
            if session.split_group_id:
                for entry in all_student_records:
                    if entry.student_id == student.student_id and entry.id != student.id:
                        if entry.assessment_absent:
                            try:
                                other_absent = json.loads(entry.assessment_absent)
                                # Merge absent status (if any assessment is absent in any session, mark as absent)
                                for key, value in other_absent.items():
                                    if key not in absent_status or not absent_status.get(key):
                                        absent_status[key] = value
                            except:
                                pass
            
            absent_status_map[student.id] = absent_status
        
        return render_template(
            'class_management/assessment.html',
            session=session,
            students=students,
            split_meta=_build_split_context(session),
            editable_indices=editable_indices,
            combined_assessment_values=combined_assessment_values,
            combined_best3=combined_best3,
            combined_pg_avg=combined_pg_avg,
            combined_pg_total=combined_pg_total,
            absent_status_map=absent_status_map,
            current_teacher_id=current_teacher.id,
            reveal_status=current_teacher_reveals,
            assessment_slot_count=len(editable_indices)
        )
        
    except Exception as e:
        flash(f'Error loading assessment page: {str(e)}', 'error')
        return redirect(url_for('class_management.index'))

@class_management_bp.route('/assessment/<int:session_id>/toggle-reveal', methods=['POST'])
@login_required
def toggle_assessment_reveal(session_id):
    """Toggle reveal status for assessment scores"""
    try:
        import json
        session = Session.query.get_or_404(session_id)
        current_teacher = _ensure_current_teacher()
        
        # Ensure current teacher owns this session or is part of split course
        if session.teacher_id != current_teacher.id:
            # Check if it's a split course and teacher is partner
            split_meta = _build_split_context(session)
            if not split_meta or not split_meta.peers:
                return jsonify({'success': False, 'message': 'Unauthorized'}), 403
            partner_ids = [peer.teacher_id for peer in split_meta.peers]
            if current_teacher.id not in partner_ids:
                return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        assessment_type = data.get('assessment_type')
        revealed = data.get('revealed', False)
        teacher_id = data.get('teacher_id', current_teacher.id)
        
        # Load existing reveal status
        reveal_status = {}
        if session.assessment_revealed:
            try:
                reveal_status = json.loads(session.assessment_revealed)
            except:
                reveal_status = {}
        
        # Initialize teacher's reveal status if not exists
        teacher_key = str(teacher_id)
        if teacher_key not in reveal_status:
            reveal_status[teacher_key] = {}
        
        # Update reveal status for this assessment type
        reveal_status[teacher_key][assessment_type] = revealed
        
        # Save to database
        session.assessment_revealed = json.dumps(reveal_status)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Reveal status updated'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@class_management_bp.route('/assessment/<int:session_id>/auto-save', methods=['POST'])
@login_required
def auto_save_assessment(session_id):
    """Auto-save assessment marks via AJAX"""
    try:
        import json
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).all()
        editable_indices = _get_editable_assessment_indices(session)
        
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
        
        try:
            if session.course_type == 'theory':
                for student in students:
                    # Load existing absent status
                    absent_status = {}
                    if student.assessment_absent:
                        try:
                            absent_status = json.loads(student.assessment_absent)
                        except:
                            absent_status = {}
                    
                    for i in range(1, 5):
                        if i in editable_indices:
                            key = f'assessment{i}_{student.id}'
                            absent_key = f'absent_{i}_{student.id}'
                            
                            # Check if absent checkbox is checked
                            is_absent = data.get(absent_key) == 'on' or data.get(absent_key) == True
                            absent_status[f'assessment{i}'] = is_absent
                            
                            # If absent, set mark to None, otherwise save the value
                            if is_absent:
                                setattr(student, f'assessment{i}', None)
                            else:
                                value = data.get(key, '')
                                setattr(student, f'assessment{i}', float(value) if value else None)
                    
                    # Save absent status
                    student.assessment_absent = json.dumps(absent_status) if absent_status else None
                    
                _recalculate_assessment_totals(session)

            elif session.course_type == 'sessional' and session.category == 'ug':
                for student in students:
                    # Load existing absent status
                    absent_status = {}
                    if student.assessment_absent:
                        try:
                            absent_status = json.loads(student.assessment_absent)
                        except:
                            absent_status = {}
                    
                    report_absent_key = f'sessional_absent_report_{student.id}'
                    viva_absent_key = f'sessional_absent_viva_{student.id}'
                    
                    report_absent = data.get(report_absent_key) == 'on' or data.get(report_absent_key) == True
                    viva_absent = data.get(viva_absent_key) == 'on' or data.get(viva_absent_key) == True
                    
                    absent_status['sessional_report'] = report_absent
                    absent_status['sessional_viva'] = viva_absent
                    
                    if report_absent:
                        student.sessional_report = None
                    else:
                        report = data.get(f'sessional_report_{student.id}', '')
                        student.sessional_report = float(report) if report else None
                    
                    if viva_absent:
                        student.sessional_viva = None
                    else:
                        viva = data.get(f'sessional_viva_{student.id}', '')
                        student.sessional_viva = float(viva) if viva else None
                    
                    # Save absent status
                    student.assessment_absent = json.dumps(absent_status) if absent_status else None
            else:
                return jsonify({'success': False, 'message': 'Unsupported course type'}), 400

            db.session.commit()
            return jsonify({'success': True, 'message': 'Assessment marks saved automatically'})
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error auto-saving assessment for session {session_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'message': f'Error saving: {str(e)}'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in auto_save_assessment for session {session_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Server error'}), 500

@class_management_bp.route('/student/view-scores')
@login_required
def student_view_scores():
    """Student view for revealed assessment and attendance scores"""
    try:
        import json
        from flask_login import current_user
        
        # Get student ID from current user (assuming username is student_id)
        student_id = current_user.username if hasattr(current_user, 'username') else None
        if not student_id:
            flash('Student ID not found.', 'error')
            return redirect(url_for('index'))
        
        # Find all ClassStudent records for this student
        student_records = ClassStudent.query.filter_by(student_id=student_id).all()
        
        # First pass: collect all sessions and identify split groups
        # Filter: Only show Theory courses (course_type == 'theory')
        session_records_map = {}  # session_id -> Session
        split_group_processed = set()  # Track processed split_group_ids to avoid duplicate processing
        processed_sessions = set()  # Track which sessions we've processed
        course_map = {}  # unique_course_key -> {'session_ids': set(), 'student_record_ids': set(), 'student_records': []}
        
        # Collect all sessions first
        for student_record in student_records:
            session_obj = Session.query.get(student_record.session_id)
            if not session_obj or session_obj.archived:
                continue
            
            # Filter: Only process Theory courses
            # Also check course_name to catch cases where course_type might be incorrectly set
            if session_obj.course_type != 'theory':
                continue
            
            # Additional check: Filter out courses with "Sessional" in the name (case-insensitive)
            # This catches cases where course_type might be incorrectly set to 'theory'
            if session_obj.course_name and 'sessional' in session_obj.course_name.lower():
                continue
            
            session_records_map[session_obj.id] = session_obj
        
        # Second pass: Group sessions by course (handle split courses properly)
        for session_id, session_obj in session_records_map.items():
            if session_id in processed_sessions:
                continue
            
            # Create unique key for grouping by course
            if session_obj.split_group_id:
                # Split course: group by split_group_id
                # Process all related sessions at once to avoid duplicates
                if session_obj.split_group_id in split_group_processed:
                    continue  # Already processed this split group
                split_group_processed.add(session_obj.split_group_id)
                
                course_key = f"split_{session_obj.split_group_id}"
                related_sessions = _get_related_sessions(session_obj)
                
                if course_key not in course_map:
                    course_map[course_key] = {
                        'session_ids': set(),
                        'student_record_ids': set(),
                        'student_records': []
                    }
                
                # Add all related sessions and their student records
                for related_session in related_sessions:
                    if related_session.course_type != 'theory' or related_session.archived:
                        continue
                    # Additional check: Filter out courses with "Sessional" in the name
                    if related_session.course_name and 'sessional' in related_session.course_name.lower():
                        continue
                    if related_session.id in processed_sessions:
                        continue
                    
                    session_records_map[related_session.id] = related_session
                    course_map[course_key]['session_ids'].add(related_session.id)
                    processed_sessions.add(related_session.id)
                    
                    # Add student records from this related session
                    related_student_records = ClassStudent.query.filter_by(
                        session_id=related_session.id,
                        student_id=student_id
                    ).all()
                    for related_rec in related_student_records:
                        if related_rec.id not in course_map[course_key]['student_record_ids']:
                            course_map[course_key]['student_record_ids'].add(related_rec.id)
                            course_map[course_key]['student_records'].append(related_rec)
            else:
                # Regular course: group by course_name, course_code, year, term, academic_session
                course_key = (
                    str(session_obj.course_name or '').strip().lower(),
                    str(session_obj.course_code or '').strip().lower(),
                    str(session_obj.year or '').strip(),
                    str(session_obj.term or '').strip(),
                    str(session_obj.academic_session or '').strip()
                )
                
                if course_key not in course_map:
                    course_map[course_key] = {
                        'session_ids': set(),
                        'student_record_ids': set(),
                        'student_records': []
                    }
                
                course_map[course_key]['session_ids'].add(session_obj.id)
                processed_sessions.add(session_obj.id)
                
                # Add student records for this session
                session_student_records = ClassStudent.query.filter_by(
                    session_id=session_obj.id,
                    student_id=student_id
                ).all()
                for rec in session_student_records:
                    if rec.id not in course_map[course_key]['student_record_ids']:
                        course_map[course_key]['student_record_ids'].add(rec.id)
                        course_map[course_key]['student_records'].append(rec)
        
        # Second pass: build reveal status by combining all sessions with same course key
        for course_key, course_data in course_map.items():
            reveal_status = {}
            # Default attendance to revealed
            reveal_status['attendance'] = True
            
            # Combine reveal status from all sessions with this course key
            for session_id in course_data['session_ids']:
                session_obj = session_records_map.get(session_id)
                if session_obj and session_obj.assessment_revealed:
                    try:
                        all_reveals = json.loads(session_obj.assessment_revealed)
                        for teacher_id, teacher_reveals in all_reveals.items():
                            for assessment_type, is_revealed in teacher_reveals.items():
                                if is_revealed:
                                    reveal_status[assessment_type] = True
                    except:
                        pass
            
            course_data['reveal_status'] = reveal_status
            # Convert session_ids set to list and get primary session
            session_ids_list = sorted(list(course_data['session_ids']))
            course_data['primary_session'] = session_records_map[session_ids_list[0]]  # Use first session as primary
        
        # Build combined data for each unique course
        courses_data = []
        for course_key, course_data in course_map.items():
            session_obj = course_data['primary_session']  # Use primary session for display
            
            # Double-check: Only process Theory courses (skip Sessional courses)
            if session_obj.course_type != 'theory':
                continue
            
            # Additional check: Filter out courses with "Sessional" in the name (case-insensitive)
            # This catches cases where course_type might be incorrectly set to 'theory'
            if session_obj.course_name and 'sessional' in session_obj.course_name.lower():
                continue
            
            student_records = course_data['student_records']
            reveal_status = course_data['reveal_status']
            all_session_ids = course_data['session_ids']
            
            # Use the first student record as primary (prioritize non-null values)
            primary_record = student_records[0]
            
            # Build assessment scores based on reveal status
            # For split courses, use _build_combined_assessment_values to properly combine from all related sessions
            assessment_scores = {}
            best3_total = None
            pg_total = None
            
            if session_obj.course_type == 'theory' and session_obj.category == 'ug':
                # Use _build_combined_assessment_values which properly handles split courses
                # This function combines assessments from Part A (assessments 1-2) and Part B (assessments 3-4)
                combined_values, combined_best3, combined_pg_avg, combined_pg_total = _build_combined_assessment_values(session_obj)
                
                # Get combined assessment values for this student
                student_combined_values = combined_values.get(student_id, {})
                
                # Build assessment_scores dict from combined values based on reveal status
                for i in range(1, 5):
                    assessment_key = f'assessment{i}'
                    if reveal_status.get(assessment_key, False):
                        # Use combined value which includes assessments from all related sessions
                        value = student_combined_values.get(i, None)
                        assessment_scores[assessment_key] = value
                
                # Get best3_total from combined calculation (includes all assessments from split sessions)
                best3_total = combined_best3.get(student_id, None)
            elif session_obj.course_type == 'theory' and session_obj.category == 'pg':
                # Use _build_combined_assessment_values which properly handles split courses
                # This function combines assessments from Part A (assessments 1-2) and Part B (assessments 3-4)
                combined_values, combined_best3, combined_pg_avg, combined_pg_total = _build_combined_assessment_values(session_obj)
                
                # Get combined assessment values for this student
                student_combined_values = combined_values.get(student_id, {})
                
                # Build assessment_scores dict from combined values based on reveal status
                for i in range(1, 5):
                    assessment_key = f'assessment{i}'
                    if reveal_status.get(assessment_key, False):
                        # Use combined value which includes assessments from all related sessions
                        value = student_combined_values.get(i, None)
                        assessment_scores[assessment_key] = value
                
                # Get pg_total from combined calculation (includes all assessments from split sessions)
                # This is calculated as: (best 3 sum / 30) * 40
                pg_total = combined_pg_total.get(student_id, None)
            # Note: Sessional courses are filtered out - only Theory courses should reach this point
            
            
            # Get attendance marks if revealed
            # For split courses, aggregate attendance from all related sessions
            attendance_data = None
            if reveal_status.get('attendance', True):  # Default to True if not set
                # Use _build_attendance_summary which already handles split courses correctly
                # It aggregates attendance from all related sessions automatically
                attendance_summary = _build_attendance_summary(session_obj)
                
                # Find the student's attendance stats from the summary
                # Use student_id (string) for lookup
                student_stats = attendance_summary.get('per_student', {}).get(student_id, {})
                
                if student_stats:
                    attendance_data = {
                        'present_count': student_stats.get('present', 0),
                        'total_classes': attendance_summary.get('total_classes', 0),
                        'percentage': student_stats.get('percentage', 0),
                        'marks': student_stats.get('marks', 0)
                    }
            
            courses_data.append({
                'session': session_obj,
                'student_record': primary_record,
                'assessment_scores': assessment_scores,
                'best3_total': best3_total,
                'pg_total': pg_total,
                'attendance_data': attendance_data,
                'reveal_status': reveal_status
            })
        
        # Sort courses by course_name, then by year-term for consistent display
        courses_data.sort(key=lambda x: (
            x['session'].course_name or '',
            x['session'].year or '',
            x['session'].term or ''
        ))
        
        return render_template(
            'class_management/student_view_scores.html',
            student_id=student_id,
            courses_data=courses_data
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading student view scores: {e}", exc_info=True)
        flash(f'Error loading scores: {str(e)}', 'error')
        return redirect(url_for('index'))

@class_management_bp.route('/download_assessment_excel/<int:session_id>')
@login_required
def download_assessment_excel(session_id):
    """Download assessment data as Excel file"""
    try:
        import json
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).all()
        combined_values, combined_best3, combined_pg_avg, combined_pg_total = _build_combined_assessment_values(session)
        
        # Helper function to get assessment value with absent check
        def get_assessment_value(student, assessment_num):
            """Get assessment value, showing 'Absent' if marked absent"""
            absent_status = {}
            if student.assessment_absent:
                try:
                    absent_status = json.loads(student.assessment_absent)
                except:
                    absent_status = {}
            
            is_absent = absent_status.get(f'assessment{assessment_num}', False)
            if is_absent:
                return 'Absent'
            
            combined = combined_values.get(student.student_id, {})
            value = combined.get(assessment_num)
            return value if value is not None else ''
        
        # Helper function to get sessional value with absent check
        def get_sessional_value(student, sessional_type):
            """Get sessional value, showing 'Absent' if marked absent"""
            absent_status = {}
            if student.assessment_absent:
                try:
                    absent_status = json.loads(student.assessment_absent)
                except:
                    absent_status = {}
            
            is_absent = absent_status.get(f'sessional_{sessional_type}', False)
            if is_absent:
                return 'Absent'
            
            if sessional_type == 'report':
                value = student.sessional_report
            else:  # viva
                value = student.sessional_viva
            
            return int(round(value)) if value is not None else ''
        
        # Build data for DataFrame
        data = []
        if session.course_type == 'theory' and session.category == 'ug':
            columns = ['Student ID', 'Name', 'Assessment 1', 'Assessment 2', 'Assessment 3', 'Assessment 4', 'Total of Best 3']
            for s in students:
                best3_total = combined_best3.get(s.student_id) if combined_best3 else None
                data.append([
                    s.student_id,
                    s.name,
                    get_assessment_value(s, 1),
                    get_assessment_value(s, 2),
                    get_assessment_value(s, 3),
                    get_assessment_value(s, 4),
                    best3_total
                ])
        elif session.course_type == 'theory' and session.category == 'pg':
            columns = ['Student ID', 'Name', 'Assessment 1', 'Assessment 2', 'Assessment 3', 'Assessment 4', 'Total (40)']
            for s in students:
                data.append([
                    s.student_id,
                    s.name,
                    get_assessment_value(s, 1),
                    get_assessment_value(s, 2),
                    get_assessment_value(s, 3),
                    get_assessment_value(s, 4),
                    combined_pg_total.get(s.student_id)
                ])
        elif session.course_type == 'sessional' and session.category == 'ug':
            columns = ['Student ID', 'Name', 'Sessional Report (60)', 'Sessional Viva (30)', 'Total (Sessional: 90)']
            for s in students:
                report_val = get_sessional_value(s, 'report')
                viva_val = get_sessional_value(s, 'viva')
                
                # Calculate total (skip if either is 'Absent')
                if report_val == 'Absent' or viva_val == 'Absent':
                    total = 'Absent'
                else:
                    total = (s.sessional_report or 0) + (s.sessional_viva or 0)
                    total = int(round(total)) if total else ''
                
                data.append([
                    s.student_id,
                    s.name,
                    report_val,
                    viva_val,
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
        
        # Use Response instead of send_file for better cPanel compatibility
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(output.getvalue()))
            }
        )
        
    except Exception as e:
        flash(f'Error downloading assessment Excel: {str(e)}', 'error')
        return redirect(url_for('class_management.assessment', session_id=session_id))

@class_management_bp.route('/download_assessment_pdf/<int:session_id>')
@login_required
def download_assessment_pdf(session_id):
    """Download assessment marks as PDF"""
    try:
        import json
        session = Session.query.get_or_404(session_id)
        students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
        combined_values, combined_best3, combined_pg_avg, combined_pg_total = _build_combined_assessment_values(session)
        
        # Helper function to get assessment value with absent check
        def get_assessment_value(student, assessment_num):
            """Get assessment value, showing 'Absent' if marked absent"""
            absent_status = {}
            if student.assessment_absent:
                try:
                    absent_status = json.loads(student.assessment_absent)
                except:
                    absent_status = {}
            
            is_absent = absent_status.get(f'assessment{assessment_num}', False)
            if is_absent:
                return 'Absent'
            
            combined = combined_values.get(student.student_id, {})
            value = combined.get(assessment_num)
            return value if value is not None else '-'
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.3*inch,
            rightMargin=0.3*inch,
            topMargin=0.3*inch,
            bottomMargin=0.3*inch
        )
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.black,
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        title = Paragraph("Continuous Assessment Marks", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.15*inch))
        
        # Course Information
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=5,
            alignment=TA_LEFT,
            fontName='Helvetica'
        )
        
        # Course Information with spacing between items
        info_items = []
        if session.course_code:
            info_items.append(f"<b>Subject Code:</b> {session.course_code}")
        if session.course_name:
            info_items.append(f"<b>Subject Name:</b> {session.course_name}")
        if session.academic_session:
            info_items.append(f"<b>Session:</b> {session.academic_session}")
        if session.year:
            info_items.append(f"<b>Year:</b> {session.year}")
        if session.term:
            info_items.append(f"<b>Term:</b> {session.term}")
        
        # Add items with spacing between them
        for i, info_line in enumerate(info_items):
            elements.append(Paragraph(info_line, info_style))
            if i < len(info_items) - 1:  # Add space between items, but not after the last one
                elements.append(Spacer(1, 0.1*inch))
        
        elements.append(Spacer(1, 0.2*inch))
        
        # Table data
        if session.course_type == 'theory' and session.category == 'ug':
            # UG Theory: Assessment 1-4 and Total of Best 3
            table_data = [['SI', 'Student ID', 'Assessment 1 (10)', 'Assessment 2 (10)', 'Assessment 3 (10)', 'Assessment 4 (10)', 'Total of Best 3 (30)']]
            
            for idx, student in enumerate(students, start=1):
                best3_total = combined_best3.get(student.student_id) if combined_best3 else '-'
                # Format total: Keep fraction for UG (show decimals if not whole number)
                if best3_total != '-' and best3_total is not None:
                    if best3_total == int(best3_total):
                        formatted_total = str(int(best3_total))
                    else:
                        formatted_total = f"{best3_total:.2f}".rstrip('0').rstrip('.')
                else:
                    formatted_total = '-'
                row = [
                    str(idx),
                    str(student.student_id),
                    str(get_assessment_value(student, 1)),
                    str(get_assessment_value(student, 2)),
                    str(get_assessment_value(student, 3)),
                    str(get_assessment_value(student, 4)),
                    formatted_total
                ]
                table_data.append(row)
        
        elif session.course_type == 'theory' and session.category == 'pg':
            # PG Theory: Assessment 1-4 and Total (40)
            table_data = [['SI', 'Student ID', 'Assessment 1 (10)', 'Assessment 2 (10)', 'Assessment 3 (10)', 'Assessment 4 (10)', 'Total (40)']]
            
            for idx, student in enumerate(students, start=1):
                pg_total = combined_pg_total.get(student.student_id) if combined_pg_total else '-'
                # Format total: Round for PG (integer)
                if pg_total != '-' and pg_total is not None:
                    formatted_total = str(int(round(pg_total)))
                else:
                    formatted_total = '-'
                row = [
                    str(idx),
                    str(student.student_id),
                    str(get_assessment_value(student, 1)),
                    str(get_assessment_value(student, 2)),
                    str(get_assessment_value(student, 3)),
                    str(get_assessment_value(student, 4)),
                    formatted_total
                ]
                table_data.append(row)
        
        else:
            flash('Assessment PDF is only available for theory courses.', 'error')
            return redirect(url_for('class_management.assessment', session_id=session_id))
        
        # Create table
        table = Table(table_data, repeatRows=1)
        
        # Table style - Black and white
        table_style = TableStyle([
            # Header row - White background, black text
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            
            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1.5, colors.black),  # Thicker borders
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            
            # All rows white background (black and white)
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            
            # Column widths - optimized for one page (without Name column)
            ('COLWIDTH', (0, 0), (0, -1), 0.4*inch),  # SI
            ('COLWIDTH', (1, 0), (1, -1), 1.1*inch),  # Student ID
            ('COLWIDTH', (2, 0), (2, -1), 1.0*inch),  # Assessment 1 (10)
            ('COLWIDTH', (3, 0), (3, -1), 1.0*inch),  # Assessment 2 (10)
            ('COLWIDTH', (4, 0), (4, -1), 1.0*inch),  # Assessment 3 (10)
            ('COLWIDTH', (5, 0), (5, -1), 1.0*inch),  # Assessment 4 (10)
            ('COLWIDTH', (6, 0), (6, -1), 1.1*inch),  # Total
        ])
        
        table.setStyle(table_style)
        elements.append(table)
        
        # Page number callback function
        def add_page_number(canvas_obj, doc_obj):
            """Add page number to each page"""
            canvas_obj.saveState()
            page_num = canvas_obj.getPageNumber()
            text = f"Page {page_num}"
            width, height = letter
            canvas_obj.setFont('Helvetica', 9)
            canvas_obj.drawRightString(width - 0.3*inch, 0.2*inch, text)
            canvas_obj.restoreState()
        
        # Build PDF with page numbers
        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
        buffer.seek(0)
        
        filename = f"assessment_{session.course_code or 'marks'}_{session.year}_{session.term}.pdf"
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(buffer.getvalue()))
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error generating assessment PDF for session {session_id}: {e}", exc_info=True)
        flash(f'Error generating assessment PDF: {str(e)}', 'error')
        return redirect(url_for('class_management.assessment', session_id=session_id))

# Template filter for dynamic attribute access
@class_management_bp.app_template_filter('getattr')
def jinja_getattr(obj, name):
    return getattr(obj, name) 

@class_management_bp.route('/evaluation/<int:session_id>')
@login_required
def evaluation(session_id):
    """Placeholder Evaluation page for a session. Forms will be added later."""
    session = Session.query.get_or_404(session_id)
    students = ClassStudent.query.filter_by(session_id=session_id).order_by(ClassStudent.student_id).all()
    return render_template('class_management/evaluation.html', session=session, students=students)

@class_management_bp.route('/evaluation/<int:session_id>/course-assessment', methods=['GET', 'POST'])
@login_required
def course_assessment(session_id):
    """Invite other teachers to evaluate this course; show existing invitations."""
    session = Session.query.get_or_404(session_id)
    inviter_teacher = Teacher.query.filter_by(id=session.teacher_id).first()

    if request.method == 'POST':
        try:
            evaluator_teacher_id = int(request.form.get('evaluator_teacher_id'))
            if evaluator_teacher_id == session.teacher_id:
                flash('You cannot invite yourself to evaluate.', 'warning')
                return redirect(url_for('class_management.course_assessment', session_id=session_id))

            # prevent duplicate invites
            existing = EvaluationInvite.query.filter_by(
                session_id=session_id,
                evaluator_teacher_id=evaluator_teacher_id
            ).first()
            if existing:
                if existing.status == 'cancelled':
                    # remove any previous submission
                    EvaluationSubmission.query.filter_by(invite_id=existing.id).delete()
                    existing.status = 'invited'
                    existing.created_at = datetime.utcnow()
                    db.session.commit()
                    flash('Invitation re-activated.', 'success')
                else:
                    flash('This teacher is already invited for this course.', 'info')
            else:
                invite = EvaluationInvite(
                    session_id=session_id,
                    inviter_teacher_id=session.teacher_id,
                    evaluator_teacher_id=evaluator_teacher_id,
                    status='invited'
                )
                db.session.add(invite)
                db.session.commit()
                flash('Invitation created successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating invitation: {str(e)}', 'danger')
        return redirect(url_for('class_management.course_assessment', session_id=session_id))

    # List of other teachers to invite (exclude self, head, and teaching assistants)
    from role_utils import get_teachers_excluding_head
    all_teachers = get_teachers_excluding_head()
    other_teachers = [t for t in all_teachers if t.id != session.teacher_id]
    # Existing invites for this session
    invites = EvaluationInvite.query.filter_by(session_id=session_id).all()
    session_ids = [inv.session_id for inv in invites]
    sessions_by_id = {s.id: s for s in Session.query.filter(Session.id.in_(session_ids)).all()} if session_ids else {}
    teacher_ids = {inv.evaluator_teacher_id for inv in invites}
    teachers_by_id = {t.id: t for t in Teacher.query.filter(Teacher.id.in_(teacher_ids)).all()} if teacher_ids else {}

    return render_template(
        'class_management/evaluation_course_assessment.html',
        session=session,
        inviter_teacher=inviter_teacher,
        other_teachers=other_teachers,
        invites=invites,
        sessions_by_id=sessions_by_id,
        teachers_by_id=teachers_by_id
    )

# Context processor to inject pending invites count into all templates
@class_management_bp.app_context_processor
def inject_invites_count():
    try:
        if current_user.is_authenticated and has_teacher_privileges(current_user):
            teacher = Teacher.query.filter_by(name=current_user.full_name).first()
            if teacher:
                count = EvaluationInvite.query.filter_by(evaluator_teacher_id=teacher.id, status='invited').count()
                exam_count = ExamScrutinizerInvite.query.filter_by(scrutinizer_teacher_id=teacher.id, status='invited').count()
                split_count = ClassSplitInvite.query.filter_by(invited_teacher_id=teacher.id, status='pending').count()
                return { 'pending_invites_count': count + exam_count + split_count }
    except Exception:
        pass
    return { 'pending_invites_count': 0 }

@class_management_bp.route('/invitations')
@login_required
def my_invitations():
    """List invitations for the logged-in teacher."""
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        flash('No teacher profile found.', 'warning')
        return redirect(url_for('index'))
    invites = EvaluationInvite.query.filter_by(evaluator_teacher_id=teacher.id).order_by(EvaluationInvite.created_at.desc()).all()
    session_ids = [inv.session_id for inv in invites]
    sessions_by_id = {s.id: s for s in Session.query.filter(Session.id.in_(session_ids)).all()} if session_ids else {}
    inviter_ids = [inv.inviter_teacher_id for inv in invites]
    inviter_by_id = {t.id: t for t in Teacher.query.filter(Teacher.id.in_(inviter_ids)).all()} if inviter_ids else {}

    exam_invites = ExamScrutinizerInvite.query.filter_by(scrutinizer_teacher_id=teacher.id).order_by(ExamScrutinizerInvite.created_at.desc()).all()
    exam_entry_ids = [inv.exam_entry_id for inv in exam_invites]
    exam_entries_by_id = {e.id: e for e in ExamPaperEvaluation.query.filter(ExamPaperEvaluation.id.in_(exam_entry_ids)).all()} if exam_entry_ids else {}
    exam_inviter_ids = [inv.inviter_teacher_id for inv in exam_invites]
    exam_inviter_by_id = {t.id: t for t in Teacher.query.filter(Teacher.id.in_(exam_inviter_ids)).all()} if exam_inviter_ids else {}

    split_invites = ClassSplitInvite.query.filter_by(invited_teacher_id=teacher.id).order_by(ClassSplitInvite.created_at.desc()).all()
    split_sessions_ids = {inv.inviter_session_id for inv in split_invites}
    split_sessions_by_id = {s.id: s for s in Session.query.filter(Session.id.in_(split_sessions_ids)).all()} if split_sessions_ids else {}
    split_inviter_ids = {inv.inviter_teacher_id for inv in split_invites}
    split_inviter_by_id = {t.id: t for t in Teacher.query.filter(Teacher.id.in_(split_inviter_ids)).all()} if split_inviter_ids else {}

    return render_template(
        'class_management/invitations.html',
        invites=invites,
        sessions_by_id=sessions_by_id,
        inviter_by_id=inviter_by_id,
        exam_invites=exam_invites,
        exam_entries_by_id=exam_entries_by_id,
        exam_inviter_by_id=exam_inviter_by_id,
        split_invites=split_invites,
        split_sessions_by_id=split_sessions_by_id,
        split_inviter_by_id=split_inviter_by_id,
        course_scope_labels=COURSE_SCOPE_LABELS
    )

@class_management_bp.route('/evaluation/<int:session_id>/course-assessment/open/<int:invite_id>', methods=['GET', 'POST'])
@login_required
def course_assessment_form(session_id, invite_id):
    """Invitee fills the class observation report form."""
    invite = EvaluationInvite.query.get_or_404(invite_id)
    if invite.session_id != session_id or invite.status == 'cancelled':
        flash('Invalid invitation.', 'danger')
        return redirect(url_for('index'))

    # Current user must be evaluator
    evaluator = Teacher.query.filter_by(name=current_user.full_name).first()
    if not evaluator or evaluator.id != invite.evaluator_teacher_id:
        flash('You are not authorized for this form.', 'danger')
        return redirect(url_for('index'))

    session = Session.query.get_or_404(session_id)
    current_teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not current_teacher or current_teacher.id not in {invite.inviter_teacher_id, invite.evaluator_teacher_id}:
        flash('You are not authorized to view this submission.', 'danger')
        return redirect(url_for('index'))

    submission = EvaluationSubmission.query.filter_by(invite_id=invite.id).first()
    general_data = {}
    score_data = {}
    section_totals = {}
    if submission:
        import json
        try:
            general_data = json.loads(submission.general_info or '{}')
            score_data = json.loads(submission.scores or '{}')
            section_totals = {
                'b1': sum(score_data.get(k, 0) for k in ['b1_a','b1_b','b1_c']),
                'b2': sum(score_data.get(k, 0) for k in ['b2_a','b2_b','b2_c','b2_d','b2_e','b2_f']),
                'b3': sum(score_data.get(k, 0) for k in ['b3_a','b3_b','b3_c','b3_d','b3_e','b3_f','b3_g','b3_h']),
                'b4': sum(score_data.get(k, 0) for k in ['b4_a','b4_b','b4_c'])
            }
            # Backward compatibility for older data
            if 'venue' not in general_data and general_data.get('venue_time'):
                general_data.setdefault('venue', general_data.get('venue_time'))
            general_data.setdefault('session_date', '')
            general_data.setdefault('session_time', '')
        except Exception:
            general_data = {}
            score_data = {}
            section_totals = {}

    general_data.setdefault('program_name', '')
    general_data['teacher_name'] = session.teacher.name if session.teacher else ''
    general_data.setdefault('observer_name', current_user.full_name)
    general_data.setdefault('course_name', session.course_name or '')
    general_data.setdefault('course_code', session.course_code or '')
    general_data.setdefault('course_year', session.year or '')
    general_data.setdefault('course_term', session.term or '')
    general_data.setdefault('academic_session', session.academic_session or '')
    general_data.setdefault('venue', '')
    general_data.setdefault('session_date', '')
    general_data.setdefault('session_time', '')

    if request.method == 'POST':
        try:
            import json
            general = {
                'program_name': request.form.get('program_name'),
                'teacher_name': session.teacher.name if session.teacher else '',
                'observer_name': request.form.get('observer_name'),
                'course_name': request.form.get('course_name') or session.course_name,
                'course_code': request.form.get('course_code') or session.course_code,
                'course_year': request.form.get('course_year') or session.year,
                'course_term': request.form.get('course_term') or session.term,
                'academic_session': request.form.get('academic_session') or session.academic_session,
                'session_date': request.form.get('session_date'),
                'session_time': request.form.get('session_time'),
                'venue': request.form.get('venue')
            }
            # Collect scores
            score_keys = [
                'b1_a','b1_b','b1_c',
                'b2_a','b2_b','b2_c','b2_d','b2_e','b2_f',
                'b3_a','b3_b','b3_c','b3_d','b3_e','b3_f','b3_g','b3_h',
                'b4_a','b4_b','b4_c'
            ]
            scores = {}
            total = 0
            for k in score_keys:
                v = request.form.get(k)
                if v:
                    scores[k] = int(v)
                    total += int(v)
            comments_observer = request.form.get('comments_observer')
            comments_presenter = submission.comments_presenter if submission else None

            if not submission:
                submission = EvaluationSubmission(
                    invite_id=invite.id,
                    session_id=session_id,
                    evaluator_teacher_id=evaluator.id
                )
                db.session.add(submission)

            submission.general_info = json.dumps(general)
            submission.scores = json.dumps(scores)
            submission.comments_observer = comments_observer
            submission.comments_presenter = comments_presenter
            submission.total_score = total
            invite.status = 'submitted'
            db.session.commit()
            flash('Assessment form submitted.', 'success')
            return redirect(url_for('class_management.my_invitations'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting form: {str(e)}', 'danger')

    current_date_str = date.today().isoformat()
    current_time_str = datetime.now().strftime('%H:%M')
    return render_template(
        'class_management/evaluation_course_assessment_form.html',
        session=session,
        invite=invite,
        submission=submission,
        general_data=general_data,
        score_data=score_data,
        section_totals=section_totals,
        current_date=current_date_str,
        current_time=current_time_str
    )


@class_management_bp.route('/evaluation/<int:session_id>/student-feedback', methods=['GET', 'POST'])
@login_required
def student_feedback_manage(session_id):
    """Manage anonymous student feedback link and view submissions."""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher or teacher.id != session.teacher_id:
        flash('শুধুমাত্র কোর্সটির শিক্ষকই ফিডব্যাক সেটআপ করতে পারবেন।', 'danger')
        return redirect(url_for('class_management.evaluation', session_id=session_id))

    feedback_link = (
        StudentFeedbackLink.query.filter_by(session_id=session_id)
        .order_by(StudentFeedbackLink.created_at.desc())
        .first()
    )

    if request.method == 'POST':
        action = request.form.get('action')
        expires_at = None
        expires_raw = request.form.get('expires_at') or ''
        if expires_raw:
            try:
                expires_at = datetime.strptime(expires_raw, '%Y-%m-%d')
            except ValueError:
                flash('ভ্যালিড মেয়াদ তারিখ দিন (YYYY-MM-DD).', 'warning')
                return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

        allow_multiple = bool(request.form.get('allow_multiple'))
        title = request.form.get('title') or f"{session.course_name or 'Course'} Feedback"
        description = request.form.get('description') or ''

        try:
            if action == 'create':
                if feedback_link:
                    flash('ফিডব্যাক লিংক ইতিমধ্যে বিদ্যমান।', 'info')
                else:
                    feedback_link = StudentFeedbackLink(
                        session_id=session_id,
                        access_code=_generate_feedback_code(),
                        title=title,
                        description=description,
                        expires_at=expires_at,
                        allow_multiple=allow_multiple,
                    )
                    db.session.add(feedback_link)
                    db.session.commit()
                    flash('ফিডব্যাক লিংক তৈরি হয়েছে।', 'success')
            elif action == 'update' and feedback_link:
                feedback_link.title = title
                feedback_link.description = description
                feedback_link.expires_at = expires_at
                feedback_link.allow_multiple = allow_multiple
                db.session.commit()
                flash('সেটিংস আপডেট হয়েছে।', 'success')
            elif action == 'regenerate' and feedback_link:
                feedback_link.access_code = _generate_feedback_code()
                db.session.commit()
                flash('নতুন অ্যাক্সেস কোড তৈরি হয়েছে।', 'info')
            elif action == 'delete' and feedback_link:
                db.session.delete(feedback_link)
                db.session.commit()
                flash('ফিডব্যাক লিংক ও সমস্ত উত্তর মুছে ফেলা হয়েছে।', 'info')
                return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))
            else:
                flash('অজানা অ্যাকশন।', 'danger')
        except Exception as exc:
            db.session.rollback()
            flash(f'ফিডব্যাক সেটআপ পরিবর্তন ব্যর্থ: {exc}', 'danger')

        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    feedback_responses = []
    if feedback_link:
        responses = (
            StudentFeedbackResponse.query.filter_by(feedback_link_id=feedback_link.id)
            .order_by(StudentFeedbackResponse.submitted_at.desc())
            .all()
        )
        for item in responses:
            try:
                answers = json.loads(item.payload or '{}')
            except json.JSONDecodeError:
                answers = {}
            feedback_responses.append(
                {
                    'submitted_at': item.submitted_at,
                    'data': answers,
                }
            )

    feedback_url = (
        url_for('student_feedback_form', code=feedback_link.access_code, _external=True)
        if feedback_link
        else None
    )

    return render_template(
        'class_management/student_feedback_manage.html',
        session=session,
        feedback_link=feedback_link,
        feedback_url=feedback_url,
        feedback_responses=feedback_responses,
        section_a_labels=FEEDBACK_SECTION_A,
        section_b_likert=FEEDBACK_SECTION_B_LIKERT,
        method_options=FEEDBACK_METHOD_OPTIONS,
        effort_options=FEEDBACK_EFFORT_OPTIONS,
    )


@class_management_bp.route('/evaluation/<int:session_id>/course-review', methods=['GET', 'POST'])
@login_required
def course_review_form(session_id):
    """Course teacher documents reflections and improvement plans."""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()

    if not teacher:
        flash('You must be registered as a teacher to access the course review form.', 'danger')
        return redirect(url_for('class_management.index'))

    if session.teacher_id != teacher.id:
        flash('Only the course teacher can access the course review form.', 'danger')
        return redirect(url_for('class_management.evaluation', session_id=session_id))

    review = CourseReview.query.filter_by(session_id=session_id, teacher_id=teacher.id).first()
    review_data = {}
    if review and review.data:
        try:
            review_data = json.loads(review.data)
        except Exception:
            review_data = {}
    if not isinstance(review_data, dict):
        review_data = {}

    if 'discipline' not in review_data and review_data.get('department'):
        review_data['discipline'] = review_data.pop('department')
    if 'school' not in review_data and review_data.get('faculty'):
        review_data['school'] = review_data.pop('faculty')
    if 'course_term' not in review_data and review_data.get('semester_term'):
        review_data['course_term'] = review_data.pop('semester_term')
    if 'course_year' not in review_data and review_data.get('level'):
        review_data['course_year'] = review_data.pop('level')

    review_data.setdefault('discipline', '')
    review_data.setdefault('school', '')
    review_data.setdefault('course_title', session.course_name or '')
    review_data.setdefault('course_code', session.course_code or '')
    review_data.setdefault('session_name', session.academic_session or session.year or '')
    review_data.setdefault('course_year', session.year or '')
    review_data.setdefault('course_term', session.term or '')
    review_data.setdefault('credit_value', '')
    review_data.setdefault('instructor_name', session.teacher.name if session.teacher else '')
    review_data.setdefault('enrollment_count', '')
    for row in COURSE_REVIEW_GRADE_ROWS:
        review_data.setdefault(f"{row['key']}_number", '')
        review_data.setdefault(f"{row['key']}_percentage", '')
    review_data.setdefault('grade_total_number', '')
    review_data.setdefault('grade_total_percentage', '')
    if request.method == 'POST':
        try:
            def _clean(field):
                return (request.form.get(field) or '').strip()
            def _to_number(value):
                try:
                    if value is None or value == '':
                        return None
                    return float(value)
                except (TypeError, ValueError):
                    return None

            def _format_number(value, decimals=None):
                if value is None:
                    return ''
                if decimals is not None:
                    return f"{value:.{decimals}f}"
                if float(value).is_integer():
                    return str(int(round(value)))
                return f"{value:.2f}".rstrip('0').rstrip('.')

            form_data = {
                'discipline': _clean('discipline'),
                'school': _clean('school'),
                'course_code': _clean('course_code'),
                'course_title': _clean('course_title'),
                'session_name': _clean('session_name'),
                'course_year': _clean('course_year'),
                'course_term': _clean('course_term'),
                'credit_value': _clean('credit_value'),
                'instructor_name': _clean('instructor_name'),
                'contact_hours': _clean('contact_hours'),
                'lecture_hours': _clean('lecture_hours'),
                'seminar_hours': _clean('seminar_hours'),
                'other_instruction': _clean('other_instruction'),
                'assessment_methods': _clean('assessment_methods'),
                'enrollment_count': _clean('enrollment_count'),
            }

            enrollment_value = _to_number(form_data['enrollment_count'])
            total_number = 0.0
            has_grade_values = False

            for row in COURSE_REVIEW_GRADE_ROWS:
                num_key = f"{row['key']}_number"
                pct_key = f"{row['key']}_percentage"
                number_value = _to_number(_clean(num_key))
                if number_value is not None:
                    has_grade_values = True
                    total_number += number_value
                    form_data[num_key] = _format_number(number_value)
                    if enrollment_value and enrollment_value > 0:
                        percentage_value = (number_value / enrollment_value) * 100
                        form_data[pct_key] = _format_number(percentage_value, decimals=2)
                    else:
                        form_data[pct_key] = ''
                else:
                    form_data[num_key] = ''
                    form_data[pct_key] = ''

            if has_grade_values:
                form_data['grade_total_number'] = _format_number(total_number)
                if enrollment_value and enrollment_value > 0:
                    total_percentage = (total_number / enrollment_value) * 100
                    form_data['grade_total_percentage'] = _format_number(total_percentage, decimals=2)
                else:
                    form_data['grade_total_percentage'] = ''
            else:
                form_data['grade_total_number'] = ''
                form_data['grade_total_percentage'] = ''

            for item in COURSE_REVIEW_COMMENT_FIELDS:
                form_data[item['key']] = _clean(item['key'])

            if review is None:
                review = CourseReview(session_id=session_id, teacher_id=teacher.id)
                db.session.add(review)

            review.data = json.dumps(form_data)
            db.session.commit()
            flash('Course review saved successfully.', 'success')
            return redirect(url_for('class_management.course_review_form', session_id=session_id))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving course review for session {session_id}: {e}")
            flash(f'Error saving course review: {str(e)}', 'danger')

    has_saved_review = bool(review and review.data)

    return render_template(
        'class_management/evaluation_course_review_form.html',
        session=session,
        review_data=review_data,
        grade_rows=COURSE_REVIEW_GRADE_ROWS,
        comment_fields=COURSE_REVIEW_COMMENT_FIELDS,
        has_saved_review=has_saved_review
    )


@class_management_bp.route('/evaluation/<int:session_id>/course-review/pdf')
@login_required
def course_review_pdf(session_id):
    """Download the Faculty Course Review Report as a PDF."""
    session = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()

    if not teacher or teacher.id != session.teacher_id:
        flash('Only the course teacher can download the course review PDF.', 'danger')
        return redirect(url_for('class_management.evaluation', session_id=session_id))

    review = CourseReview.query.filter_by(session_id=session_id, teacher_id=teacher.id).first()
    if not review or not review.data:
        flash('No saved course review found to generate PDF.', 'warning')
        return redirect(url_for('class_management.course_review_form', session_id=session_id))

    try:
        stored_data = json.loads(review.data)
    except Exception:
        flash('Stored course review data is invalid.', 'danger')
        return redirect(url_for('class_management.course_review_form', session_id=session_id))

    from xml.sax.saxutils import escape

    def get_value(key):
        return escape(str(stored_data.get(key, '') or ''))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='CourseReviewTitle',
        parent=styles['Heading1'],
        alignment=TA_CENTER,
        fontSize=14,
        leading=16,
        spaceAfter=12
    )
    subtitle_style = ParagraphStyle(
        name='CourseReviewSubtitle',
        parent=styles['BodyText'],
        alignment=TA_CENTER,
        fontSize=9,
        leading=12,
        spaceAfter=18
    )
    label_style = ParagraphStyle(
        name='CourseReviewLabel',
        parent=styles['BodyText'],
        fontSize=9,
        leading=11,
        spaceAfter=4,
        spaceBefore=2
    )
    comment_style = ParagraphStyle(
        name='CourseReviewComment',
        parent=styles['BodyText'],
        fontSize=9,
        leading=12
    )

    elements = []
    elements.append(Paragraph('FACULTY COURSE REVIEW REPORT', title_style))
    elements.append(Paragraph('(To be filled by each teacher at the time of Course Completion)', subtitle_style))

    table_width = doc.width

    other_paragraph = Paragraph(get_value('other_instruction') or '&nbsp;', comment_style)
    assessment_paragraph = Paragraph(get_value('assessment_methods') or '&nbsp;', comment_style)

    enrollment_paragraph = Paragraph(
        f'Number of Enrolled Students: {get_value("enrollment_count") or "&nbsp;"}',
        label_style
    )

    info_col_widths = [table_width * 0.2, table_width * 0.3, table_width * 0.2, table_width * 0.3]
    info_data = [
        [Paragraph('Discipline', label_style), Paragraph(get_value('discipline'), comment_style), Paragraph('School', label_style), Paragraph(get_value('school'), comment_style)],
        [Paragraph('Course Code', label_style), Paragraph(get_value('course_code'), comment_style), Paragraph('Title', label_style), Paragraph(get_value('course_title'), comment_style)],
        [Paragraph('Session', label_style), Paragraph(get_value('session_name'), comment_style), Paragraph('Year', label_style), Paragraph(get_value('course_year'), comment_style)],
        [Paragraph('Term', label_style), Paragraph(get_value('course_term'), comment_style), Paragraph('Credit Value', label_style), Paragraph(get_value('credit_value'), comment_style)],
        [Paragraph('Name of Course Instructor', label_style), Paragraph(get_value('instructor_name'), comment_style), Paragraph('No. of Students Contact Hour', label_style), Paragraph(get_value('contact_hours'), comment_style)],
        [Paragraph('Lectures', label_style), Paragraph(get_value('lecture_hours'), comment_style), Paragraph('Seminar', label_style), Paragraph(get_value('seminar_hours'), comment_style)],
        [Paragraph('Number of Enrolled Students', label_style), Paragraph(get_value('enrollment_count'), comment_style), '', ''],
        [Paragraph('Other (Please State)', label_style), other_paragraph, '', ''],
        [Paragraph('Assessment Methods: give precise details (no & length of assignments, exams, weightings etc)', label_style), assessment_paragraph, '', '']
    ]

    info_table = Table(info_data, colWidths=info_col_widths, hAlign='CENTER', repeatRows=1)
    info_table.setStyle(TableStyle([
        ('INNERGRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (0, 6), (1, 6)),
        ('SPAN', (0, 7), (1, 7)),
        ('SPAN', (0, 8), (1, 8)),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 16))

    grade_table_data = [['Scale', 'Letter Grade', 'Number of Students', '%']]
    for row in COURSE_REVIEW_GRADE_ROWS:
        grade_table_data.append([
            row['scale'],
            row['letter'],
            get_value(f"{row['key']}_number"),
            get_value(f"{row['key']}_percentage"),
        ])
    grade_table_data.append([
        'Total', '',
        get_value('grade_total_number'),
        get_value('grade_total_percentage'),
    ])

    grade_col_widths = [
        table_width * 0.36,
        table_width * 0.14,
        table_width * 0.25,
        table_width * 0.25,
    ]
    grade_table = Table(grade_table_data, colWidths=grade_col_widths, hAlign='CENTER')
    grade_table.setStyle(TableStyle([
        ('INNERGRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.whitesmoke),
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ]))
    elements.append(grade_table)
    elements.append(Spacer(1, 18))

    elements.append(Paragraph('Overview/Evaluation (Course Coordinator\'s Comments)', label_style))

    comment_table_data = []
    for item in COURSE_REVIEW_COMMENT_FIELDS:
        comment_table_data.append([
            Paragraph(item['label'], label_style),
            Paragraph(get_value(item['key']) or '&nbsp;', comment_style)
        ])

    comment_table = Table(comment_table_data, colWidths=[table_width / 2, table_width / 2], hAlign='CENTER')
    comment_table.setStyle(TableStyle([
        ('INNERGRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('BACKGROUND', (1, 0), (1, -1), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ]))
    elements.append(comment_table)
    elements.append(Spacer(1, 20))

    signature_width = table_width / 2
    signature_table_data = [
        [
            Paragraph('Head of the Discipline Signature', label_style),
            Paragraph('Course Instructor (s) Signature', label_style)
        ],
        [
            Paragraph('&nbsp;' * 4, comment_style),
            Paragraph('&nbsp;' * 4, comment_style)
        ],
        [
            Paragraph('Date: ___________________', label_style),
            Paragraph('Date: ___________________', label_style)
        ]
    ]

    signature_table = Table(
        signature_table_data,
        colWidths=[signature_width, signature_width],
        hAlign='CENTER'
    )
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 24),
        ('RIGHTPADDING', (0, 0), (-1, -1), 24),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEABOVE', (0, 1), (0, 1), 0.8, colors.black),
        ('LINEABOVE', (1, 1), (1, 1), 0.8, colors.black),
        ('BOTTOMPADDING', (0, 1), (1, 1), 24),
    ]))

    elements.append(signature_table)

    def _add_page_number(canvas_obj, doc_obj):
        canvas_obj.saveState()
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.drawRightString(
            doc_obj.pagesize[0] - doc_obj.rightMargin,
            doc_obj.bottomMargin - 20,
            text
        )
        canvas_obj.restoreState()

    doc.build(elements, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    buffer.seek(0)

    filename = f"course_review_{session.course_code or session.id}.pdf"
    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(buffer.getvalue()))
        }
    )


@class_management_bp.route('/evaluation/<int:session_id>/course-assessment/view/<int:invite_id>', methods=['GET', 'POST'])
@login_required
def course_assessment_view(session_id, invite_id):
    """Inviter views a submission and can download PDF."""
    invite = EvaluationInvite.query.get_or_404(invite_id)
    if invite.session_id != session_id:
        flash('Invalid invitation.', 'danger')
        return redirect(url_for('index'))
    session = Session.query.get_or_404(session_id)
    current_teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not current_teacher or current_teacher.id not in {invite.inviter_teacher_id, invite.evaluator_teacher_id}:
        flash('You are not authorized to view this submission.', 'danger')
        return redirect(url_for('index'))

    submission = EvaluationSubmission.query.filter_by(invite_id=invite.id).first()
    if not submission:
        flash('No submission yet.', 'info')
        return redirect(url_for('class_management.course_assessment', session_id=session_id))
    import json
    score_data = json.loads(submission.scores or '{}')
    general_data = json.loads(submission.general_info or '{}')
    if 'venue' not in general_data and general_data.get('venue_time'):
        general_data.setdefault('venue', general_data.get('venue_time'))
    general_data.setdefault('session_date', '')
    general_data.setdefault('session_time', '')
    general_data.setdefault('program_name', '')
    general_data['teacher_name'] = session.teacher.name if session.teacher else ''
    general_data.setdefault('observer_name', '')
    general_data.setdefault('course_name', session.course_name or '')
    general_data.setdefault('course_code', session.course_code or '')
    general_data.setdefault('course_year', session.year or '')
    general_data.setdefault('course_term', session.term or '')
    general_data.setdefault('academic_session', session.academic_session or '')
    section_totals = {
        'b1': sum(score_data.get(k, 0) for k in ['b1_a','b1_b','b1_c']),
        'b2': sum(score_data.get(k, 0) for k in ['b2_a','b2_b','b2_c','b2_d','b2_e','b2_f']),
        'b3': sum(score_data.get(k, 0) for k in ['b3_a','b3_b','b3_c','b3_d','b3_e','b3_f','b3_g','b3_h']),
        'b4': sum(score_data.get(k, 0) for k in ['b4_a','b4_b','b4_c'])
    }
    can_edit_presenter = current_teacher and current_teacher.id == session.teacher_id

    if request.method == 'POST':
        if not can_edit_presenter:
            flash('You are not authorized to update presenter comments.', 'danger')
            return redirect(url_for('class_management.course_assessment_view', session_id=session_id, invite_id=invite_id))
        submission.comments_presenter = request.form.get('comments_presenter')
        try:
            db.session.commit()
            flash("Presenter's comments updated.", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating comments: {str(e)}', 'danger')
        return redirect(url_for('class_management.course_assessment_view', session_id=session_id, invite_id=invite_id))

    return render_template('class_management/evaluation_course_assessment_view.html', session=session, invite=invite, submission=submission, general_data=general_data, score_data=score_data, section_totals=section_totals, can_edit_presenter=can_edit_presenter)

@class_management_bp.route('/evaluation/<int:session_id>/course-assessment/pdf/<int:invite_id>')
@login_required
def course_assessment_pdf(session_id, invite_id):
    """Generate PDF of the submitted assessment."""
    try:
        import json
        from xml.sax.saxutils import escape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        invite = EvaluationInvite.query.get_or_404(invite_id)
        if invite.session_id != session_id:
            flash('Invalid invitation.', 'danger')
            return redirect(url_for('index'))
        session = Session.query.get_or_404(session_id)
        current_teacher = Teacher.query.filter_by(name=current_user.full_name).first()
        if not current_teacher or current_teacher.id not in {invite.inviter_teacher_id, invite.evaluator_teacher_id}:
            flash('You are not authorized to download this report.', 'danger')
            return redirect(url_for('index'))

        submission = EvaluationSubmission.query.filter_by(invite_id=invite.id).first()
        if not submission:
            flash('No submission to export.', 'warning')
            return redirect(url_for('class_management.course_assessment', session_id=session_id))

        general = json.loads(submission.general_info or '{}')
        if 'venue' not in general and general.get('venue_time'):
            general.setdefault('venue', general.get('venue_time'))
        general.setdefault('session_date', '')
        general.setdefault('session_time', '')
        general.setdefault('program_name', '')
        general.setdefault('teacher_name', session.teacher.name if session.teacher else '')
        general.setdefault('observer_name', '')
        general.setdefault('course_name', session.course_name or '')
        general.setdefault('course_code', session.course_code or '')
        general.setdefault('course_year', session.year or '')
        general.setdefault('course_term', session.term or '')
        general.setdefault('academic_session', session.academic_session or '')
        scores = json.loads(submission.scores or '{}')
        section_totals = {
            'b1': sum(scores.get(k, 0) for k in ['b1_a','b1_b','b1_c']),
            'b2': sum(scores.get(k, 0) for k in ['b2_a','b2_b','b2_c','b2_d','b2_e','b2_f']),
            'b3': sum(scores.get(k, 0) for k in ['b3_a','b3_b','b3_c','b3_d','b3_e','b3_f','b3_g','b3_h']),
            'b4': sum(scores.get(k, 0) for k in ['b4_a','b4_b','b4_c'])
        }

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('ReportTitle', parent=styles['Title'], fontSize=16, spaceAfter=12)
        label_style = ParagraphStyle('Label', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=10)
        value_style = ParagraphStyle('Value', parent=styles['BodyText'], fontSize=10)
        center_value_style = ParagraphStyle('CenterValue', parent=value_style, alignment=1)
        section_header_style = ParagraphStyle('SectionHeader', parent=styles['BodyText'], fontName='Helvetica-Bold', fontSize=10)
        subtotal_style = ParagraphStyle('Subtotal', parent=styles['BodyText'], fontName='Helvetica-Oblique', fontSize=10)
        comment_header_style = ParagraphStyle('CommentHeader', parent=styles['Heading4'], fontSize=11, spaceBefore=12, spaceAfter=6)

        elements = []
        elements.append(Paragraph('Classroom Teaching Observation Report', title_style))

        info_data = [
            [Paragraph('Program', label_style), Paragraph(escape(general.get('program_name') or '-') , value_style),
             Paragraph('Teacher', label_style), Paragraph(escape(general.get('teacher_name') or '-') , value_style)],
            [Paragraph('Observer', label_style), Paragraph(escape(general.get('observer_name') or '-') , value_style),
             Paragraph('Course Name', label_style), Paragraph(escape(general.get('course_name') or '-') , value_style)],
            [Paragraph('Course Code', label_style), Paragraph(escape(general.get('course_code') or '-') , value_style),
             Paragraph('Academic Session', label_style), Paragraph(escape(general.get('academic_session') or '-') , value_style)],
            [Paragraph('Year', label_style), Paragraph(escape(general.get('course_year') or '-') , value_style),
             Paragraph('Term', label_style), Paragraph(escape(general.get('course_term') or '-') , value_style)],
            [Paragraph('Date', label_style), Paragraph(escape(general.get('session_date') or '-') , value_style),
             Paragraph('Time', label_style), Paragraph(escape(general.get('session_time') or '-') , value_style)],
            [Paragraph('Venue', label_style), Paragraph(escape(general.get('venue') or '-') , value_style),
             Paragraph('', label_style), Paragraph('', value_style)]
        ]
        info_table = Table(info_data, colWidths=[80, 180, 80, 180])
        info_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f7f7f7')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('SPAN', (2,5), (3,5)),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 10))
        elements.append(Paragraph('Score Scale: 5 = Excellent, 4 = Very Good, 3 = Good, 2 = Fair, 1 = Poor', styles['BodyText']))
        elements.append(Spacer(1, 8))

        score_rows = [[Paragraph('<b>Description</b>', label_style), Paragraph('<b>Score</b>', center_value_style)]]
        section_headers = []
        span_rows = []
        subtotal_rows = []

        def add_section(title, items, subtotal_key):
            header_idx = len(score_rows)
            score_rows.append([Paragraph(f'<b>{escape(title)}</b>', section_header_style), ''])
            section_headers.append(header_idx)
            span_rows.append(header_idx)
            for text, key in items:
                score_rows.append([
                    Paragraph(escape(text), value_style),
                    Paragraph(str(scores.get(key)) if key in scores else '-', center_value_style)
                ])
            subtotal_idx = len(score_rows)
            score_rows.append([
                Paragraph(f'<i>Subtotal for {escape(title)}</i>', subtotal_style),
                Paragraph(f"<b>{section_totals.get(subtotal_key, 0)}</b>", center_value_style)
            ])
            subtotal_rows.append(subtotal_idx)

        add_section('Section 1: Set Induction', [
            ('a) Clarity of objectives', 'b1_a'),
            ('b) Relevance to topic', 'b1_b'),
            ('c) Appropriateness of introduction', 'b1_c')
        ], 'b1')

        add_section('Section 2: Content', [
            ('a) Knowledge', 'b2_a'),
            ('b) Extend of coverage', 'b2_b'),
            ('c) Level of interest generated', 'b2_c'),
            ('d) Logical flow of presentation', 'b2_d'),
            ('e) Correctness of language used', 'b2_e'),
            ('f) Clear and relevant use of analogies/examples', 'b2_f')
        ], 'b2')

        add_section('Section 3: Presentation', [
            ('a) Appropriate pacing', 'b3_a'),
            ('b) Confidence', 'b3_b'),
            ('c) Enthusiasm', 'b3_c'),
            ('d) Provoking students to think', 'b3_d'),
            ('e) Clarity of presentation', 'b3_e'),
            ('f) Interaction with students', 'b3_f'),
            ('g) Effective use of teaching/learning aids', 'b3_g'),
            ('h) Effective class management', 'b3_h')
        ], 'b3')

        add_section('Section 4: Closure', [
            ('a) Appropriateness of closure', 'b4_a'),
            ('b) Effective questions for feedback', 'b4_b'),
            ('c) Appropriate links to the next lesson', 'b4_c')
        ], 'b4')

        score_rows.append([
            Paragraph('<b>Total Score</b>', label_style),
            Paragraph(f"<b>{submission.total_score or 0}</b>", center_value_style)
        ])

        score_table = Table(score_rows, colWidths=[360, 80])
        score_style = TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ])
        for idx in section_headers:
            score_style.add('SPAN', (0, idx), (1, idx))
            score_style.add('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#e5e5e5'))
            score_style.add('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold')
        for idx in subtotal_rows:
            score_style.add('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#f9f9f9'))
        score_style.add('BACKGROUND', (0, len(score_rows)-1), (-1, len(score_rows)-1), colors.HexColor('#e8f4ff'))
        score_table.setStyle(score_style)
        elements.append(score_table)

        elements.append(Spacer(1, 12))

        interpret_data = [
            [Paragraph('<b>Score</b>', label_style), Paragraph('<b>Interpretation</b>', label_style)],
            ['90 to 100', 'Excellent'],
            ['80 to less than 90', 'Very Good'],
            ['70 to less than 80', 'Good'],
            ['60 to less than 70', 'Fair'],
            ['50 to less than 60', 'Poor'],
            ['40 to less than 50', 'Very Poor']
        ]
        interpret_table = Table(interpret_data, colWidths=[140, 200])
        interpret_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f0f0f0')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER')
        ]))
        elements.append(interpret_table)

        observer_comment = (submission.comments_observer or '').strip()
        presenter_comment = (submission.comments_presenter or '').strip()
        elements.append(Paragraph("Observer's Overall Comments and Suggestions for Improvement", comment_header_style))
        elements.append(Paragraph(escape(observer_comment).replace('\n', '<br/>') or '-', styles['BodyText']))
        elements.append(Paragraph("Presenter's Comments", comment_header_style))
        elements.append(Paragraph(escape(presenter_comment).replace('\n', '<br/>') or '-', styles['BodyText']))

        elements.append(Spacer(1, 60))
        line_width = (A4[0] - 72) / 2
        signature_table = Table(
            [['', ''], ["Presenter's Signature", "Observer's Signature"]],
            colWidths=[line_width, line_width]
        )
        signature_table.setStyle(TableStyle([
            ('LINEABOVE', (0,0), (0,0), 0.7, colors.black),
            ('LINEABOVE', (1,0), (1,0), 0.7, colors.black),
            ('TOPPADDING', (0,0), (-1,0), 30),
            ('ALIGN', (0,1), (-1,1), 'CENTER'),
            ('TOPPADDING', (0,1), (-1,1), 8)
        ]))
        elements.append(signature_table)

        class NumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_page_number(num_pages)
                    super().showPage()
                super().save()

            def draw_page_number(self, page_count):
                self.setFont('Helvetica', 9)
                text = f"Page {self._pageNumber} of {page_count}"
                self.drawRightString(A4[0] - 36, 30, text)

        doc.build(elements, canvasmaker=NumberedCanvas)
        buffer.seek(0)
        filename = f"course_assessment_{session.course_code or session.id}.pdf"
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(buffer.getvalue()))
            }
        )
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'danger')
        return redirect(url_for('class_management.course_assessment', session_id=session_id))

@class_management_bp.route('/invitation/<int:invite_id>/cancel', methods=['POST'])
@login_required
def cancel_invitation(invite_id):
    """Allow either inviter or invitee to cancel an invitation."""
    invite = EvaluationInvite.query.get_or_404(invite_id)

    # Resolve current teacher for the logged-in user
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        flash('No teacher profile found.', 'warning')
        return redirect(url_for('index'))

    if teacher.id not in [invite.inviter_teacher_id, invite.evaluator_teacher_id]:
        flash('You are not authorized to cancel this invitation.', 'danger')
        return redirect(url_for('index'))

    try:
        invite.status = 'cancelled'
        EvaluationSubmission.query.filter_by(invite_id=invite.id).delete()
        db.session.commit()
        flash('Invitation has been cancelled.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling invitation: {str(e)}', 'danger')

    # Redirect back to sensible page
    if teacher.id == invite.inviter_teacher_id:
        return redirect(url_for('class_management.course_assessment', session_id=invite.session_id))
    else:
        return redirect(url_for('class_management.my_invitations'))

FEEDBACK_SECTION_A = [
    ('course_structure', 'Course content is structured in a comprehensible manner.'),
    ('course_goals', 'The goals of the course are clear.'),
    ('course_content_guidance', 'The course contents are explained in an understandable fashion.'),
    ('course_interest', 'The course fosters my interest in the discussed topics.'),
]

FEEDBACK_SECTION_B_LIKERT = [
    ('course_plan_discussed', 'Course plan (assessment criteria/ content) was discussed in advance.'),
    ('guidelines_received', 'Received oral instruction and written guidelines for continuous assessment.'),
    ('assessment_helpful', 'Course projects/assignments/tests were helpful to demonstrate an understanding of the course material.'),
    ('feedback_timely', 'Received feedback and grades of continuous assessments from course teacher in due time.'),
]

FEEDBACK_METHOD_OPTIONS = [
    'Lectures (including online lectures)',
    'Class discussions (including online discussion boards)',
    'In-class learning activities (other than discussion)',
    'In-class clickers or other quick response methods',
    'Homework (readings and assignments)',
    'Labs',
    'Projects or portfolios',
    'Teamwork or group activities',
    'Student presentations',
    'Guest lecturers',
    'Fieldwork/field trips',
    'Mentoring outside of the classroom',
    'Support from Teaching/ Research Assistants',
    'Others'
]

FEEDBACK_EFFORT_OPTIONS = [
    'Memorizing facts and repeating ideas from the readings and lectures.',
    'Making judgments about the value of information, arguments, or methods.',
    'Applying basic elements of an idea, experience, or theory.',
    'Applying theories or concepts to practical problems or in new situations.',
    'Synthesizing and organizing ideas, information, or experiences.',
    'Solving problems.',
    'Thinking creatively or critically.',
    'Teamwork or group activities.',
    'Doing lab work.',
    'Presenting in person or via a recording.',
    'Reading and writing for deep understanding.',
    'Others'
]

@class_management_bp.route('/evaluation/<int:session_id>/student-feedback/responses/pdf')
@login_required
def student_feedback_responses_pdf(session_id):
    session_obj = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher or teacher.id != session_obj.teacher_id:
        flash('You are not authorized to access this download.', 'danger')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    feedback_link = StudentFeedbackLink.query.filter_by(session_id=session_id).first()
    if not feedback_link:
        flash('No feedback responses found.', 'info')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    responses = (
        StudentFeedbackResponse.query.filter_by(feedback_link_id=feedback_link.id)
        .order_by(StudentFeedbackResponse.submitted_at.asc())
        .all()
    )
    if not responses:
        flash('No feedback responses to download.', 'info')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    buffer = io.BytesIO()
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    response_font = 'Helvetica'
    response_bold_font = 'Helvetica-Bold'
    kalpurush_available = False
    try:
        font_root = os.path.join(current_app.root_path, 'static', 'fonts')
        regular_candidates = ['Kalpurush.ttf', 'Kalpurush-Regular.ttf']
        bold_candidates = ['Kalpurush-Bold.ttf', 'Kalpurush Bold.ttf']
        regular_path = next((os.path.join(font_root, f) for f in regular_candidates if os.path.exists(os.path.join(font_root, f))), None)
        bold_path = next((os.path.join(font_root, f) for f in bold_candidates if os.path.exists(os.path.join(font_root, f))), None)
        if regular_path:
            pdfmetrics.registerFont(TTFont('Kalpurush', regular_path))
            response_font = 'Kalpurush'
            kalpurush_available = True
        if bold_path:
            pdfmetrics.registerFont(TTFont('Kalpurush-Bold', bold_path))
            response_bold_font = 'Kalpurush-Bold'
        elif regular_path:
            response_bold_font = 'Kalpurush'
    except Exception as exc:  # pragma: no cover
        current_app.logger.warning('Kalpurush font registration failed: %s', exc)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=28,
        bottomMargin=28,
        leftMargin=32,
        rightMargin=32,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, fontSize=16, leading=18, spaceAfter=6, textTransform='uppercase', fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], alignment=1, fontSize=13, leading=16, spaceAfter=12, textTransform='uppercase', fontName='Helvetica-Bold')
    section_header_style = ParagraphStyle('SectionHeader', parent=styles['Heading3'], fontSize=11, leading=13, spaceBefore=8, spaceAfter=4, textTransform='uppercase', fontName='Helvetica-Bold')
    label_style = ParagraphStyle('Label', parent=styles['Normal'], fontSize=9, leading=11, fontName='Helvetica-Bold', wordWrap='CJK')
    instruction_style = ParagraphStyle('Instruction', parent=styles['Normal'], fontSize=9, leading=11, alignment=1, textTransform='uppercase', spaceBefore=6, spaceAfter=6, wordWrap='CJK', fontName='Helvetica-Bold')
    value_style = ParagraphStyle('Value', parent=styles['Normal'], fontSize=9.5, leading=11, fontName=response_font, wordWrap='CJK')
    value_bold_style = ParagraphStyle('ValueBold', parent=value_style, fontName=response_bold_font)
    # Style for Praise and Suggestions section - always use Kalpurush if available
    praise_suggestions_font = 'Kalpurush' if kalpurush_available else response_font
    praise_suggestions_style = ParagraphStyle('PraiseSuggestions', parent=styles['Normal'], fontSize=9.5, leading=11, fontName=praise_suggestions_font, wordWrap='CJK')

    likert_header = ['Statement', 'Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree']

    def likert_table(section_values, labels):
        data = [[Paragraph(text, label_style) for text in likert_header]]
        for key, question in labels:
            selected = (section_values or {}).get(key)
            row = [Paragraph(question, value_style)]
            for option in likert_header[1:]:
                mark = '✓' if selected and selected.lower() == option.lower() else ''
                row.append(Paragraph(mark, value_style))
            data.append(row)
        table = Table(data, colWidths=[240, 52, 52, 52, 52, 52])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEADING', (0, 0), (-1, -1), 11),
        ]))
        return table

    def checklist_table(options, selected):
        rows = []
        selected = selected or []
        for idx in range(0, len(options), 2):
            row = []
            for offset in (0, 1):
                if idx + offset < len(options):
                    option = options[idx + offset]
                    mark = '✓' if option in selected else ''
                    row.append(Paragraph(f"{mark} {option}", value_style))
                else:
                    row.append('')
            rows.append(row)
        table = Table(rows, colWidths=[255, 255])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.75, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return table

    elements = []
    for idx, item in enumerate(responses, start=1):
        try:
            data = json.loads(item.payload or '{}')
        except json.JSONDecodeError:
            data = {}

        academic = data.get('academic_info', {}) or {}
        section_a = data.get('section_a', {}) or {}
        section_b = data.get('section_b', {}) or {}
        section_c = data.get('section_c', {}) or {}
        section_d = data.get('section_d', {}) or {}

        if idx > 1:
            elements.append(PageBreak())

        elements.append(Paragraph('Student Feedback Form', title_style))
        elements.append(Paragraph('Khulna University', subtitle_style))
        elements.append(Paragraph(f"Response {idx} - {item.submitted_at.strftime('%Y-%m-%d %H:%M')}", value_bold_style))
        elements.append(Spacer(1, 6))

        info_data = [
            [Paragraph('Academic Session', label_style), Paragraph(academic.get('academic_session') or '—', value_style)],
            [Paragraph('Title of the Course', label_style), Paragraph(academic.get('course_title') or session_obj.course_name or '—', value_style)],
            [Paragraph('Course Code', label_style), Paragraph(academic.get('course_code') or session_obj.course_code or '—', value_style)],
        ]
        info_table = Table(info_data, colWidths=[140, 360])
        info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
        ]))
        elements.append(info_table)
        elements.append(Paragraph('Please tick/cross in the blank space which best describes how much you agree with the following statements', instruction_style))

        elements.append(Paragraph('A. Satisfaction with the Course', section_header_style))
        elements.append(likert_table(section_a, FEEDBACK_SECTION_A))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph('B. Teaching-Learning Methods', section_header_style))
        elements.append(likert_table(section_b, [FEEDBACK_SECTION_B_LIKERT[0]]))
        elements.append(Spacer(1, 4))

        methods = section_b.get('teaching_methods') or []
        if methods:
            elements.append(Paragraph('Teaching methods that contributed significantly (selected):', value_bold_style))
            elements.append(checklist_table(FEEDBACK_METHOD_OPTIONS, methods))
            elements.append(Spacer(1, 4))

        elements.append(likert_table(section_b, FEEDBACK_SECTION_B_LIKERT[1:]))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph('C. Engagement and Workload', section_header_style))
        engagement_table = Table(
            [
                [Paragraph('How much time do you devote to this course before and after each lecture?', label_style), Paragraph(section_c.get('study_time') or '—', value_style)],
                [Paragraph('About what percent of the class meetings (including discussions) did you attend?', label_style), Paragraph(section_c.get('attendance_percent') or '—', value_style)],
            ],
            colWidths=[360, 140]
        )
        engagement_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(engagement_table)
        elements.append(Spacer(1, 4))

        efforts = section_c.get('effort_focus') or []
        elements.append(Paragraph('Significant aspects of your effort (selected):', value_bold_style))
        elements.append(checklist_table(FEEDBACK_EFFORT_OPTIONS, efforts))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph('D. Praise and Suggestions', section_header_style))
        def open_block(title, content):
            # Use Kalpurush font for Praise and Suggestions content
            content_style = praise_suggestions_style
            table = Table(
                [
                    [Paragraph(title, label_style)],
                    [Paragraph(content or '—', content_style)]
                ],
                colWidths=[500]
            )
            table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('VALIGN', (0, 1), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 12)
            ]))
            return table

        elements.append(open_block('What did you like especially about this course?', section_d.get('likes')))
        elements.append(Spacer(1, 4))
        elements.append(open_block('What are the challenges you have faced in attending the course?', section_d.get('challenges')))
        elements.append(Spacer(1, 4))
        elements.append(open_block('Suggestions on how to improve the course:', section_d.get('suggestions')))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()

    filename = f"student_feedback_responses_{session_obj.course_code or 'course'}.pdf"
    return Response(
        pdf_data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(pdf_data)),
        },
    )

@class_management_bp.route('/evaluation/<int:session_id>/student-feedback/responses/pdf-weasyprint')
@login_required
def student_feedback_responses_pdf_weasyprint(session_id):
    """Generate student feedback PDF using WeasyPrint with Kalpurush for Praise and Suggestions."""
    # Lazy import WeasyPrint - only when actually needed
    HTML = _get_weasyprint_html()
    if HTML is None:
        error_msg = 'Error generating PDF: WeasyPrint is not available. '
        error_msg += 'Please ensure WeasyPrint dependencies are installed. '
        error_msg += 'On macOS, run: brew install cairo pango gdk-pixbuf gobject-introspection'
        flash(error_msg, 'error')
        current_app.logger.error("WeasyPrint not available for PDF generation")
        current_app.logger.error(f"Current availability status: {_WEASYPRINT_AVAILABLE}")
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))
    
    session_obj = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher or teacher.id != session_obj.teacher_id:
        flash('You are not authorized to access this download.', 'danger')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    feedback_link = StudentFeedbackLink.query.filter_by(session_id=session_id).first()
    if not feedback_link:
        flash('No feedback responses found.', 'info')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    responses = (
        StudentFeedbackResponse.query.filter_by(feedback_link_id=feedback_link.id)
        .order_by(StudentFeedbackResponse.submitted_at.asc())
        .all()
    )
    if not responses:
        flash('No feedback responses to download.', 'info')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    try:
        from error_handler import log_error
        import os
        
        # Prepare data for template
        feedback_data = []
        for idx, item in enumerate(responses, start=1):
            try:
                data = json.loads(item.payload or '{}')
            except json.JSONDecodeError:
                data = {}
            
            academic = data.get('academic_info', {}) or {}
            section_a = data.get('section_a', {}) or {}
            section_b = data.get('section_b', {}) or {}
            section_c = data.get('section_c', {}) or {}
            section_d = data.get('section_d', {}) or {}
            
            feedback_data.append({
                'index': idx,
                'submitted_at': item.submitted_at.strftime('%Y-%m-%d'),
                'academic': academic,
                'section_a': section_a,
                'section_b': section_b,
                'section_c': section_c,
                'section_d': section_d,
                'course_name': academic.get('course_title') or session_obj.course_name or '—',
                'course_code': academic.get('course_code') or session_obj.course_code or '—',
                'academic_session': academic.get('academic_session') or '—',
            })
        
        # Get font path for WeasyPrint
        font_path = os.path.join(current_app.root_path, 'static', 'Fonts', 'kalpurush.ttf')
        if not os.path.exists(font_path):
            # Try alternative path
            font_path = os.path.join(current_app.root_path, 'static', 'fonts', 'kalpurush.ttf')
        
        # Render template
        html_content = render_template(
            'class_management/student_feedback_weasyprint.html',
            feedback_data=feedback_data,
            feedback_section_a=FEEDBACK_SECTION_A,
            feedback_section_b_likert=FEEDBACK_SECTION_B_LIKERT,
            feedback_method_options=FEEDBACK_METHOD_OPTIONS,
            feedback_effort_options=FEEDBACK_EFFORT_OPTIONS,
            likert_options=['Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'],
            kalpurush_font_path=font_path if os.path.exists(font_path) else None
        )
        
        # Generate PDF with WeasyPrint (lazy import already done above)
        try:
            pdf_buffer = io.BytesIO()
            HTML(string=html_content, base_url=request.url_root).write_pdf(pdf_buffer)
            pdf_buffer.seek(0)
        except Exception as e:
            current_app.logger.error(f"Error generating PDF with WeasyPrint: {e}", exc_info=True)
            flash(f'Error generating PDF: {str(e)}', 'error')
            return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))
        
        filename = f"student_feedback_responses_{session_obj.course_code or 'course'}.pdf"
        
        current_app.logger.info(f"WeasyPrint PDF generated successfully for student feedback session {session_id}")
        return Response(
            pdf_buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Length': str(len(pdf_buffer.getvalue()))
            }
        )
        
    except Exception as e:
        log_error(e, {
            'session_id': session_id,
            'function': 'student_feedback_responses_pdf_weasyprint',
            'user': current_user.username if current_user.is_authenticated else 'Anonymous'
        })
        current_app.logger.error(f"Error generating WeasyPrint student feedback PDF for session {session_id}: {e}", exc_info=True)
        flash(f'Error generating PDF: {str(e)}', 'error')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

@class_management_bp.route('/evaluation/<int:session_id>/student-feedback/responses/docx')
@login_required
def student_feedback_responses_docx(session_id):
    session_obj = Session.query.get_or_404(session_id)
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher or teacher.id != session_obj.teacher_id:
        flash('You are not authorized to access this download.', 'danger')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    feedback_link = StudentFeedbackLink.query.filter_by(session_id=session_id).first()
    if not feedback_link:
        flash('No feedback responses found.', 'info')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    responses = (
        StudentFeedbackResponse.query.filter_by(feedback_link_id=feedback_link.id)
        .order_by(StudentFeedbackResponse.submitted_at.asc())
        .all()
    )
    if not responses:
        flash('No feedback responses to download.', 'info')
        return redirect(url_for('class_management.student_feedback_manage', session_id=session_id))

    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn

    document = Document()
    normal_style = document.styles['Normal']
    normal_style.font.name = 'Kalpurush'
    normal_style.font.size = Pt(11)
    normal_style._element.rPr.rFonts.set(qn('w:eastAsia'), 'Kalpurush')

    heading1 = document.styles['Heading 1']
    heading1.font.name = 'Helvetica'
    heading1.font.size = Pt(16)
    heading1.font.bold = True

    heading2 = document.styles['Heading 2']
    heading2.font.name = 'Helvetica'
    heading2.font.size = Pt(13)
    heading2.font.bold = True

    for idx, item in enumerate(responses, start=1):
        try:
            data = json.loads(item.payload or '{}')
        except json.JSONDecodeError:
            data = {}

        academic = data.get('academic_info', {}) or {}
        section_a = data.get('section_a', {}) or {}
        section_b = data.get('section_b', {}) or {}
        section_c = data.get('section_c', {}) or {}
        section_d = data.get('section_d', {}) or {}

        if idx > 1:
            document.add_page_break()

        title_para = document.add_paragraph('STUDENT FEEDBACK FORM')
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.runs[0]
        title_run.bold = True
        title_run.font.size = Pt(16)

        uni_para = document.add_paragraph('KHULNA UNIVERSITY')
        uni_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        uni_para.runs[0].bold = True
        uni_para.runs[0].font.size = Pt(12)

        meta_para = document.add_paragraph(f"Response {idx} - {item.submitted_at.strftime('%Y-%m-%d %H:%M')}")
        meta_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta_para.runs[0].font.size = Pt(10)

        add_header_table([
            ('Academic Session', academic.get('academic_session') or '—'),
            ('Title of the Course', academic.get('course_title') or session_obj.course_name or '—'),
            ('Course Code', academic.get('course_code') or session_obj.course_code or '—'),
        ])

        instruction_para = document.add_paragraph(
            'PLEASE TICK/CROSS IN THE BLANK SPACE WHICH BEST DESCRIBES HOW MUCH YOU AGREE WITH THE FOLLOWING STATEMENTS'
        )
        instruction_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        instruction_para.runs[0].font.size = Pt(9)

        document.add_paragraph('A. SATISFACTION WITH THE COURSE', style='Heading 3')
        section_a_rows = []
        for key, question in FEEDBACK_SECTION_A:
            selected = section_a.get(key)
            row = [question]
            for option in likert_header[1:]:
                row.append('✓' if selected and selected.lower() == option.lower() else '')
            section_a_rows.append(row)
        add_likert_table(section_a_rows, likert_header)

        document.add_paragraph('B. TEACHING-LEARNING METHODS', style='Heading 3')
        first_question = FEEDBACK_SECTION_B_LIKERT[0]
        first_selected = section_b.get(first_question[0])
        first_rows = [[first_question[1]] + [('✓' if first_selected and first_selected.lower() == opt.lower() else '') for opt in likert_header[1:]]]
        add_likert_table(first_rows, likert_header)

        methods_heading = document.add_paragraph('Teaching methods that contributed significantly (selected):')
        methods_heading.runs[0].bold = True
        methods = section_b.get('teaching_methods') or []
        if methods:
            for method in methods:
                bullet = document.add_paragraph(method, style='List Bullet')
                bullet.paragraph_format.space_after = Pt(1)
        else:
            document.add_paragraph('—', style='List Bullet')

        remaining_rows = []
        for key, question in FEEDBACK_SECTION_B_LIKERT[1:]:
            selected = section_b.get(key)
            row = [question]
            for option in likert_header[1:]:
                row.append('✓' if selected and selected.lower() == option.lower() else '')
            remaining_rows.append(row)
        add_likert_table(remaining_rows, likert_header)

        document.add_paragraph('C. ENGAGEMENT AND WORKLOAD', style='Heading 3')
        engagement_rows = [
            ('How much time do you devote to this course before and after each lecture?', section_c.get('study_time') or '—'),
            ('About what percent of the class meetings (including discussions) did you attend?', section_c.get('attendance_percent') or '—'),
        ]
        engagement_table = document.add_table(rows=len(engagement_rows), cols=2)
        engagement_table.style = 'Table Grid'
        for row_idx, (label, value) in enumerate(engagement_rows):
            set_cell_shading(engagement_table.cell(row_idx, 0), 'D9D9D9')
            set_cell_text(engagement_table.cell(row_idx, 0), label, bold=True, align='left')
            set_cell_text(engagement_table.cell(row_idx, 1), value, align='left')

        effort_heading = document.add_paragraph('Significant aspects of your effort (selected):')
        effort_heading.runs[0].bold = True
        efforts = section_c.get('effort_focus') or []
        if efforts:
            for effort in efforts:
                bullet = document.add_paragraph(effort, style='List Bullet')
                bullet.paragraph_format.space_after = Pt(1)
        else:
            document.add_paragraph('—', style='List Bullet')

        document.add_paragraph('D. PRAISE AND SUGGESTIONS', style='Heading 3')
        add_open_block('What did you like especially about this course?', section_d.get('likes'))
        add_open_block('What are the challenges you have faced in attending the course?', section_d.get('challenges'))
        add_open_block('Suggestions on how to improve the course:', section_d.get('suggestions'))

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    docx_data = buffer.getvalue()
    buffer.close()

    filename = f"student_feedback_responses_{session_obj.course_code or 'course'}.docx"
    return Response(
        docx_data,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(docx_data)),
        },
    )