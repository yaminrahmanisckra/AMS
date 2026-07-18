from flask import render_template, request, redirect, url_for, flash, jsonify, send_file, current_app, session
from flask_login import login_required, current_user
from extensions import db
from . import course_management_bp
from .models import Curriculum, Course, StudentCourseRegistration, CourseRegistrationInvite, DutyAssignment, CurriculumYearTerm, CourseSessionAssignment
from .forms import CurriculumForm, CourseForm, CourseInfoForm
from blueprints.student_management.models import Student
from blueprints.class_management.models import Session, Teacher, ClassStudent
from role_utils import parse_roles, is_admin, get_teachers_excluding_head
try:
    from utils.semester_utils import filter_by_active_semester
except ImportError:
    filter_by_active_semester = None
try:
    from utils.window_utils import (
        filter_by_active_window,
        filter_offered_courses,
        get_effective_window_id,
        query_for_window,
        stamp_window_id,
        get_for_window,
        DEFAULT_WINDOW_ID,
    )
except ImportError:
    filter_by_active_window = None
    filter_offered_courses = None
    get_effective_window_id = None
    query_for_window = None
    stamp_window_id = None
    get_for_window = None
    DEFAULT_WINDOW_ID = 1
from user_models import User
from sqlalchemy import and_, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import noload
from io import BytesIO


def _cyt_query():
    """Curriculum year/term configs scoped to the active operational window."""
    if query_for_window:
        return query_for_window(CurriculumYearTerm)
    return CurriculumYearTerm.query


def _csa_query():
    """Course session assignments scoped to the active operational window."""
    if query_for_window:
        return query_for_window(CourseSessionAssignment)
    return CourseSessionAssignment.query


def _active_window_id():
    """Resolved operational window id for curriculum UI and writes."""
    if not get_effective_window_id:
        return DEFAULT_WINDOW_ID
    # Always honor the user's selected window (including Head/Admin with W2).
    window_id = get_effective_window_id(admin_override=False)
    if window_id is None:
        return DEFAULT_WINDOW_ID
    return window_id


def _window_rows_filter(model, window_id=None):
    """Filter rows belonging to the selected operational window."""
    window_id = _active_window_id() if window_id is None else window_id
    if not hasattr(model, 'window_id'):
        return True
    if window_id == DEFAULT_WINDOW_ID:
        return or_(
            model.window_id == window_id,
            model.window_id.is_(None),
        )
    return model.window_id == window_id

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from PIL import Image as PILImage
import os
import hashlib
from datetime import datetime


def _normalize_session_course_type(raw_course_type):
    """Map course types to compact values fitting class_session.course_type."""
    value = (raw_course_type or '').strip().lower()
    if not value:
        return 'theory'
    if 'dissertation' in value:
        return 'dissertation'
    if 'thesis' in value:
        return 'thesis'
    if 'sessional' in value:
        return 'sessional'
    if 'viva' in value:
        return 'viva'
    if 'theory' in value:
        return 'theory'
    # Keep a safe bounded fallback to avoid DataError on short DB column.
    return value[:20]


def _normalize_source_year_term(payload_source_year, payload_source_term, running_year, running_term):
    """Normalize course-origin metadata with safe running-context fallback."""
    source_year = str(payload_source_year or '').strip() or str(running_year or '').strip() or None
    source_term = str(payload_source_term or '').strip() or str(running_term or '').strip() or None
    return source_year, source_term


def _is_retake_remark(remark_value):
    remark_normalized = str(remark_value or '').strip().lower()
    return remark_normalized in {'retake', 're-retake', 're retake', 'reretake'}


def _course_code_lookup_key(course_code):
    return str(course_code or '').strip().replace(' ', '').lower()


def _collapsed_course_code_column(column):
    return func.replace(func.lower(column), ' ', '')


def _registration_course_filter(course_code, academic_session, year, term, include_archived=False):
    """Build filters for course-wise registration queries.

    Includes:
    - Direct registrations on the selected course code (Regular or Retake)
    - Retake rows mapped to this subject via relevant_course_code, using either
      the running semester or the stored relevant semester context
    """
    course_code_key = _course_code_lookup_key(course_code)
    status_filters = []
    if not include_archived:
        status_filters.append(StudentCourseRegistration.status != 'archived')

    remark_lower = func.lower(func.trim(StudentCourseRegistration.remark))
    retake_remarks = ['retake', 're-retake', 're retake', 'reretake']

    direct_clause = and_(
        _collapsed_course_code_column(StudentCourseRegistration.course_code) == course_code_key,
        StudentCourseRegistration.academic_session == academic_session,
        StudentCourseRegistration.year == year,
        StudentCourseRegistration.term == term,
        *status_filters,
    )

    retake_via_relevant_context = and_(
        _collapsed_course_code_column(StudentCourseRegistration.relevant_course_code) == course_code_key,
        StudentCourseRegistration.relevant_academic_session == academic_session,
        StudentCourseRegistration.relevant_year == year,
        StudentCourseRegistration.relevant_term == term,
        remark_lower.in_(retake_remarks),
        *status_filters,
    )

    retake_via_running_context = and_(
        _collapsed_course_code_column(StudentCourseRegistration.relevant_course_code) == course_code_key,
        StudentCourseRegistration.academic_session == academic_session,
        StudentCourseRegistration.year == year,
        StudentCourseRegistration.term == term,
        remark_lower.in_(retake_remarks),
        *status_filters,
    )

    return or_(direct_clause, retake_via_relevant_context, retake_via_running_context), course_code_key


def _serialize_course_wise_registration(reg, student, selected_course_code_key=None):
    registered_code_key = _course_code_lookup_key(reg.course_code)
    relevant_code_key = _course_code_lookup_key(getattr(reg, 'relevant_course_code', '') or '')
    is_retake_row = _is_retake_remark(reg.remark)
    is_merged_retake = (
        selected_course_code_key
        and is_retake_row
        and relevant_code_key == selected_course_code_key
        and registered_code_key != selected_course_code_key
    )
    return {
        'registration_id': reg.id,
        'course_id': reg.course_id,
        'student_id': student.id,
        'student_roll': getattr(student, 'student_id', '') or '',
        'student_name': getattr(student, 'name', '') or '',
        'batch': getattr(student, 'batch', '') or '',
        'remark': reg.remark or 'Regular',
        'carry_on': bool(getattr(reg, 'carry_on', False)),
        'use_relevant_for_committee': (
            reg.use_relevant_for_committee
            if hasattr(reg, 'use_relevant_for_committee') and reg.use_relevant_for_committee is not None
            else True
        ),
        'status': reg.status,
        'source_year': reg.source_year or reg.year,
        'source_term': reg.source_term or reg.term,
        'registered_course_code': reg.course_code,
        'registered_course_name': reg.course_name,
        'is_merged_retake': is_merged_retake,
        'relevant_course_id': getattr(reg, 'relevant_course_id', None),
        'relevant_course_code': getattr(reg, 'relevant_course_code', '') or '',
        'relevant_academic_session': getattr(reg, 'relevant_academic_session', '') or '',
        'relevant_year': getattr(reg, 'relevant_year', '') or '',
        'relevant_term': getattr(reg, 'relevant_term', '') or '',
        'credit': reg.credit,
        'course_type': reg.course_type,
        'nature': reg.nature or 'Core',
    }


def _normalize_use_relevant_for_committee(raw_value, is_retake):
    """Normalize per-registration merge flag for committee/remuneration counting."""
    if not is_retake:
        return False
    # Backward-compatible default for retake rows: merge enabled.
    if raw_value in (None, ''):
        return True
    if isinstance(raw_value, bool):
        return raw_value
    value = str(raw_value).strip().lower()
    if value in {'1', 'true', 'yes', 'y', 'on'}:
        return True
    if value in {'0', 'false', 'no', 'n', 'off'}:
        return False
    return True


def _resolve_use_relevant_for_committee(raw_value, is_retake, existing_value=None):
    """
    Resolve merge flag with safe preservation behavior.

    - Non-retake rows are always False.
    - For retake rows, when payload omits the field and an existing value is known,
      preserve existing value instead of forcing fallback default.
    """
    if not is_retake:
        return False
    if raw_value in (None, '') and existing_value is not None:
        return bool(existing_value)
    return _normalize_use_relevant_for_committee(raw_value, is_retake)


def _normalize_relevant_course_mapping(payload, default_year=None, default_term=None):
    """Normalize relevant-course mapping fields from payload."""
    payload = payload or {}
    relevant_course_id = payload.get('relevant_course_id')
    relevant_course_code = str(payload.get('relevant_course_code') or '').strip() or None
    relevant_academic_session = str(payload.get('relevant_academic_session') or '').strip() or None
    relevant_year = str(payload.get('relevant_year') or '').strip() or (str(default_year or '').strip() or None)
    relevant_term = str(payload.get('relevant_term') or '').strip() or (str(default_term or '').strip() or None)

    try:
        relevant_course_id = int(relevant_course_id) if relevant_course_id not in (None, '') else None
    except (TypeError, ValueError):
        relevant_course_id = None

    if relevant_course_id and not relevant_course_code:
        mapped_course = Course.query.get(relevant_course_id)
        if mapped_course:
            relevant_course_code = (mapped_course.course_code or '').strip() or None

    if relevant_course_code and not relevant_course_id:
        mapped_course = Course.query.filter_by(course_code=relevant_course_code).first()
        if mapped_course:
            relevant_course_id = mapped_course.id

    if not relevant_year or not relevant_term:
        relevant_year = None
        relevant_term = None
    if not relevant_academic_session:
        relevant_academic_session = None

    # Allow year/term/session-only mapping for retake committee context.
    # relevant_course_code can remain empty, but context should not be dropped.
    if not relevant_course_code and not any([relevant_academic_session, relevant_year, relevant_term]):
        return {
            'relevant_course_id': None,
            'relevant_course_code': None,
            'relevant_academic_session': None,
            'relevant_year': None,
            'relevant_term': None,
        }

    return {
        'relevant_course_id': relevant_course_id,
        'relevant_course_code': relevant_course_code,
        'relevant_academic_session': relevant_academic_session,
        'relevant_year': relevant_year,
        'relevant_term': relevant_term,
    }


def _resolve_class_target_context(registration_like, fallback_course_code, fallback_session, fallback_year, fallback_term):
    """Resolve class session target using carry_on + relevant mapping policy."""
    def _extract(name, default=None):
        if isinstance(registration_like, dict):
            return registration_like.get(name, default)
        return getattr(registration_like, name, default)

    remark = _extract('remark', 'Regular')
    carry_on = bool(_extract('carry_on', False))
    is_retake = _is_retake_remark(remark)

    if is_retake and not carry_on:
        relevant_course_code = str(_extract('relevant_course_code') or '').strip()
        relevant_session = str(_extract('relevant_academic_session') or '').strip()
        relevant_year = str(_extract('relevant_year') or '').strip()
        relevant_term = str(_extract('relevant_term') or '').strip()
        if relevant_course_code and relevant_session and relevant_year and relevant_term:
            return {
                'course_code': relevant_course_code,
                'academic_session': relevant_session,
                'year': relevant_year,
                'term': relevant_term
            }

    return {
        'course_code': fallback_course_code,
        'academic_session': fallback_session,
        'year': fallback_year,
        'term': fallback_term
    }


def _remove_students_from_class_sessions(course_code, academic_session, year, term, student_ids):
    """Remove students from class management sessions when registration is deleted"""
    if not Session or not ClassStudent or not Student:
        return
    
    try:
        # Find all sessions for this course, session, year, and term
        sessions = Session.query.filter_by(
            course_code=course_code,
            academic_session=academic_session,
            year=year,
            term=term
        ).all()
        
        if not sessions:
            current_app.logger.info(f'No sessions found for course {course_code}, session {academic_session}, year {year}, term {term}')
            return
        
        removed_count = 0
        
        for session in sessions:
            # Get student records - student_ids can be either Student.id (int) or student_id (string)
            # Try to get by id first, then by student_id
            students = []
            student_ids_list = []
            for sid in student_ids:
                student = Student.query.get(sid) if isinstance(sid, int) else Student.query.filter_by(student_id=sid).first()
                if student:
                    students.append(student)
                    student_ids_list.append(student.student_id)
            
            if not student_ids_list:
                continue
            
            # Find and delete ClassStudent records for these students in this session
            class_students = ClassStudent.query.filter(
                ClassStudent.session_id == session.id,
                ClassStudent.student_id.in_(student_ids_list)
            ).all()
            
            for class_student in class_students:
                db.session.delete(class_student)
                removed_count += 1
                
                # Also remove from peer sessions for split courses
                try:
                    from blueprints.class_management.routes import _replicate_student_to_peers
                    # Find peer sessions
                    if hasattr(session, 'split_group_id') and session.split_group_id:
                        peer_sessions = Session.query.filter_by(
                            split_group_id=session.split_group_id,
                            course_code=course_code,
                            academic_session=academic_session,
                            year=year,
                            term=term
                        ).filter(Session.id != session.id).all()
                        
                        for peer_session in peer_sessions:
                            peer_class_student = ClassStudent.query.filter_by(
                                session_id=peer_session.id,
                                student_id=class_student.student_id
                            ).first()
                            if peer_class_student:
                                db.session.delete(peer_class_student)
                                removed_count += 1
                except Exception as replicate_error:
                    current_app.logger.warning(f'Error removing student from peers for {class_student.student_id}: {replicate_error}')
        
        if removed_count > 0:
            db.session.commit()
            current_app.logger.info(f'Removed {removed_count} student(s) from {len(sessions)} session(s) for course {course_code}')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error removing students from class sessions: {e}', exc_info=True)
        raise


def _add_students_to_class_sessions(course_code, academic_session, year, term, students_data):
    """Add students to class management sessions based on course registration"""
    if not Session or not ClassStudent or not Student:
        return
    
    try:
        added_to_sessions = 0

        sessions_cache = {}

        for student_info in students_data:
            # Handle both dict and int formats
            if isinstance(student_info, dict):
                student_id = student_info.get('student_id')
                carry_on = student_info.get('carry_on', False)
                target_course_code = (student_info.get('target_course_code') or course_code or '').strip()
                target_session = (student_info.get('target_academic_session') or academic_session or '').strip()
                target_year = (student_info.get('target_year') or year or '').strip()
                target_term = (student_info.get('target_term') or term or '').strip()
            else:
                student_id = student_info
                carry_on = False
                target_course_code = (course_code or '').strip()
                target_session = (academic_session or '').strip()
                target_year = (year or '').strip()
                target_term = (term or '').strip()

            if not target_course_code or not target_session or not target_year or not target_term:
                current_app.logger.warning(
                    'Skipping class placement due to incomplete target context: '
                    f'student_id={student_id}, target={target_course_code}/{target_session}/{target_year}/{target_term}'
                )
                continue

            target_key = (target_course_code, target_session, target_year, target_term)
            if target_key not in sessions_cache:
                sessions_cache[target_key] = Session.query.filter_by(
                    course_code=target_course_code,
                    academic_session=target_session,
                    year=target_year,
                    term=target_term
                ).all()
            sessions = sessions_cache[target_key]

            if not sessions:
                current_app.logger.info(
                    'No sessions found for target class placement (exact match). '
                    f'Attempting to auto-create from course assignments: '
                    f'course={target_course_code}, session={target_session}, year={target_year}, term={target_term}'
                )

                try:
                    assignments = _csa_query().join(
                        Course, Course.id == CourseSessionAssignment.course_id
                    ).filter(
                        Course.course_code == target_course_code,
                        CourseSessionAssignment.academic_session == target_session,
                        CourseSessionAssignment.year == target_year,
                        CourseSessionAssignment.term == target_term
                    ).all()

                    created_sessions = []
                    for assignment in assignments:
                        if not assignment.teacher_id:
                            continue

                        section_value = (assignment.section or '').strip().upper()
                        if section_value == 'A':
                            scope_value = 'part_a'
                        elif section_value == 'B':
                            scope_value = 'part_b'
                        else:
                            scope_value = 'full'

                        existing_session = Session.query.filter_by(
                            teacher_id=assignment.teacher_id,
                            course_code=target_course_code,
                            academic_session=target_session,
                            year=target_year,
                            term=target_term,
                            course_scope=scope_value
                        ).first()
                        if existing_session:
                            created_sessions.append(existing_session)
                            continue

                        session_obj = Session(
                            year=target_year,
                            term=target_term,
                            academic_session=target_session,
                            course_code=target_course_code,
                            course_name=(assignment.course.course_name if assignment.course else target_course_code),
                            teacher_id=assignment.teacher_id,
                            course_type=_normalize_session_course_type(assignment.course.course_type if assignment.course else 'theory'),
                            category=(assignment.course.category if assignment.course and assignment.course.category else 'ug'),
                            course_scope=scope_value
                        )
                        db.session.add(session_obj)
                        db.session.flush()
                        created_sessions.append(session_obj)

                    if created_sessions:
                        sessions = created_sessions
                        sessions_cache[target_key] = sessions
                        current_app.logger.info(
                            f'Auto-created/found {len(created_sessions)} target session(s) for '
                            f'{target_course_code} {target_session}/{target_year}/{target_term}'
                        )
                    else:
                        current_app.logger.info(
                            'No assignments found to auto-create target sessions for '
                            f'course={target_course_code}, session={target_session}, year={target_year}, term={target_term}'
                        )
                        continue
                except Exception as auto_create_error:
                    current_app.logger.warning(
                        f'Failed to auto-create target sessions for class placement: {auto_create_error}',
                        exc_info=True
                    )
                    continue

            # Get student record
            student = Student.query.get(student_id)
            if not student:
                current_app.logger.warning(f'Student with id {student_id} not found in Student model, skipping...')
                continue

            for session_obj in sessions:
                current_app.logger.info(
                    f'Processing student: {student.student_id} ({student.name}) for session '
                    f'{session_obj.id} (course: {session_obj.course_code})'
                )

                # Check if student already exists in this session
                existing = ClassStudent.query.filter_by(
                    session_id=session_obj.id,
                    student_id=student.student_id
                ).first()

                if existing:
                    current_app.logger.info(
                        f'Student {student.student_id} ({student.name}) already exists in session '
                        f'{session_obj.id} for course {target_course_code}, skipping...'
                    )
                    continue

                # Add student to session
                class_student = ClassStudent(
                    student_id=student.student_id,
                    name=student.name,
                    session_id=session_obj.id,
                    teacher_id=session_obj.teacher_id
                )
                db.session.add(class_student)
                db.session.flush()  # Flush to get class_student.id

                # Carry on assessment marks if enabled
                if carry_on:
                    try:
                        from blueprints.class_management.routes import _carry_on_assessment_marks
                        _carry_on_assessment_marks(class_student, session_obj)
                    except Exception as carry_on_error:
                        current_app.logger.warning(f'Error carrying on marks for {student.student_id}: {carry_on_error}')

                # Replicate to peer sessions for split courses
                try:
                    from blueprints.class_management.routes import _replicate_student_to_peers
                    _replicate_student_to_peers(session_obj, class_student)
                except Exception as replicate_error:
                    current_app.logger.warning(f'Error replicating student to peers for {student.student_id}: {replicate_error}')

                added_to_sessions += 1
        
        if added_to_sessions > 0:
            db.session.commit()
            current_app.logger.info(f'Successfully added {added_to_sessions} student(s) to Class Management sessions')
        else:
            current_app.logger.warning('No students were added to Class Management. They may already exist in target sessions.')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error adding students to class sessions: {e}', exc_info=True)
        raise


def _get_current_student_record():
    username = getattr(current_user, 'username', None)
    if not username:
        return None
    return Student.query.filter_by(student_id=username).first()

def _get_teachers_excluding_head():
    """Get teachers excluding Head/TA/Admin and deleted accounts (uses role_utils)."""
    return get_teachers_excluding_head()


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


def _normalize_registration_year(label):
    """Normalize year labels for registration matching (LLM <-> Fifth, etc.)."""
    if not label:
        return ''
    value = str(label).strip().lower()
    for suffix in [' year', 'yr', ' years']:
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
    year_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second',
        '3': 'third', '3rd': 'third', 'third': 'third',
        '4': 'fourth', '4th': 'fourth', 'fourth': 'fourth',
        '5': 'fifth', '5th': 'fifth', 'fifth': 'fifth',
        'llm': 'llm',
    }
    canonical = year_map.get(value, value)
    if canonical in {'fifth', 'llm'}:
        return 'llm'
    return canonical


def _normalize_registration_term(label):
    """Normalize term labels for registration matching."""
    if not label:
        return ''
    value = str(label).strip().lower()
    for suffix in [' term', 'semester', ' sem']:
        if value.endswith(suffix):
            value = value[:-len(suffix)].strip()
    term_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second',
        'thesis': 'thesis', 'thesis term': 'thesis',
    }
    return term_map.get(value, value)


def _registration_years_match(year_a, year_b):
    if not year_a or not year_b:
        return False
    return _normalize_registration_year(year_a) == _normalize_registration_year(year_b)


def _registration_terms_match(term_a, term_b):
    if not term_a or not term_b:
        return False
    return _normalize_registration_term(term_a) == _normalize_registration_term(term_b)


def _cyt_rows_for_session_year_term(session_name=None, year=None, term=None):
    """Return curriculum year/term rows matching session/year/term with label normalization."""
    rows = _cyt_query().all()
    matched = []
    for row in rows:
        if session_name and str(row.academic_session or '').strip() != str(session_name).strip():
            continue
        if year and not _registration_years_match(row.year, year):
            continue
        if term and not _registration_terms_match(row.term, term):
            continue
        matched.append(row)
    return matched


def _batches_from_csv(batch_text):
    if not batch_text:
        return []
    return [b.strip() for b in str(batch_text).split(',') if b.strip() and b.strip() != 'None']


def _curriculum_accepts_batch(curriculum, batch_value, window_id=None):
    """Return True when batch is allowed by curriculum-level applicable batches."""
    if not curriculum or not batch_value:
        return False
    applicable = curriculum.get_batches_list(window_id=window_id)
    if not applicable:
        return True
    return batch_value in applicable


def _cyt_row_accepts_batch(cfg, batch_value, curriculum, window_id=None):
    """Match batch against CurriculumYearTerm row and curriculum applicable batches."""
    configured = _batches_from_csv(cfg.batch if cfg else None)
    if configured:
        return batch_value in configured
    return _curriculum_accepts_batch(curriculum, batch_value, window_id)


def _resolve_allowed_curriculum_ids(session_name, year, term, batch_value, window_id=None):
    """Resolve curricula for coordinator/student registration course dropdowns."""
    if not session_name or not batch_value:
        return None, ''

    matching_configs = _cyt_rows_for_session_year_term(session_name, year, term)
    curriculum_ids = {cfg.curriculum_id for cfg in matching_configs if cfg.curriculum_id}
    curricula_by_id = {
        c.id: c for c in Curriculum.query.filter(Curriculum.id.in_(curriculum_ids)).all()
    } if curriculum_ids else {}

    allowed = set()
    for cfg in matching_configs:
        curriculum = curricula_by_id.get(cfg.curriculum_id)
        if not curriculum:
            continue
        if _cyt_row_accepts_batch(cfg, batch_value, curriculum, window_id):
            allowed.add(curriculum.id)

    if not allowed:
        for curriculum in Curriculum.query.order_by(Curriculum.name.asc()).all():
            if not _curriculum_accepts_batch(curriculum, batch_value, window_id):
                continue
            cfg = curriculum.get_year_term_config(year, term, window_id=window_id)
            if not cfg:
                continue
            if session_name and str(cfg.academic_session or '').strip() != str(session_name).strip():
                continue
            allowed.add(curriculum.id)

    if allowed:
        names = Curriculum.query.filter(Curriculum.id.in_(allowed)).order_by(Curriculum.name.asc()).all()
        label = ', '.join(c.name for c in names)
    else:
        label = f'No configured curriculum for batch {batch_value}'
    return allowed, label


def _not_running_curriculum_ids(session_name, year, term, window_id=None):
    """Curricula explicitly marked not running for session/year/term."""
    blocked = set()
    for row in _cyt_rows_for_session_year_term(session_name=session_name or None, year=year, term=term):
        if not row.curriculum_id:
            continue
        if row.batch and str(row.batch).strip() and str(row.batch).strip() != 'None':
            continue
        curriculum = Curriculum.query.get(row.curriculum_id)
        if curriculum and curriculum.get_batches_list(window_id=window_id):
            continue
        blocked.add(row.curriculum_id)
    return blocked


def _is_postgraduate_course(course):
    """Detect PG courses even when category was not saved as pg."""
    if not course:
        return False
    if (course.category or '').lower() == 'pg':
        return True
    if _normalize_registration_year(course.derived_year or '') == 'llm':
        return True
    digits = course._extract_year_term_digits() if hasattr(course, '_extract_year_term_digits') else ''
    return bool(digits and len(digits) >= 4 and digits[0] == '5')


def _course_matches_registration_year_term(course, year, term):
    """Match course year/term labels to registration selection, including PG aliases."""
    course_year = course.display_year or course.year or ''
    course_term = course.display_term or course.term or ''
    derived_term = course.derived_term or ''

    term_ok = _registration_terms_match(course_term, term)
    if not term_ok and derived_term:
        term_ok = _registration_terms_match(derived_term, term)
    if not term_ok:
        return False

    if _registration_years_match(course_year, year):
        return True

    if _is_postgraduate_course(course) and _normalize_registration_year(year) == 'llm':
        return True

    return False


def _serialize_registration_course(course, year, term):
    return {
        'id': course.id,
        'course_code': course.course_code,
        'course_name': course.course_name,
        'credit': course.credit,
        'course_type': course.course_type,
        'category': course.category,
        'nature': course.core_optional or 'Core',
        'source_year': year,
        'source_term': term,
    }

def get_available_batches(exclude_curriculum_id=None):
    """Get all distinct batches from Student model.

    Same batch can be used in multiple curricula/syllabus definitions.
    """
    all_batches = db.session.query(Student.batch).distinct().filter(
        Student.batch.isnot(None),
        Student.batch != ''
    ).order_by(Student.batch.desc()).all()
    all_batch_values = [batch[0] for batch in all_batches if batch[0]]
    return [(batch, batch) for batch in all_batch_values]

@course_management_bp.route('/')
@login_required
def index():
    """List all curricula"""
    curricula = Curriculum.query.order_by(Curriculum.created_at.desc()).all()
    curriculum_form = CurriculumForm()
    curriculum_form.applicable_batches.choices = get_available_batches()
    active_window_id = _active_window_id()
    return render_template(
        'course_management/index.html',
        curricula=curricula,
        curriculum_form=curriculum_form,
        active_window_id=active_window_id,
    )

@course_management_bp.route('/curriculum/<int:curriculum_id>')
@login_required
def view_curriculum(curriculum_id):
    """View courses in a specific curriculum"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    active_window_id = _active_window_id()
    courses = Course.query.filter_by(curriculum_id=curriculum_id).order_by('course_code').all()
    course_form = CourseForm()
    curriculum_form = CurriculumForm()
    curriculum_form.applicable_batches.choices = get_available_batches()
    
    # Create edit form for this curriculum
    edit_curriculum_form = CurriculumForm()
    edit_curriculum_form.applicable_batches.choices = get_available_batches(exclude_curriculum_id=curriculum_id)
    # Include batches already assigned to this curriculum (active window)
    existing_batches = curriculum.get_batches_list(window_id=active_window_id)
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
    curriculum_batches = curriculum.get_batches_list(window_id=active_window_id) if curriculum else []
    
    # Get teachers for assignment dropdown (exclude Head of the Discipline)
    teachers = _get_teachers_excluding_head()
    
    # Get existing session assignments for courses
    course_assignments = {}
    teacher_map = {}
    try:
        from .models import CourseSessionAssignment
        assignments = _csa_query().filter_by(
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
    
    # Build year-term session configuration map for UI.
    # Key format keeps lookups simple from Jinja: "<year>|||<term>".
    year_term_configs_map = {}
    try:
        all_configs = _cyt_query().filter_by(curriculum_id=curriculum_id).all()
        for cfg in all_configs:
            config_key = f'{(cfg.year or "").strip()}|||{(cfg.term or "").strip()}'
            parsed_batches = []
            if cfg.batch and cfg.batch.strip():
                parsed_batches = [b.strip() for b in cfg.batch.split(',') if b.strip()]
            year_term_configs_map.setdefault(config_key, []).append({
                'academic_session': (cfg.academic_session or '').strip(),
                'batch': cfg.batch or '',
                'batches': parsed_batches,
                'updated_at': cfg.updated_at.isoformat() if cfg.updated_at else None
            })
    except Exception:
        year_term_configs_map = {}

    active_window_id = _active_window_id()

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
                         teacher_map=teacher_map,
                         year_term_configs_map=year_term_configs_map,
                         active_window_id=active_window_id)

@course_management_bp.route('/curriculum/add', methods=['POST'])
@login_required
def add_curriculum():
    """Add a new curriculum"""
    form = CurriculumForm()
    form.applicable_batches.choices = get_available_batches()
    if form.validate_on_submit():
        new_curriculum = Curriculum(
            name=form.name.data,
            date=form.date.data,
        )
        db.session.add(new_curriculum)
        db.session.flush()
        new_curriculum.set_batches_for_window(
            form.applicable_batches.data or [],
            window_id=_active_window_id(),
        )
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
    active_window_id = _active_window_id()
    form = CurriculumForm()
    form.applicable_batches.choices = get_available_batches(exclude_curriculum_id=curriculum_id)
    
    # Include batches already assigned to this curriculum (active window)
    existing_batches = curriculum.get_batches_list(window_id=active_window_id)
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
            curriculum.name = form.name.data
            curriculum.date = form.date.data
            curriculum.set_batches_for_window(
                form.applicable_batches.data or [],
                window_id=active_window_id,
            )
            
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

@course_management_bp.route('/curriculum/<int:curriculum_id>/clear-assignments', methods=['POST'])
@login_required
def clear_curriculum_assignments(curriculum_id):
    """Clear all teacher assignments for this curriculum (archive linked sessions, then remove assignments)."""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    assignments = _csa_query().filter_by(curriculum_id=curriculum_id).all()
    count = 0
    try:
        for assignment in assignments:
            if assignment.session_id:
                session_obj = Session.query.get(assignment.session_id)
                if session_obj and hasattr(session_obj, 'archived'):
                    if assignment.academic_session and not session_obj.academic_session:
                        session_obj.academic_session = assignment.academic_session
                    session_obj.archived = True
            db.session.delete(assignment)
            count += 1
        db.session.commit()
        flash(f'All assignments cleared. {count} assignment(s) removed.', 'success')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to clear curriculum assignments {curriculum_id}: {exc}', exc_info=True)
        flash('Failed to clear assignments. Please try again.', 'error')
    return redirect(url_for('course_management.view_curriculum', curriculum_id=curriculum_id))


@course_management_bp.route('/curriculum/<int:curriculum_id>/delete', methods=['POST'])
@login_required
def delete_curriculum(curriculum_id):
    """Delete a curriculum and all related courses (with proper cleanup)"""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    curriculum_name = curriculum.name
    
    try:
        # Delete all courses in this curriculum (cascade will handle Course objects,
        # but we need to explicitly handle sessions via CourseSessionAssignment)
        # Since Course has cascade delete, we should iterate and delete courses
        # to ensure proper cleanup of sessions
        
        # Get all courses before deletion
        courses = Course.query.filter_by(curriculum_id=curriculum_id).all()
        
        # Import necessary models for course cleanup
        from blueprints.class_management.models import (
            Session, ClassStudent, ClassAttendance, CourseReview, 
            EvaluationInvite, EvaluationSubmission, StudentFeedbackLink, 
            StudentFeedbackResponse, ClassSplitInvite, CourseOutline
        )
        try:
            from blueprints.academic_calendar.models import BatchCustomEvent
        except ImportError:
            BatchCustomEvent = None
        
        # Delete each course and its related sessions
        for course in courses:
            course_id = course.id
            # Clean up any teacher assignments / sessions tied to this course
            assignments = CourseSessionAssignment.query.filter_by(course_id=course_id).all()
            for assignment in assignments:
                session_obj = Session.query.get(assignment.session_id) if assignment.session_id else None
                if session_obj:
                    session_id = session_obj.id
                    
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
                    db.session.delete(session_obj)
                
                db.session.delete(assignment)
            
            # Detach historical records instead of deleting them
            StudentCourseRegistration.query.filter_by(course_id=course_id).update({'course_id': None})
            DutyAssignment.query.filter_by(course_id=course_id).update({'course_id': None})
        
        # Delete the curriculum (courses will be deleted via cascade, but we've already cleaned up sessions)
        db.session.delete(curriculum)
        db.session.commit()
        flash(f'Curriculum "{curriculum_name}" deleted successfully!', 'success')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to delete curriculum {curriculum_id}: {exc}', exc_info=True)
        flash('Failed to delete curriculum. Please try again.', 'error')
    
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
        db.session.flush()
        new_course.set_offered_for_window(True, window_id=_active_window_id())
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
        
        # Clean up any teacher assignments / sessions tied to this course
        assignments = CourseSessionAssignment.query.filter_by(course_id=course_id).all()
        for assignment in assignments:
            session_obj = Session.query.get(assignment.session_id) if assignment.session_id else None
            if session_obj:
                session_id = session_obj.id
                
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
        
        # Handle Course Contents - check if JSON format or text format
        content_a = request.form.get('content_section_a', '')
        if content_a:
            try:
                # Try to parse as JSON
                content_a_data = json.loads(content_a)
                if isinstance(content_a_data, list):
                    # Store as JSON
                    course.content_section_a = json.dumps(content_a_data)
                else:
                    # Store as text
                    course.content_section_a = content_a
            except (json.JSONDecodeError, TypeError):
                # Not JSON, store as text
                course.content_section_a = content_a if content_a else None
        else:
            course.content_section_a = None
        
        content_b = request.form.get('content_section_b', '')
        if content_b:
            try:
                # Try to parse as JSON
                content_b_data = json.loads(content_b)
                if isinstance(content_b_data, list):
                    # Store as JSON
                    course.content_section_b = json.dumps(content_b_data)
                else:
                    # Store as text
                    course.content_section_b = content_b
            except (json.JSONDecodeError, TypeError):
                # Not JSON, store as text
                course.content_section_b = content_b if content_b else None
        else:
            course.content_section_b = None
        
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
    """Toggle the offered status of a course for the active operational window"""
    try:
        course = Course.query.get_or_404(course_id)
        active_window_id = _active_window_id()
        
        if request.is_json:
            data = request.get_json()
            offered = data.get('offered', True)
        else:
            offered = request.form.get('offered', 'true').lower() == 'true'
        
        course.set_offered_for_window(offered, window_id=active_window_id)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Course {"offered" if offered else "not offered"} status updated successfully',
            'offered': course.is_offered(window_id=active_window_id)
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
    from utils.dashboard_settings import require_student_dashboard_card
    blocked = require_student_dashboard_card('course_registration')
    if blocked:
        return blocked
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        flash('Course registration is available only for student accounts.', 'danger')
        return redirect(url_for('index'))
    
    # Get current student record
    student_record = _get_current_student_record()
    
    # Get distinct academic sessions ONLY from registrations this student has
    if student_record:
        sessions = db.session.query(StudentCourseRegistration.academic_session).distinct().filter(
            StudentCourseRegistration.student_id == student_record.id,
            StudentCourseRegistration.academic_session.isnot(None)
        ).order_by(StudentCourseRegistration.academic_session.desc()).all()
        academic_sessions = [s[0] for s in sessions if s[0]]
    else:
        # If student record not found, show empty list
        academic_sessions = []
    
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
    
    # Supports both legacy keys (year/term) and source keys (source_year/source_term)
    year = request.args.get('source_year', '').strip() or request.args.get('year', '').strip()
    term = request.args.get('source_term', '').strip() or request.args.get('term', '').strip()
    session_name = request.args.get('session', '').strip()
    batch_value = request.args.get('batch', '').strip()
    
    if not year or not term:
        return jsonify({'success': False, 'message': 'Year and Term are required'}), 400

    active_window_id = _active_window_id()

    try:
        not_running_curriculum_ids = _not_running_curriculum_ids(
            session_name, year, term, window_id=active_window_id
        )
    except Exception as e:
        current_app.logger.warning(f'Error checking CurriculumYearTerm not-running filter: {e}', exc_info=True)
        not_running_curriculum_ids = set()

    allowed_curriculum_ids = None
    curriculum_label = ''
    if session_name and batch_value:
        try:
            allowed_curriculum_ids, curriculum_label = _resolve_allowed_curriculum_ids(
                session_name, year, term, batch_value, window_id=active_window_id
            )
        except Exception as e:
            current_app.logger.warning(f'Error resolving curriculum scope by batch: {e}', exc_info=True)
            allowed_curriculum_ids = set()
            curriculum_label = 'Curriculum lookup failed'
    
    # Get offered courses for the active operational window
    if allowed_curriculum_ids is not None:
        base_query = Course.query.filter(Course.curriculum_id.in_(allowed_curriculum_ids))
        if filter_offered_courses:
            courses = filter_offered_courses(base_query, window_id=active_window_id).order_by(Course.course_name.asc()).all()
            if not courses:
                courses = base_query.order_by(Course.course_name.asc()).all()
                current_app.logger.info(
                    f'No offered courses in active window for curricula {allowed_curriculum_ids}; '
                    f'using all {len(courses)} courses from matched curricula'
                )
        else:
            courses = base_query.filter_by(offered=True).order_by(Course.course_name.asc()).all()
            if not courses:
                courses = base_query.order_by(Course.course_name.asc()).all()
    elif filter_offered_courses:
        query = filter_offered_courses(Course.query, window_id=active_window_id)
        courses = query.order_by(Course.course_name.asc()).all()
    else:
        courses = Course.query.filter_by(offered=True).order_by(Course.course_name.asc()).all()
    
    # Filter by year and term
    filtered_courses = []
    allowed_set = allowed_curriculum_ids or set()
    active_not_running = {
        cid for cid in not_running_curriculum_ids
        if cid not in allowed_set
    }
    for c in courses:
        if not _course_matches_registration_year_term(c, year, term):
            continue
        if c.curriculum_id and c.curriculum_id in active_not_running:
            continue
        if allowed_curriculum_ids is not None:
            if not c.curriculum_id or c.curriculum_id not in allowed_curriculum_ids:
                continue
        filtered_courses.append(_serialize_registration_course(c, year, term))

    if not filtered_courses and allowed_curriculum_ids and courses:
        for c in courses:
            if c.curriculum_id not in allowed_curriculum_ids:
                continue
            if c.curriculum_id and c.curriculum_id in active_not_running:
                continue
            if not _is_postgraduate_course(c):
                continue
            course_term = c.display_term or c.term or c.derived_term or ''
            if not _registration_terms_match(course_term, term):
                continue
            filtered_courses.append(_serialize_registration_course(c, year, term))
        if filtered_courses:
            current_app.logger.info(
                f'PG fallback loaded {len(filtered_courses)} course(s) for curricula {allowed_curriculum_ids}'
            )
    
    return jsonify({
        'success': True,
        'courses': filtered_courses,
        'curriculum_label': curriculum_label
    })


@course_management_bp.route('/coordinator/register-student/api/relevant-courses', methods=['GET'])
@login_required
def get_relevant_courses_for_retake():
    """Get relevant-course candidates scoped by selected session/year/term."""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    session_name = request.args.get('session', '').strip()
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()

    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year and Term are required'}), 400

    try:
        # Scope relevant candidates to curricula configured for the selected
        # academic session + year + term.
        configured_year_terms = _cyt_rows_for_session_year_term(session_name, year, term)
        allowed_curriculum_ids = {
            row.curriculum_id
            for row in configured_year_terms
            if row.curriculum_id
        }

        if not allowed_curriculum_ids:
            return jsonify({'success': True, 'courses': []})

        offered_query = Course.query.filter(Course.curriculum_id.in_(allowed_curriculum_ids))
        if filter_offered_courses:
            offered_query = filter_offered_courses(offered_query, window_id=_active_window_id())
        else:
            offered_query = offered_query.filter(Course.offered.is_(True))
        offered_courses = offered_query.order_by(
            Course.course_code.asc(), Course.course_name.asc(), Course.id.asc()
        ).all()
        if not offered_courses:
            offered_courses = Course.query.filter(
                Course.curriculum_id.in_(allowed_curriculum_ids)
            ).order_by(
                Course.course_code.asc(), Course.course_name.asc(), Course.id.asc()
            ).all()

        relevant_candidates = []
        seen_course_codes = set()
        for course in offered_courses:
            if not _course_matches_registration_year_term(course, year, term):
                continue

            normalized_code = (course.course_code or '').strip().lower()
            if normalized_code in seen_course_codes:
                continue
            seen_course_codes.add(normalized_code)

            relevant_candidates.append({
                'id': course.id,
                'course_code': course.course_code,
                'course_name': course.course_name,
                'credit': course.credit,
                'course_type': course.course_type,
                'nature': course.core_optional or 'Core',
                'relevant_academic_session': session_name,
                'relevant_year': year,
                'relevant_term': term,
            })

        return jsonify({'success': True, 'courses': relevant_candidates})
    except Exception as exc:
        current_app.logger.error(f'Failed to load relevant courses: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to load relevant courses'}), 500


@course_management_bp.route('/student/registration/api/year-term', methods=['GET'])
@login_required
def get_year_term_by_session():
    """Get Year and Term options for a given academic session"""
    session_name = request.args.get('session', '').strip()
    
    if not session_name:
        return jsonify({'success': False, 'message': 'Session is required'}), 400
    
    try:
        window_id = _active_window_id()
        # Get distinct Year and Term combinations from Session table for this academic session
        sessions = Session.query.filter(
            Session.academic_session == session_name,
            _window_rows_filter(Session, window_id),
        ).distinct().all()
        
        # Extract unique Year-Term combinations
        year_term_combinations = set()
        for session in sessions:
            if session.year and session.term:
                year_term_combinations.add((session.year, session.term))
        
        # Convert to list of dictionaries
        year_term_list = [{'year': yt[0], 'term': yt[1]} for yt in sorted(year_term_combinations)]
        
        # Also check CurriculumYearTerm for additional combinations
        # IMPORTANT: Only include Year/Term combinations where batch is assigned (NOT NULL/empty/'None')
        curriculum_year_terms = _cyt_query().filter_by(
            academic_session=session_name
        ).filter(
            CurriculumYearTerm.batch.isnot(None),
            CurriculumYearTerm.batch != '',
            CurriculumYearTerm.batch != 'None'
        ).distinct().all()
        
        for cyt in curriculum_year_terms:
            if cyt.year and cyt.term:
                year_term_combinations.add((cyt.year, cyt.term))
        
        # Update the list with all combinations (only those with batch assigned)
        year_term_list = [{'year': yt[0], 'term': yt[1]} for yt in sorted(year_term_combinations)]
        
        return jsonify({
            'success': True,
            'year_term_options': year_term_list,
            'window_id': window_id,
        })
    except Exception as e:
        current_app.logger.error(f'Error getting year-term options: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error fetching year-term options'}), 500

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

    # Return all non-archived registrations so student/head/coordinator views stay in sync.
    reg_query = StudentCourseRegistration.query.filter_by(
        student_id=student_record.id,
        academic_session=session_name,
        year=year,
        term=term
    ).filter(StudentCourseRegistration.status != 'archived')
    
    # Apply active semester filtering (if not admin and filter function available)
    if filter_by_active_semester and not is_admin(current_user):
        # Get batch from student record if available
        batch = None
        if hasattr(student_record, 'batch') and student_record.batch:
            batch = student_record.batch
        reg_query = filter_by_active_semester(reg_query, StudentCourseRegistration, batch=batch, admin_override=False)

    if filter_by_active_window and not is_admin(current_user):
        reg_query = filter_by_active_window(reg_query, StudentCourseRegistration, admin_override=False)
    
    registrations = reg_query.order_by(StudentCourseRegistration.course_code.asc()).all()

    data = [{
        # Keep `id` as course_id for UI compatibility and provide explicit registration_id.
        'id': reg.course_id,
        'registration_id': reg.id,
        'course_id': reg.course_id,
        'course_code': reg.course_code,
        'course_name': reg.course_name,
        'credit': reg.credit,
        'course_type': reg.course_type,
        'nature': reg.nature,
        'remark': reg.remark,
        'source_year': (reg.source_year or reg.year),
        'source_term': (reg.source_term or reg.term),
        'relevant_course_id': reg.relevant_course_id,
        'relevant_course_code': reg.relevant_course_code,
        'relevant_academic_session': reg.relevant_academic_session,
        'relevant_year': reg.relevant_year,
        'relevant_term': reg.relevant_term,
        'use_relevant_for_committee': reg.use_relevant_for_committee if hasattr(reg, 'use_relevant_for_committee') else True,
        'carry_on': reg.carry_on if hasattr(reg, 'carry_on') else False,
        'status': reg.status,
        'registered_by': reg.registered_by if hasattr(reg, 'registered_by') else 'student'
    } for reg in registrations]

    return jsonify({'success': True, 'registrations': data})


@course_management_bp.route('/student/registration/remove-course', methods=['POST'])
@login_required
def student_remove_course():
    """Remove a single course from student registration"""
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json() or {}
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    registration_id = data.get('registration_id')
    
    if not session_name or not year or not term or not registration_id:
        return jsonify({'success': False, 'message': 'Session, Year, Term, and Registration ID are required'}), 400
    
    student_record = _get_current_student_record()
    if not student_record:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404
    
    try:
        # Find the registration
        reg = StudentCourseRegistration.query.filter_by(
            id=registration_id,
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).first()
        
        if not reg:
            return jsonify({'success': False, 'message': 'Registration not found'}), 404
        
        # Check if can be removed (not finalized by coordinator/head)
        if reg.status == 'finalized' or (reg.registered_by and reg.registered_by in ['coordinator', 'head']):
            return jsonify({
                'success': False,
                'message': 'Cannot remove finalized registrations or registrations created by coordinator/head.'
            }), 403
        
        course_code = reg.course_code
        
        # Remove from Class Management if registration was finalized
        if reg.status == 'finalized':
            try:
                _remove_students_from_class_sessions(
                    course_code, session_name, year, term, [student_record.id]
                )
            except Exception as remove_error:
                current_app.logger.error(f'Error removing student from Class Management: {remove_error}', exc_info=True)
        
        # Delete related invites
        invites_to_delete = query_for_window(CourseRegistrationInvite).filter_by(
            registration_id=reg.id
        ).all()
        for invite in invites_to_delete:
            db.session.delete(invite)
        
        # Delete the registration
        db.session.delete(reg)
        db.session.commit()
        
        current_app.logger.info(f'Student {student_record.student_id} removed course {course_code} from registration')
        
        return jsonify({
            'success': True,
            'message': f'Successfully removed {course_code} from registration.'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to remove course from student registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to remove course from registration'}), 500


@course_management_bp.route('/student/registration/remove-all-courses', methods=['POST'])
@login_required
def student_remove_all_courses():
    """Remove all removable courses from student registration (bulk deregister)"""
    roles = parse_roles(current_user.role)
    if 'student' not in roles and 'teaching_assistant' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json() or {}
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    registration_ids = data.get('registration_ids', [])
    
    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400
    
    if not registration_ids or len(registration_ids) == 0:
        return jsonify({'success': False, 'message': 'No registration IDs provided'}), 400
    
    student_record = _get_current_student_record()
    if not student_record:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404
    
    try:
        # Find all registrations
        regs = StudentCourseRegistration.query.filter(
            StudentCourseRegistration.id.in_(registration_ids),
            StudentCourseRegistration.student_id == student_record.id,
            StudentCourseRegistration.academic_session == session_name,
            StudentCourseRegistration.year == year,
            StudentCourseRegistration.term == term
        ).all()
        
        if not regs or len(regs) == 0:
            return jsonify({'success': False, 'message': 'No registrations found'}), 404
        
        # Filter out finalized or coordinator/head registrations
        removable_regs = [reg for reg in regs if reg.status != 'finalized' and (not reg.registered_by or reg.registered_by not in ['coordinator', 'head'])]
        
        if not removable_regs:
            return jsonify({
                'success': False,
                'message': 'No courses can be removed. All courses are finalized or created by coordinator/head.'
            }), 403
        
        course_codes = []
        
        # Remove from Class Management if registrations were finalized (shouldn't happen, but just in case)
        for reg in removable_regs:
            if reg.status == 'finalized':
                try:
                    _remove_students_from_class_sessions(
                        reg.course_code, session_name, year, term, [student_record.id]
                    )
                except Exception as remove_error:
                    current_app.logger.error(f'Error removing student from Class Management for course {reg.course_code}: {remove_error}', exc_info=True)
            
            course_codes.append(reg.course_code)
            
            # Delete related invites
            invites_to_delete = query_for_window(CourseRegistrationInvite).filter_by(
                registration_id=reg.id
            ).all()
            for invite in invites_to_delete:
                db.session.delete(invite)
            
            # Delete the registration
            db.session.delete(reg)
        
        db.session.commit()
        
        current_app.logger.info(f'Student {student_record.student_id} removed {len(removable_regs)} course(s) from registration: {course_codes}')
        
        return jsonify({
            'success': True,
            'message': f'Successfully removed {len(removable_regs)} course(s) from registration.'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to remove all courses from student registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to remove courses from registration'}), 500


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

    reg_window_id = get_effective_window_id(admin_override=False) if get_effective_window_id else None

    if not courses:
        return jsonify({'success': False, 'message': 'No courses selected'}), 400

    student_record = _get_current_student_record()
    if not student_record:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404

    try:
        # Get existing registrations to preserve carry_on flags if needed
        existing_regs = StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()
        existing_carry_on = {reg.course_code: getattr(reg, 'carry_on', False) for reg in existing_regs}
        existing_use_relevant_for_committee = {
            reg.course_code: getattr(reg, 'use_relevant_for_committee', True) for reg in existing_regs
        }
        
        # If coordinator/head already created or finalized registrations, student cannot edit those
        coordinator_registrations = [reg for reg in existing_regs if reg.registered_by in ['coordinator', 'head'] or reg.status == 'finalized']
        if coordinator_registrations:
            return jsonify({
                'success': False, 
                'message': 'Cannot edit finalized registrations or registrations created by coordinator/head. Please contact your coordinator for changes.'
            }), 403
        
        # Get existing registrations before deletion to remove from Class Management
        existing_regs_to_delete = StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).all()
        
        # Track finalized registrations so class entries can be removed from their actual target context.
        finalized_regs_to_remove = [reg for reg in existing_regs_to_delete if reg.status == 'finalized']
        
        # Delete existing registrations (only student-initiated ones)
        StudentCourseRegistration.query.filter_by(
            student_id=student_record.id,
            academic_session=session_name,
            year=year,
            term=term
        ).delete()
        
        # Remove students from Class Management for deleted finalized registrations
        for reg in finalized_regs_to_remove:
            try:
                class_target = _resolve_class_target_context(
                    reg,
                    fallback_course_code=reg.course_code,
                    fallback_session=session_name,
                    fallback_year=year,
                    fallback_term=term
                )
                _remove_students_from_class_sessions(
                    class_target['course_code'],
                    class_target['academic_session'],
                    class_target['year'],
                    class_target['term'],
                    [student_record.id]
                )
            except Exception as remove_error:
                current_app.logger.error(f'Error removing students from Class Management: {remove_error}', exc_info=True)

        for course in courses:
            # Students' own registrations are FINAL
            status = 'finalized'
            registered_by = 'student'
            # Keep carry_on fallback from any prior draft if not provided
            carry_on_val = course.get('carry_on', existing_carry_on.get(course.get('course_code', ''), False))
            remark_value = str(course.get('remark', 'Regular') or 'Regular').strip() or 'Regular'
            is_retake = _is_retake_remark(remark_value)
            normalized_source_year, normalized_source_term = _normalize_source_year_term(
                course.get('source_year'),
                course.get('source_term'),
                year,
                term
            )
            relevant_mapping = _normalize_relevant_course_mapping(
                course,
                default_year=normalized_source_year,
                default_term=normalized_source_term
            )
            if not is_retake:
                relevant_mapping = _normalize_relevant_course_mapping({})
            use_relevant_for_committee = _resolve_use_relevant_for_committee(
                course.get('use_relevant_for_committee'),
                is_retake,
                existing_value=existing_use_relevant_for_committee.get(course.get('course_code', ''))
            )
                        
            reg = StudentCourseRegistration(
                student_id=student_record.id,
                course_id=course.get('id'),
                window_id=reg_window_id,
                academic_session=session_name,
                year=year,
                term=term,
                source_year=normalized_source_year,
                source_term=normalized_source_term,
                course_code=course.get('course_code', ''),
                course_name=course.get('course_name', ''),
                credit=course.get('credit', 0),
                course_type=course.get('course_type', ''),
                nature=course.get('nature', 'Core'),
                remark=remark_value,
                carry_on=carry_on_val,
                relevant_course_id=relevant_mapping['relevant_course_id'],
                relevant_course_code=relevant_mapping['relevant_course_code'],
                relevant_academic_session=relevant_mapping['relevant_academic_session'],
                relevant_year=relevant_mapping['relevant_year'],
                relevant_term=relevant_mapping['relevant_term'],
                use_relevant_for_committee=use_relevant_for_committee,
                status=status,
                registered_by=registered_by
            )
            db.session.add(reg)

        db.session.commit()
        
        # Add this student to Class Management for each finalized registration (fresh set)
        try:
            for course in courses:
                class_target = _resolve_class_target_context(
                    course,
                    fallback_course_code=course.get('course_code', ''),
                    fallback_session=session_name,
                    fallback_year=year,
                    fallback_term=term
                )
                _add_students_to_class_sessions(
                    course_code=course.get('course_code', ''),
                    academic_session=session_name,
                    year=year,
                    term=term,
                    students_data=[{
                        'student_id': student_record.id,
                        'carry_on': course.get('carry_on', False),
                        'target_course_code': class_target['course_code'],
                        'target_academic_session': class_target['academic_session'],
                        'target_year': class_target['year'],
                        'target_term': class_target['term'],
                    }]
                )
        except Exception as session_error:
            current_app.logger.warning(f'Failed to add student to Class Management (student flow): {session_error}', exc_info=True)
            # Do not fail the response if session addition fails
        
        return jsonify({'success': True, 'message': 'Registration saved and finalized successfully.'})
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
        pdf_data = buffer.getvalue()
        
        filename = f'course_registration_{student_id}_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        # Use Response instead of send_file for better cPanel compatibility
        from flask import Response
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
        coordinator_assignment = filter_by_active_window(
            DutyAssignment.query.filter(
                DutyAssignment.duty_type == 'course_coordinator',
                DutyAssignment.status == 'active',
                DutyAssignment.batch == student_record.batch,
                DutyAssignment.assigned_teacher_id.isnot(None)
            ),
            DutyAssignment,
        ).order_by(DutyAssignment.created_at.desc()).first()

        if coordinator_assignment and coordinator_assignment.assigned_teacher:
            coordinator_teacher = coordinator_assignment.assigned_teacher
        else:
            # Fallback to legacy assignments without batch
            legacy_assignment = filter_by_active_window(
                DutyAssignment.query.filter(
                    DutyAssignment.duty_type == 'course_coordinator',
                    DutyAssignment.status == 'active',
                    or_(DutyAssignment.batch.is_(None), DutyAssignment.batch == ''),
                    DutyAssignment.assigned_teacher_id.isnot(None)
                ),
                DutyAssignment,
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
            existing_invites = query_for_window(CourseRegistrationInvite).filter_by(
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
                if stamp_window_id:
                    stamp_window_id(invite, window_id=reg.window_id)
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
    """View course registrations as coordinator with session/batch filters"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        flash('This page is available only for coordinators.', 'danger')
        return redirect(url_for('index'))

    # Get current teacher profile
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        flash('Teacher profile not found.', 'warning')
        return redirect(url_for('index'))

    # Get filter parameters; persist in session so redirects (e.g. after actions) keep the same selection
    if 'session' in request.args or 'batch' in request.args or 'student_id' in request.args:
        session_filter = request.args.get('session', '').strip()
        batch_filter = request.args.get('batch', '').strip()
        student_id_filter = request.args.get('student_id', type=int)
        session['coordinator_registrations_session'] = session_filter
        session['coordinator_registrations_batch'] = batch_filter
        session['coordinator_registrations_student_id'] = student_id_filter
    else:
        session_filter = session.get('coordinator_registrations_session', '')
        batch_filter = session.get('coordinator_registrations_batch', '')
        student_id_filter = session.get('coordinator_registrations_student_id')

    # Get pending invites for this coordinator (always show, even without filters)
    # Exclude invites for archived registrations
    pending_invites_query = query_for_window(CourseRegistrationInvite).filter_by(
        status='pending',
        coordinator_teacher_id=teacher.id
    ).join(StudentCourseRegistration).filter(
        StudentCourseRegistration.status != 'archived'
    )
    
    # Apply filters to pending invites if provided
    if session_filter:
        pending_invites_query = pending_invites_query.filter(
            StudentCourseRegistration.academic_session == session_filter
        )
    if batch_filter and Student:
        batch_student_ids = [s.id for s in Student.query.filter_by(batch=batch_filter).all()]
        if batch_student_ids:
            pending_invites_query = pending_invites_query.filter(CourseRegistrationInvite.student_id.in_(batch_student_ids))
        else:
            pending_invites_query = pending_invites_query.filter(CourseRegistrationInvite.student_id == -1)
    if student_id_filter:
        pending_invites_query = pending_invites_query.filter_by(student_id=student_id_filter)
    
    pending_invites = pending_invites_query.order_by(CourseRegistrationInvite.created_at.desc()).all()
    
    # Only show finalized registrations if at least one filter is applied
    # Coordinators can see ALL finalized registrations (same as Head)
    # Get finalized registrations directly - this ensures all finalized registrations are visible
    finalized_regs = []
    if session_filter or batch_filter or student_id_filter:
        reg_query = StudentCourseRegistration.query.filter_by(
            status='finalized'
        )
        
        # Head/Dean (and admin) review ALL finalized registrations, so they must
        # not be limited to the currently active semester/operational window —
        # otherwise past or other-window registrations show "No finalized
        # registrations found" even though they exist. The explicit
        # session/batch/student filters below already scope the results.
        can_view_all_registrations = (
            is_admin(current_user) or 'head' in roles or 'dean' in roles
        )

        # Apply active semester filtering (if not privileged and filter function available)
        if filter_by_active_semester and not can_view_all_registrations:
            batch_for_filter = batch_filter if batch_filter else None
            reg_query = filter_by_active_semester(reg_query, StudentCourseRegistration, batch=batch_for_filter, admin_override=False)

        if filter_by_active_window and not can_view_all_registrations:
            reg_query = filter_by_active_window(reg_query, StudentCourseRegistration, admin_override=False)
        
        # Apply filters to registrations
        if session_filter:
            reg_query = reg_query.filter(StudentCourseRegistration.academic_session == session_filter)
        if batch_filter and Student:
            batch_student_ids = [s.id for s in Student.query.filter_by(batch=batch_filter).all()]
            if batch_student_ids:
                reg_query = reg_query.filter(StudentCourseRegistration.student_id.in_(batch_student_ids))
            else:
                reg_query = reg_query.filter(StudentCourseRegistration.student_id == -1)
        if student_id_filter:
            reg_query = reg_query.filter_by(student_id=student_id_filter)
        
        finalized_regs = reg_query.order_by(StudentCourseRegistration.id.desc()).all()

    # Group pending invites by student/session/year/term
    pending_by_student = {}
    for invite in pending_invites:
        reg = invite.registration
        if reg:
            key = (reg.student_id, reg.academic_session, reg.year, reg.term)
            if key not in pending_by_student:
                pending_by_student[key] = {
                    'student': reg.student,
                    'session': reg.academic_session,
                    'year': reg.year,
                    'term': reg.term,
                    'registrations': [],
                    'registration_ids': set(),
                    'invite_ids': []
                }
            entry = pending_by_student[key]
            if reg.id not in entry['registration_ids']:
                entry['registrations'].append(reg)
                entry['registration_ids'].add(reg.id)
            pending_by_student[key]['invite_ids'].append(invite.id)
    
    # Group finalized registrations by student/session/year/term
    finalized_by_student = {}
    for reg in finalized_regs:
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
        
        # Get invite IDs for this registration if any exist
        invites_for_reg = query_for_window(CourseRegistrationInvite).filter_by(
            registration_id=reg.id,
            status='finalized'
        ).all()
        for invite in invites_for_reg:
            if invite.id not in entry['invite_ids']:
                entry['invite_ids'].append(invite.id)

    # Get distinct sessions and batches for filters (window-scoped)
    window_id = _active_window_id()
    sessions = db.session.query(Session.academic_session).distinct().filter(
        Session.academic_session.isnot(None),
        _window_rows_filter(Session, window_id),
    ).order_by(Session.academic_session.desc()).all()
    academic_sessions = [s[0] for s in sessions if s[0]]

    # Also include sessions from registrations in this window (covers edge cases)
    reg_sessions = db.session.query(StudentCourseRegistration.academic_session).distinct().filter(
        StudentCourseRegistration.academic_session.isnot(None),
        StudentCourseRegistration.status != 'archived',
        _window_rows_filter(StudentCourseRegistration, window_id),
    ).all()
    for row in reg_sessions:
        if row[0] and row[0] not in academic_sessions:
            academic_sessions.append(row[0])
    academic_sessions = sorted(academic_sessions, reverse=True)
    
    batches = []
    if Student:
        batches = db.session.query(Student.batch).distinct().filter(
            Student.batch.isnot(None),
            Student.batch != ''
        ).order_by(Student.batch.desc()).all()
        batch_list = [b[0] for b in batches if b[0]]
    else:
        batch_list = []
    
    # Get students for dropdown (filtered by session/batch if provided)
    students_query = Student.query
    if batch_filter:
        students_query = students_query.filter_by(batch=batch_filter)
    students = students_query.order_by(Student.student_id.asc()).limit(500).all()

    can_course_wise_review = is_admin(current_user) or 'head' in roles or 'dean' in roles

    return render_template('course_management/coordinator_registrations.html',
                         pending_registrations=pending_by_student,
                         finalized_registrations=finalized_by_student,
                         academic_sessions=academic_sessions,
                         batches=batch_list,
                         students=students,
                         selected_session=session_filter,
                         selected_batch=batch_filter,
                         selected_student_id=student_id_filter,
                         can_course_wise_review=can_course_wise_review,
                         active_window_id=window_id)


@course_management_bp.route('/coordinator/registrations/api/course-subjects', methods=['GET'])
@login_required
def get_course_subjects_for_registration_review():
    """List subjects with registrations for course-wise review (Head/Dean)."""
    roles = parse_roles(current_user.role)
    if not (is_admin(current_user) or 'head' in roles or 'dean' in roles):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    session_name = request.args.get('session', '').strip()
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()

    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400

    try:
        window_id = _active_window_id()
        rows = db.session.query(
            StudentCourseRegistration.student_id,
            StudentCourseRegistration.course_code,
            StudentCourseRegistration.course_name,
            StudentCourseRegistration.course_id,
            StudentCourseRegistration.remark,
            StudentCourseRegistration.relevant_course_code,
            StudentCourseRegistration.relevant_course_id,
            StudentCourseRegistration.use_relevant_for_committee,
        ).filter(
            StudentCourseRegistration.academic_session == session_name,
            StudentCourseRegistration.year == year,
            StudentCourseRegistration.term == term,
            StudentCourseRegistration.status != 'archived',
            _window_rows_filter(StudentCourseRegistration, window_id),
        ).all()

        subjects_map = {}

        def _track_subject(code, name, course_id, student_id):
            code_key = _course_code_lookup_key(code)
            if not code_key or not student_id:
                return
            entry = subjects_map.get(code_key)
            if not entry:
                entry = {
                    'course_code': (code or '').strip(),
                    'course_name': (name or code or '').strip(),
                    'course_id': course_id,
                    'student_ids': set(),
                }
                subjects_map[code_key] = entry
            else:
                if name and len(name) > len(entry['course_name'] or ''):
                    entry['course_name'] = name.strip()
                if course_id and not entry['course_id']:
                    entry['course_id'] = course_id
            entry['student_ids'].add(student_id)

        for row in rows:
            _track_subject(row.course_code, row.course_name, row.course_id, row.student_id)

            relevant_code = (row.relevant_course_code or '').strip()
            if (
                _is_retake_remark(row.remark)
                and relevant_code
                and _course_code_lookup_key(relevant_code) != _course_code_lookup_key(row.course_code)
            ):
                _track_subject(
                    relevant_code,
                    relevant_code,
                    row.relevant_course_id,
                    row.student_id
                )

        if subjects_map:
            course_name_lookup = {}
            course_keys = list(subjects_map.keys())
            matched_courses = Course.query.filter(
                _collapsed_course_code_column(Course.course_code).in_(course_keys)
            ).order_by(Course.id.desc()).all()
            for course in matched_courses:
                key = _course_code_lookup_key(course.course_code)
                if key and key not in course_name_lookup:
                    course_name_lookup[key] = course

            for code_key, entry in subjects_map.items():
                matched = course_name_lookup.get(code_key)
                if matched:
                    if not entry['course_id']:
                        entry['course_id'] = matched.id
                    if entry['course_name'] == entry['course_code'] or not entry['course_name']:
                        entry['course_name'] = matched.course_name or entry['course_code']

        subjects = [{
            'course_code': entry['course_code'],
            'course_name': entry['course_name'],
            'course_id': entry['course_id'],
            'registration_count': len(entry['student_ids']),
        } for entry in subjects_map.values()]
        subjects.sort(key=lambda item: item['course_code'])

        return jsonify({
            'success': True,
            'subjects': subjects,
            'window_id': window_id,
        })
    except Exception as exc:
        current_app.logger.error(f'Error fetching course subjects for review: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error fetching subjects'}), 500


@course_management_bp.route('/coordinator/registrations/api/course-wise', methods=['GET'])
@login_required
def get_course_wise_registrations():
    """Get registered students for a specific course (Head/Dean course-wise review)."""
    roles = parse_roles(current_user.role)
    if not (is_admin(current_user) or 'head' in roles or 'dean' in roles):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    session_name = request.args.get('session', '').strip()
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()
    course_code = request.args.get('course_code', '').strip()

    if not session_name or not year or not term or not course_code:
        return jsonify({'success': False, 'message': 'Session, Year, Term, and Course are required'}), 400

    try:
        window_id = _active_window_id()
        scope_filter, course_code_key = _registration_course_filter(
            course_code, session_name, year, term
        )
        rows = db.session.query(
            StudentCourseRegistration, Student
        ).join(
            Student, Student.id == StudentCourseRegistration.student_id
        ).options(
            noload(StudentCourseRegistration.relevant_course),
            noload(StudentCourseRegistration.course),
        ).filter(
            scope_filter,
            _window_rows_filter(StudentCourseRegistration, window_id),
        ).order_by(
            Student.student_id.asc(),
            StudentCourseRegistration.id.asc()
        ).all()

        students = []
        regs = []
        for reg, student in rows:
            regs.append(reg)
            students.append(_serialize_course_wise_registration(reg, student, course_code_key))

        course_info = {}
        if regs:
            first = regs[0]
            course_info = {
                'course_id': first.course_id,
                'course_code': first.course_code,
                'course_name': first.course_name,
                'credit': first.credit,
                'course_type': first.course_type,
                'nature': first.nature or 'Core',
            }
        else:
            matched_course = Course.query.filter(
                _collapsed_course_code_column(Course.course_code) == course_code_key
            ).order_by(Course.id.desc()).first()
            if matched_course:
                course_info = {
                    'course_id': matched_course.id,
                    'course_code': matched_course.course_code,
                    'course_name': matched_course.course_name,
                    'credit': matched_course.credit,
                    'course_type': matched_course.course_type,
                    'nature': matched_course.core_optional or 'Core',
                }
            else:
                course_info = {
                    'course_id': None,
                    'course_code': course_code,
                    'course_name': '',
                    'credit': 0,
                    'course_type': '',
                    'nature': 'Core',
                }

        return jsonify({
            'success': True,
            'session': session_name,
            'year': year,
            'term': term,
            'course': course_info,
            'students': students,
            'count': len(students),
            'window_id': window_id,
        })
    except Exception as exc:
        current_app.logger.error(f'Error fetching course-wise registrations: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': f'Error fetching registrations: {exc}'}), 500


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
    # Get all registrations (both pending and finalized) for coordinator to review
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
        'source_year': (reg.source_year or reg.year),
        'source_term': (reg.source_term or reg.term),
        'relevant_course_id': reg.relevant_course_id,
        'relevant_course_code': reg.relevant_course_code,
        'relevant_academic_session': reg.relevant_academic_session,
        'relevant_year': reg.relevant_year,
        'relevant_term': reg.relevant_term,
        'use_relevant_for_committee': reg.use_relevant_for_committee if hasattr(reg, 'use_relevant_for_committee') else True,
        'carry_on': reg.carry_on if hasattr(reg, 'carry_on') else False,
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


@course_management_bp.route('/coordinator/registration/remove-all-courses', methods=['POST'])
@login_required
def remove_all_courses_from_registration():
    """Remove all courses from student registration (bulk deregister)"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json() or {}
    student_id = data.get('student_id')
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    registration_ids = data.get('registration_ids', [])
    
    if not student_id or not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Student ID, Session, Year, and Term are required'}), 400

    if not registration_ids or len(registration_ids) == 0:
        return jsonify({'success': False, 'message': 'No registration IDs provided'}), 400
    
    try:
        # Find all registrations
        regs = StudentCourseRegistration.query.filter(
            StudentCourseRegistration.id.in_(registration_ids),
            StudentCourseRegistration.student_id == student_id,
            StudentCourseRegistration.academic_session == session_name,
            StudentCourseRegistration.year == year,
            StudentCourseRegistration.term == term
        ).all()
        
        if not regs or len(regs) == 0:
            return jsonify({'success': False, 'message': 'No registrations found'}), 404
        
        course_codes = []
        student_ids_to_remove = []
        
        # Remove from Class Management if registrations were finalized
        finalized_regs = [reg for reg in regs if reg.status == 'finalized']
        if finalized_regs:
            # Remove from Class Management using each registration's target context.
            for reg in finalized_regs:
                try:
                    class_target = _resolve_class_target_context(
                        reg,
                        fallback_course_code=reg.course_code,
                        fallback_session=session_name,
                        fallback_year=year,
                        fallback_term=term
                    )
                    _remove_students_from_class_sessions(
                        class_target['course_code'],
                        class_target['academic_session'],
                        class_target['year'],
                        class_target['term'],
                        [reg.student_id]
                    )
                except Exception as remove_error:
                    current_app.logger.error(f'Error removing students from Class Management for course {reg.course_code}: {remove_error}', exc_info=True)
        
        # Delete related invites and registrations
        for reg in regs:
            course_codes.append(reg.course_code)
            
            # Delete related invites
            invites_to_delete = query_for_window(CourseRegistrationInvite).filter_by(
                registration_id=reg.id
            ).all()
            for invite in invites_to_delete:
                db.session.delete(invite)
            
            # Delete the registration
            db.session.delete(reg)
        
        db.session.commit()
        
        current_app.logger.info(f'Removed all {len(regs)} course(s) from student {student_id} registration: {course_codes}')
        
        return jsonify({
            'success': True,
            'message': f'Successfully deregistered all {len(regs)} course(s) from registration.'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to remove all courses from registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to remove all courses from registration'}), 500


@course_management_bp.route('/coordinator/registration/remove-course', methods=['POST'])
@login_required
def remove_course_from_registration():
    """Remove a single course from student registration (instant deregister)"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json() or {}
    student_id = data.get('student_id')
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    registration_id = data.get('registration_id')
    
    if not student_id or not session_name or not year or not term or not registration_id:
        return jsonify({'success': False, 'message': 'Student ID, Session, Year, Term, and Registration ID are required'}), 400
    
    try:
        # Find the registration
        reg = StudentCourseRegistration.query.filter_by(
            id=registration_id,
            student_id=student_id,
            academic_session=session_name,
            year=year,
            term=term
        ).first()
        
        if not reg:
            return jsonify({'success': False, 'message': 'Registration not found'}), 404
        
        course_code = reg.course_code
        
        # Remove from Class Management if registration was finalized
        if reg.status == 'finalized':
            try:
                class_target = _resolve_class_target_context(
                    reg,
                    fallback_course_code=course_code,
                    fallback_session=session_name,
                    fallback_year=year,
                    fallback_term=term
                )
                _remove_students_from_class_sessions(
                    class_target['course_code'],
                    class_target['academic_session'],
                    class_target['year'],
                    class_target['term'],
                    [student_id]
                )
            except Exception as remove_error:
                current_app.logger.error(f'Error removing student from Class Management: {remove_error}', exc_info=True)
        
        # Delete related invites
        invites_to_delete = query_for_window(CourseRegistrationInvite).filter_by(
            registration_id=reg.id
        ).all()
        for invite in invites_to_delete:
            db.session.delete(invite)
        
        # Delete the registration
        db.session.delete(reg)
        db.session.commit()
        
        current_app.logger.info(f'Removed course {course_code} from student {student_id} registration')
        
        return jsonify({
            'success': True,
            'message': f'Successfully removed {course_code} from registration.'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to remove course from registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to remove course from registration'}), 500


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

    current_app.logger.info(f'Registration update request: student_id={student_id}, session={session_name}, year={year}, term={term}, courses_count={len(courses)}, user={current_user.username}, roles={roles}')

    if not student_id or not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Student ID, Session, Year, and Term are required'}), 400

    reg_window_id = get_effective_window_id(admin_override=False) if get_effective_window_id else None

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

        # Head and Coordinator updates keep finalized status (coordinators have same power as Head)
        is_head = 'head' in roles
        is_coordinator = 'teacher' in roles or 'dean' in roles
        # Check if this is a finalization request (from pending invite)
        finalize_request = data.get('finalize', False)
        # Both Head and Coordinators can finalize registrations
        # If finalize_request is True, always finalize (coordinator is finalizing a pending invite)
        update_status = 'finalized' if (is_head or is_coordinator or finalize_request) else 'pending'
        
        for course in courses:
            course_code = course.get('course_code', '')
            if course_code in existing_codes:
                # Update existing
                reg = existing_codes[course_code]
                reg.course_name = course.get('course_name', reg.course_name)
                reg.credit = course.get('credit', reg.credit)
                reg.course_type = course.get('course_type', reg.course_type)
                reg.nature = course.get('nature', reg.nature)
                remark_value = str(course.get('remark', reg.remark) or 'Regular').strip() or 'Regular'
                is_retake = _is_retake_remark(remark_value)
                reg.remark = remark_value
                normalized_source_year, normalized_source_term = _normalize_source_year_term(
                    course.get('source_year'),
                    course.get('source_term'),
                    year,
                    term
                )
                relevant_mapping = _normalize_relevant_course_mapping(
                    course,
                    default_year=normalized_source_year,
                    default_term=normalized_source_term
                )
                if not is_retake:
                    relevant_mapping = _normalize_relevant_course_mapping({})
                use_relevant_for_committee = _resolve_use_relevant_for_committee(
                    course.get('use_relevant_for_committee'),
                    is_retake,
                    existing_value=reg.use_relevant_for_committee
                )
                reg.source_year = normalized_source_year
                reg.source_term = normalized_source_term
                reg.relevant_course_id = relevant_mapping['relevant_course_id']
                reg.relevant_course_code = relevant_mapping['relevant_course_code']
                reg.relevant_academic_session = relevant_mapping['relevant_academic_session']
                reg.relevant_year = relevant_mapping['relevant_year']
                reg.relevant_term = relevant_mapping['relevant_term']
                reg.use_relevant_for_committee = use_relevant_for_committee
                # Update carry_on if provided
                if 'carry_on' in course:
                    reg.carry_on = course.get('carry_on', False)
                # Keep finalized status if Head/Coordinator or if finalizing
                was_finalized = reg.status == 'finalized'
                if is_head or is_coordinator or finalize_request:
                    reg.status = 'finalized'
                    # When coordinator finalizes, keep registered_by as 'student' if it was student-initiated
                    # Don't change registered_by if it was already set
                    if not reg.registered_by:
                        reg.registered_by = 'student'
                else:
                    reg.status = 'pending'
                updated_codes.add(course_code)
                
                # If status changed from non-finalized to finalized, add to Class Management
                if (is_head or is_coordinator or finalize_request) and not was_finalized:
                    # Will be handled after commit
                    pass
            else:
                # Create new
                # If finalizing a pending invite, keep registered_by as 'student'
                # Otherwise, set based on who is creating
                if finalize_request:
                    registered_by = 'student'  # Student initiated, coordinator is finalizing
                else:
                    registered_by = 'head' if is_head else 'coordinator'
                normalized_source_year, normalized_source_term = _normalize_source_year_term(
                    course.get('source_year'),
                    course.get('source_term'),
                    year,
                    term
                )
                remark_value = str(course.get('remark', 'Regular') or 'Regular').strip() or 'Regular'
                is_retake = _is_retake_remark(remark_value)
                relevant_mapping = _normalize_relevant_course_mapping(
                    course,
                    default_year=normalized_source_year,
                    default_term=normalized_source_term
                )
                if not is_retake:
                    relevant_mapping = _normalize_relevant_course_mapping({})
                use_relevant_for_committee = _resolve_use_relevant_for_committee(
                    course.get('use_relevant_for_committee'),
                    is_retake
                )
                reg = StudentCourseRegistration(
                    student_id=student_id,
                    course_id=course.get('course_id'),
                    window_id=reg_window_id,
                    academic_session=session_name,
                    year=year,
                    term=term,
                    source_year=normalized_source_year,
                    source_term=normalized_source_term,
                    course_code=course_code,
                    course_name=course.get('course_name', ''),
                    credit=course.get('credit', 0),
                    course_type=course.get('course_type', ''),
                    nature=course.get('nature', 'Core'),
                    remark=remark_value,
                    carry_on=course.get('carry_on', False),
                    relevant_course_id=relevant_mapping['relevant_course_id'],
                    relevant_course_code=relevant_mapping['relevant_course_code'],
                    relevant_academic_session=relevant_mapping['relevant_academic_session'],
                    relevant_year=relevant_mapping['relevant_year'],
                    relevant_term=relevant_mapping['relevant_term'],
                    use_relevant_for_committee=use_relevant_for_committee,
                    status=update_status,
                    registered_by=registered_by
                )
                db.session.add(reg)
                updated_codes.add(course_code)

        # Delete removed courses
        for code, reg in existing_codes.items():
            if code not in updated_codes:
                # Remove from Class Management if registration was finalized
                if reg.status == 'finalized':
                    try:
                        class_target = _resolve_class_target_context(
                            reg,
                            fallback_course_code=reg.course_code,
                            fallback_session=session_name,
                            fallback_year=year,
                            fallback_term=term
                        )
                        _remove_students_from_class_sessions(
                            class_target['course_code'],
                            class_target['academic_session'],
                            class_target['year'],
                            class_target['term'],
                            [student_id]
                        )
                    except Exception as remove_error:
                        current_app.logger.error(f'Error removing student from Class Management: {remove_error}', exc_info=True)
                
                # Delete related invites before deleting registration
                invites_to_delete = query_for_window(CourseRegistrationInvite).filter_by(
                    registration_id=reg.id
                ).all()
                for invite in invites_to_delete:
                    db.session.delete(invite)
                
                db.session.delete(reg)
        
        # Update invite status if Head or Coordinator (both can finalize)
        # Also update if finalizing a pending invite
        if is_head or is_coordinator or finalize_request:
            # Get all registration IDs for this student/session/year/term (after updates/deletes)
            all_regs = StudentCourseRegistration.query.filter_by(
                student_id=student_id,
                academic_session=session_name,
                year=year,
                term=term
            ).all()
            reg_ids = [reg.id for reg in all_regs]
            
            if reg_ids:
                # Update invites to finalized if registrations exist
                # For coordinators finalizing pending invites, update their own invites
                # For Head, update all invites for these registrations
                if is_head:
                    # Head can update all invites
                    invites = query_for_window(CourseRegistrationInvite).filter(
                        CourseRegistrationInvite.registration_id.in_(reg_ids)
                    ).all()
                else:
                    # Coordinator updates/create invites for themselves (especially when finalizing pending)
                    invites = query_for_window(CourseRegistrationInvite).filter(
                        CourseRegistrationInvite.registration_id.in_(reg_ids),
                        CourseRegistrationInvite.coordinator_teacher_id == teacher.id
                    ).all()
                
                # Update existing invites
                for invite in invites:
                    invite.status = 'finalized'
                    if not invite.responded_at:
                        invite.responded_at = datetime.utcnow()
                
                # For coordinators, create invites if they don't exist (when finalizing)
                if (is_coordinator and not is_head) or finalize_request:
                    existing_invite_reg_ids = {inv.registration_id for inv in invites}
                    for reg_id in reg_ids:
                        if reg_id not in existing_invite_reg_ids:
                            # Create new invite for this coordinator
                            reg = StudentCourseRegistration.query.get(reg_id)
                            if reg:
                                new_invite = CourseRegistrationInvite(
                                    registration_id=reg_id,
                                    student_id=student_id,
                                    coordinator_teacher_id=teacher.id,
                                    status='finalized',
                                    responded_at=datetime.utcnow()
                                )
                                if stamp_window_id:
                                    stamp_window_id(new_invite, window_id=reg.window_id if reg else None)
                                db.session.add(new_invite)
            else:
                # If all registrations are deleted, find and delete related invites
                if is_head:
                    # Head can delete all invites for this student/session/year/term
                    invites = query_for_window(CourseRegistrationInvite).join(StudentCourseRegistration).filter(
                        StudentCourseRegistration.student_id == student_id,
                        StudentCourseRegistration.academic_session == session_name,
                        StudentCourseRegistration.year == year,
                        StudentCourseRegistration.term == term
                    ).all()
                else:
                    # Coordinator deletes only their own invites
                    invites = query_for_window(CourseRegistrationInvite).filter_by(
                        student_id=student_id,
                        coordinator_teacher_id=teacher.id
                    ).all()
                
                # Filter invites that match the session/year/term by checking their registration
                invites_to_delete = []
                for invite in invites:
                    reg = StudentCourseRegistration.query.get(invite.registration_id)
                    if reg and reg.academic_session == session_name and reg.year == year and reg.term == term:
                        invites_to_delete.append(invite)
                
                # Delete invites if all registrations are removed
                for invite in invites_to_delete:
                    db.session.delete(invite)

        db.session.commit()
        
        # Add students to Class Management for finalized registrations (Head and Coordinator updates are automatically finalized)
        if is_head or is_coordinator:
            try:
                # Get all finalized registrations after commit
                finalized_regs = StudentCourseRegistration.query.filter_by(
                    student_id=student_id,
                    academic_session=session_name,
                    year=year,
                    term=term,
                    status='finalized'
                ).all()
                
                # Get student record to ensure it exists
                student = Student.query.get(student_id)
                if not student:
                    current_app.logger.warning(f'Student with id {student_id} not found for Class Management addition')
                    # Don't return, continue to log the issue
                else:
                    current_app.logger.info(f'Found student: {student.student_id} ({student.name}) for Class Management addition')
                
                if not finalized_regs:
                    current_app.logger.warning(f'No finalized registrations found for student {student_id}, session {session_name}, year {year}, term {term}')
                else:
                    current_app.logger.info(f'Found {len(finalized_regs)} finalized registration(s) for student {student_id}')
                
                current_app.logger.info(f'Preparing to add student to {len(finalized_regs)} finalized registration target(s) in Class Management')

                # Add student to Class Management for each finalized registration
                for reg in finalized_regs:
                    try:
                        class_target = _resolve_class_target_context(
                            reg,
                            fallback_course_code=reg.course_code,
                            fallback_session=session_name,
                            fallback_year=year,
                            fallback_term=term
                        )
                        current_app.logger.info(
                            f'Adding student {student_id} ({student.student_id if student else "unknown"}) '
                            f'to Class Management target {class_target["course_code"]}/'
                            f'{class_target["academic_session"]}/{class_target["year"]}/{class_target["term"]}'
                        )
                        _add_students_to_class_sessions(
                            course_code=reg.course_code,
                            academic_session=session_name,
                            year=year,
                            term=term,
                            students_data=[{
                                'student_id': student_id,
                                'carry_on': reg.carry_on if hasattr(reg, 'carry_on') else False,
                                'target_course_code': class_target['course_code'],
                                'target_academic_session': class_target['academic_session'],
                                'target_year': class_target['year'],
                                'target_term': class_target['term'],
                            }]
                        )
                        current_app.logger.info(f'Successfully added student {student_id} to Class Management for course {reg.course_code}')
                    except Exception as session_error:
                        current_app.logger.error(f'Failed to add student to class sessions for course {reg.course_code}: {session_error}', exc_info=True)
            except Exception as add_error:
                current_app.logger.warning(f'Failed to add students to Class Management: {add_error}', exc_info=True)
                # Don't fail the registration if session addition fails
        
        return jsonify({'success': True, 'message': 'Registration updated successfully.'})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to update registration: {exc}', exc_info=True)
        error_message = str(exc) if str(exc) else 'Failed to update registration.'
        return jsonify({'success': False, 'message': f'Failed to update registration: {error_message}'}), 500


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
        invites = query_for_window(CourseRegistrationInvite).filter(
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
    """Coordinator can register students for a course (course-wise)"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        flash('This page is available only for coordinators.', 'danger')
        return redirect(url_for('index'))
    
    # Batches will be loaded dynamically via API based on selected session/year/term
    # No need to load all batches initially
    batch_list = []
    
    # Get distinct academic sessions from curriculum year/term configuration
    # This shows all sessions that are assigned in the curriculum
    sessions = _cyt_query().with_entities(
        CurriculumYearTerm.academic_session
    ).distinct().filter(
        CurriculumYearTerm.academic_session.isnot(None)
    ).order_by(CurriculumYearTerm.academic_session.desc()).all()
    academic_sessions = [s[0] for s in sessions if s[0]]
    
    default_batch = session.get('course_registration_batch', '')
    return render_template('course_management/coordinator_register_student.html',
                         batches=batch_list,
                         academic_sessions=academic_sessions,
                         default_batch=default_batch)


@course_management_bp.route('/coordinator/register-student/save', methods=['POST'])
@login_required
def coordinator_save_student_registration():
    """Save course registration for multiple students by coordinator (course-wise)"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    # Check if user is Head - Head registrations are automatically finalized
    is_head = 'head' in roles
    
    data = request.get_json() or {}
    course_id = data.get('course_id')
    course_code = data.get('course_code', '').strip()
    course_name = data.get('course_name', '').strip()
    session_name = data.get('session', '').strip()
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    source_year = data.get('source_year', '').strip()
    source_term = data.get('source_term', '').strip()
    relevant_course_id = data.get('relevant_course_id')
    relevant_course_code = data.get('relevant_course_code', '').strip()
    relevant_academic_session = data.get('relevant_academic_session', '').strip()
    relevant_year = data.get('relevant_year', '').strip()
    relevant_term = data.get('relevant_term', '').strip()
    use_relevant_for_committee = data.get('use_relevant_for_committee')
    
    # Support both old format (student_ids + remark) and new format (students array)
    students_data = data.get('students', [])  # New format: [{student_id, remark, carry_on}]
    student_ids = data.get('student_ids', [])  # Old format: list of student IDs
    remark = data.get('remark', 'Regular').strip()  # Old format: single remark for all
    remove_student_ids = data.get('remove_student_ids', [])  # Student IDs to deregister
    
    if not course_id or not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Course, Session, Year, and Term are required'}), 400

    reg_window_id = get_effective_window_id(admin_override=False) if get_effective_window_id else None
    
    # Convert old format to new format if needed
    if student_ids and not students_data:
        students_data = [{'student_id': sid, 'remark': remark, 'carry_on': False} for sid in student_ids]
    
    # Handle individual deregistration
    if remove_student_ids and len(remove_student_ids) > 0:
        try:
            for student_id_to_remove in remove_student_ids:
                # Find and delete the registration
                reg_to_delete = StudentCourseRegistration.query.filter_by(
                    student_id=student_id_to_remove,
                    course_code=course_code,
                    academic_session=session_name,
                    year=year,
                    term=term
                ).first()
                
                if reg_to_delete:
                    # Remove from Class Management if finalized
                    if reg_to_delete.status == 'finalized':
                        try:
                            class_target = _resolve_class_target_context(
                                reg_to_delete,
                                fallback_course_code=course_code,
                                fallback_session=session_name,
                                fallback_year=year,
                                fallback_term=term
                            )
                            _remove_students_from_class_sessions(
                                class_target['course_code'],
                                class_target['academic_session'],
                                class_target['year'],
                                class_target['term'],
                                [student_id_to_remove]
                            )
                        except Exception as remove_error:
                            current_app.logger.error(f'Error removing student from Class Management: {remove_error}', exc_info=True)
                    
                    # Delete related invites
                    invites_to_delete = query_for_window(CourseRegistrationInvite).filter_by(
                        registration_id=reg_to_delete.id
                    ).all()
                    for invite in invites_to_delete:
                        db.session.delete(invite)
                    
                    # Delete the registration
                    db.session.delete(reg_to_delete)
                    current_app.logger.info(f'Deregistered student {student_id_to_remove} from course {course_code}')
            
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f'Successfully deregistered {len(remove_student_ids)} student(s) from {course_name}.'
            })
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f'Failed to deregister students: {exc}', exc_info=True)
            return jsonify({'success': False, 'message': 'Failed to deregister students'}), 500
    
    if not students_data or len(students_data) == 0:
        return jsonify({'success': False, 'message': 'No students selected'}), 400
    
    # Get course details
    course = Course.query.get(course_id)
    if not course:
        return jsonify({'success': False, 'message': 'Course not found'}), 404
    
    # Use course details if not provided
    if not course_code:
        course_code = course.course_code
    if not course_name:
        course_name = course.course_name
    
    # Get current teacher profile
    teacher = Teacher.query.filter_by(name=current_user.full_name).first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher profile not found'}), 404
    
    try:
        base_relevant_mapping = _normalize_relevant_course_mapping({
            'relevant_course_id': relevant_course_id,
            'relevant_course_code': relevant_course_code,
            'relevant_academic_session': relevant_academic_session,
            'relevant_year': relevant_year,
            'relevant_term': relevant_term
        }, default_year=source_year or year, default_term=source_term or term)

        # Get existing registrations for this course to identify removed students
        # CRITICAL: We need to track which students were in the PREVIOUS save operation for THIS teacher
        # We do this by checking for invites that belong to THIS teacher BEFORE we make any changes
        # Store the OLD state before any updates - check BOTH finalized and pending invites
        existing_invites_before_update = query_for_window(CourseRegistrationInvite).filter_by(
            coordinator_teacher_id=teacher.id
        ).join(StudentCourseRegistration).filter(
            StudentCourseRegistration.course_code == course_code,
            StudentCourseRegistration.academic_session == session_name,
            StudentCourseRegistration.year == year,
            StudentCourseRegistration.term == term
        ).all()
        
        # Get existing student IDs from these invites (BEFORE any updates)
        # Include students with finalized registrations that have invites for this teacher
        # This ensures we track all students that THIS teacher has worked with
        existing_student_ids = set()
        for invite in existing_invites_before_update:
            if invite.registration and invite.registration.status == 'finalized':
                existing_student_ids.add(invite.registration.student_id)
        
        current_app.logger.info(f'[coordinator_save] Course: {course_code}, Teacher: {teacher.id} ({teacher.name})')
        current_app.logger.info(f'[coordinator_save] Found {len(existing_invites_before_update)} existing invites for this teacher')
        current_app.logger.info(f'[coordinator_save] Existing student IDs (before update, finalized only): {existing_student_ids}')
        
        registered_count = 0
        skipped_count = 0
        new_student_ids = set()
        
        for student_info in students_data:
            # Handle both dict and int formats
            if isinstance(student_info, dict):
                student_id = student_info.get('student_id')
                remark = str(student_info.get('remark', 'Regular') or 'Regular').strip() or 'Regular'
                carry_on = student_info.get('carry_on', False)
                row_use_relevant_for_committee = student_info.get('use_relevant_for_committee')
                row_relevant_mapping = _normalize_relevant_course_mapping({
                    'relevant_course_id': student_info.get('relevant_course_id'),
                    'relevant_course_code': student_info.get('relevant_course_code'),
                    'relevant_academic_session': student_info.get('relevant_academic_session'),
                    'relevant_year': student_info.get('relevant_year'),
                    'relevant_term': student_info.get('relevant_term')
                }, default_year=source_year or year, default_term=source_term or term)
            else:
                # Old format: just student_id
                student_id = student_info
                remark = 'Regular'
                carry_on = False
                row_use_relevant_for_committee = use_relevant_for_committee
                row_relevant_mapping = _normalize_relevant_course_mapping({})

            remark_normalized = remark.lower()
            is_retake = remark_normalized in {'retake', 're-retake', 're retake', 'reretake'}
            if is_retake and (not session_name or not year or not term):
                return jsonify({
                    'success': False,
                    'message': 'Retake/Re-retake registration requires running Session, Year, and Term.'
                }), 400
            effective_relevant_mapping = row_relevant_mapping
            if not effective_relevant_mapping['relevant_course_code']:
                effective_relevant_mapping = base_relevant_mapping
            if is_retake and not effective_relevant_mapping['relevant_course_code']:
                return jsonify({
                    'success': False,
                    'message': f'Relevant course is required for retake/re-retake (Student ID: {student_id}).'
                }), 400
            if is_retake and (
                not effective_relevant_mapping['relevant_academic_session']
                or not effective_relevant_mapping['relevant_year']
                or not effective_relevant_mapping['relevant_term']
            ):
                return jsonify({
                    'success': False,
                    'message': f'Relevant course context (session/year/term) is incomplete (Student ID: {student_id}).'
                }), 400
            if not is_retake:
                effective_relevant_mapping = _normalize_relevant_course_mapping({})
            existing_row = None
            if student_id and course_code and session_name and year and term:
                existing_row = StudentCourseRegistration.query.filter_by(
                    student_id=student_id,
                    course_code=course_code,
                    academic_session=session_name,
                    year=year,
                    term=term
                ).first()
            effective_use_relevant_for_committee = _resolve_use_relevant_for_committee(
                row_use_relevant_for_committee,
                is_retake,
                existing_value=(existing_row.use_relevant_for_committee if existing_row else None)
            )
            if is_retake:
                current_app.logger.info(
                    '[retake_context] coordinator_save_student_registration '
                    f'student_id={student_id}, course={course_code}, session={session_name}, year={year}, term={term}, '
                    f'remark={remark}, carry_on={bool(carry_on)}, '
                    f'relevant={effective_relevant_mapping}'
                )
            
            # Check if student exists
            student = Student.query.get(student_id)
            if not student:
                skipped_count += 1
                continue
            
            # Check if registration already exists
            existing_reg = StudentCourseRegistration.query.filter_by(
                student_id=student_id,
                course_code=course_code,
                academic_session=session_name,
                year=year,
                term=term
            ).first()
            
            # Both Head and Coordinator registrations are FINAL
            is_head = 'head' in roles
            registration_status = 'finalized'
            invite_status = 'finalized'
            registered_by = 'head' if is_head else 'coordinator'
            
            if existing_reg:
                # Check if status changed from finalized to something else - need to remove from Class Management
                was_finalized = existing_reg.status == 'finalized'
                will_be_finalized = registration_status == 'finalized'
                
                # If was finalized but won't be finalized anymore, remove from Class Management
                if was_finalized and not will_be_finalized:
                    try:
                        _remove_students_from_class_sessions(
                            course_code, session_name, year, term, [student_id]
                        )
                    except Exception as remove_error:
                        current_app.logger.error(f'Error removing student from Class Management: {remove_error}', exc_info=True)
                
                # Update existing registration - preserve registered_by if it was set by coordinator/head
                # Only allow update if current user is coordinator/head
                existing_reg.course_id = course_id
                existing_reg.course_name = course_name
                existing_reg.credit = course.credit
                existing_reg.course_type = course.course_type
                existing_reg.nature = course.core_optional or 'Core'
                existing_reg.remark = remark
                existing_reg.carry_on = carry_on
                normalized_source_year, normalized_source_term = _normalize_source_year_term(
                    source_year,
                    source_term,
                    year,
                    term
                )
                existing_reg.source_year = normalized_source_year
                existing_reg.source_term = normalized_source_term
                existing_reg.relevant_course_id = effective_relevant_mapping['relevant_course_id']
                existing_reg.relevant_course_code = effective_relevant_mapping['relevant_course_code']
                existing_reg.relevant_academic_session = effective_relevant_mapping['relevant_academic_session']
                existing_reg.relevant_year = effective_relevant_mapping['relevant_year']
                existing_reg.relevant_term = effective_relevant_mapping['relevant_term']
                existing_reg.use_relevant_for_committee = effective_use_relevant_for_committee
                existing_reg.status = registration_status
                # Preserve registered_by if it was coordinator/head, otherwise update
                if existing_reg.registered_by in ['coordinator', 'head']:
                    existing_reg.registered_by = registered_by
                reg = existing_reg
            else:
                # Create new registration
                normalized_source_year, normalized_source_term = _normalize_source_year_term(
                    source_year,
                    source_term,
                    year,
                    term
                )
                reg = StudentCourseRegistration(
                    student_id=student_id,
                    course_id=course_id,
                    window_id=reg_window_id,
                    academic_session=session_name,
                    year=year,
                    term=term,
                    source_year=normalized_source_year,
                    source_term=normalized_source_term,
                    course_code=course_code,
                    course_name=course_name,
                    credit=course.credit,
                    course_type=course.course_type,
                    nature=course.core_optional or 'Core',
                    remark=remark,
                    carry_on=carry_on,
                    relevant_course_id=effective_relevant_mapping['relevant_course_id'],
                    relevant_course_code=effective_relevant_mapping['relevant_course_code'],
                    relevant_academic_session=effective_relevant_mapping['relevant_academic_session'],
                    relevant_year=effective_relevant_mapping['relevant_year'],
                    relevant_term=effective_relevant_mapping['relevant_term'],
                    use_relevant_for_committee=effective_use_relevant_for_committee,
                    status=registration_status,
                    registered_by=registered_by
                )
                db.session.add(reg)
            
            # Create or update invite for this coordinator
            db.session.flush()  # Flush to get reg.id
            
            existing_invite = query_for_window(CourseRegistrationInvite).filter_by(
                registration_id=reg.id,
                coordinator_teacher_id=teacher.id
            ).first()
            
            if existing_invite:
                # Update existing invite status
                existing_invite.status = invite_status
                if is_head and not existing_invite.responded_at:
                    existing_invite.responded_at = datetime.utcnow()
            else:
                invite = CourseRegistrationInvite(
                    registration_id=reg.id,
                    student_id=student_id,
                    coordinator_teacher_id=teacher.id,
                    status=invite_status
                )
                if stamp_window_id:
                    stamp_window_id(invite, window_id=reg.window_id)
                if is_head:
                    invite.responded_at = datetime.utcnow()
                db.session.add(invite)
            
            registered_count += 1
            new_student_ids.add(student_id)
        
        current_app.logger.info(f'[coordinator_save] New student IDs (after processing): {new_student_ids}')
        
        # CRITICAL FIX: We should NOT remove students just because they're not in the new list
        # We should ONLY remove students if their registration was actually DELETED in this operation
        # Check which registrations were actually deleted (existed before but don't exist now)
        
        # Get all finalized registrations AFTER the update to see what's still there
        final_regs_after = StudentCourseRegistration.query.filter_by(
            course_code=course_code,
            academic_session=session_name,
            year=year,
            term=term,
            status='finalized'
        ).all()
        
        final_student_ids_after = {reg.student_id for reg in final_regs_after}
        
        # Only remove students that:
        # 1. Were in existing_student_ids (had an invite for this teacher)
        # 2. Are NOT in final_student_ids_after (their registration was actually deleted/unfinalized)
        # This ensures we only remove students whose registrations were actually removed, not just missing from the new list
        removed_student_ids = existing_student_ids - final_student_ids_after
        
        current_app.logger.info(f'[coordinator_save] Finalized student IDs after update: {final_student_ids_after}')
        current_app.logger.info(f'[coordinator_save] Removed student IDs (registrations deleted/unfinalized): {removed_student_ids}')
        
        # IMPORTANT: Only remove students from Class Management if:
        # 1. They were registered by THIS teacher (were in existing_student_ids)
        # 2. Their registration was actually deleted/unfinalized (not in final_student_ids_after)
        # 3. The registration status is finalized
        if removed_student_ids and registration_status == 'finalized':
            try:
                current_app.logger.warning(f'[coordinator_save] REMOVING {len(removed_student_ids)} student(s) from Class Management for course {course_code}. Student IDs: {removed_student_ids}')
                removed_regs = [
                    inv.registration for inv in existing_invites_before_update
                    if inv.registration and inv.registration.student_id in removed_student_ids
                ]
                if removed_regs:
                    for reg in removed_regs:
                        class_target = _resolve_class_target_context(
                            reg,
                            fallback_course_code=course_code,
                            fallback_session=session_name,
                            fallback_year=year,
                            fallback_term=term
                        )
                        _remove_students_from_class_sessions(
                            class_target['course_code'],
                            class_target['academic_session'],
                            class_target['year'],
                            class_target['term'],
                            [reg.student_id]
                        )
                else:
                    _remove_students_from_class_sessions(
                        course_code, session_name, year, term, list(removed_student_ids)
                    )
                current_app.logger.info(f'[coordinator_save] Successfully removed {len(removed_student_ids)} student(s) from Class Management')
            except Exception as remove_error:
                current_app.logger.error(f'[coordinator_save] Error removing students from Class Management: {remove_error}', exc_info=True)
        elif removed_student_ids:
            current_app.logger.info(f'[coordinator_save] Not removing students because registration_status is not finalized (status: {registration_status})')
        else:
            current_app.logger.info(f'[coordinator_save] No students to remove - all existing students still have finalized registrations')
        
        db.session.commit()
        
        # After registration is saved, add students to class management sessions
        # Only for finalized registrations (Head registrations are automatically finalized)
        if registration_status == 'finalized':
            try:
                finalized_regs_for_students = StudentCourseRegistration.query.filter(
                    StudentCourseRegistration.course_code == course_code,
                    StudentCourseRegistration.academic_session == session_name,
                    StudentCourseRegistration.year == year,
                    StudentCourseRegistration.term == term,
                    StudentCourseRegistration.status == 'finalized',
                    StudentCourseRegistration.student_id.in_([s.get('student_id') for s in students_data if isinstance(s, dict)])
                ).all()
                reg_map = {reg.student_id: reg for reg in finalized_regs_for_students}
                students_for_class = []
                for student_info in students_data:
                    if isinstance(student_info, dict):
                        sid = student_info.get('student_id')
                        carry_on_flag = student_info.get('carry_on', False)
                    else:
                        sid = student_info
                        carry_on_flag = False
                    reg_obj = reg_map.get(sid)
                    class_target = _resolve_class_target_context(
                        reg_obj or {
                            'remark': student_info.get('remark') if isinstance(student_info, dict) else 'Regular',
                            'carry_on': carry_on_flag,
                            'relevant_course_code': (base_relevant_mapping or {}).get('relevant_course_code'),
                            'relevant_academic_session': (base_relevant_mapping or {}).get('relevant_academic_session'),
                            'relevant_year': (base_relevant_mapping or {}).get('relevant_year'),
                            'relevant_term': (base_relevant_mapping or {}).get('relevant_term'),
                        },
                        fallback_course_code=course_code,
                        fallback_session=session_name,
                        fallback_year=year,
                        fallback_term=term
                    )
                    students_for_class.append({
                        'student_id': sid,
                        'carry_on': carry_on_flag,
                        'target_course_code': class_target['course_code'],
                        'target_academic_session': class_target['academic_session'],
                        'target_year': class_target['year'],
                        'target_term': class_target['term'],
                    })
                _add_students_to_class_sessions(
                    course_code=course_code,
                    academic_session=session_name,
                    year=year,
                    term=term,
                    students_data=students_for_class
                )
            except Exception as session_error:
                current_app.logger.warning(f'Failed to add students to class sessions: {session_error}', exc_info=True)
                # Don't fail the registration if session addition fails
        
        return jsonify({
            'success': True,
            'message': f'Successfully registered {registered_count} student(s) for {course_name}. {skipped_count} student(s) skipped.'
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'Failed to save coordinator registration: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': f'Failed to save registration: {exc}'}), 500


@course_management_bp.route('/coordinator/register-student/api/batches', methods=['GET'])
@login_required
def get_batches_for_registration():
    """Get batches assigned in curriculum for a given session, year, and term"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    session_name = request.args.get('session', '').strip()
    year = request.args.get('year', '').strip()
    term = request.args.get('term', '').strip()
    
    if not session_name or not year or not term:
        return jsonify({'success': False, 'message': 'Session, Year, and Term are required'}), 400
    
    try:
        active_window_id = _active_window_id()
        matching_configs = _cyt_rows_for_session_year_term(session_name, year, term)
        primary_batches = []
        seen_primary = set()
        curriculum_ids = {cfg.curriculum_id for cfg in matching_configs if cfg.curriculum_id}
        curricula_by_id = {
            c.id: c for c in Curriculum.query.filter(Curriculum.id.in_(curriculum_ids)).all()
        } if curriculum_ids else {}

        for cfg in matching_configs:
            configured = _batches_from_csv(cfg.batch)
            batch_candidates = configured
            if not batch_candidates:
                curriculum = curricula_by_id.get(cfg.curriculum_id)
                if curriculum:
                    batch_candidates = curriculum.get_batches_list(window_id=active_window_id) or []
            for batch in batch_candidates:
                if batch == 'None' or batch in seen_primary:
                    continue
                seen_primary.add(batch)
                primary_batches.append(batch)
        
        current_app.logger.info(f'[get_batches_for_registration] Session: {session_name}, Year: {year}, Term: {term}')
        current_app.logger.info(f'[get_batches_for_registration] Primary batches (Recommended): {primary_batches}')
        
        # Also get all batches from Student table (for retake students who might be from other batches)
        all_batches_set = set(primary_batches)
        if Student:
            all_student_batches = db.session.query(Student.batch).distinct().filter(
                Student.batch.isnot(None),
                Student.batch != ''
            ).order_by(Student.batch.desc()).all()
            for batch_tuple in all_student_batches:
                if batch_tuple[0]:
                    all_batches_set.add(batch_tuple[0])
        
        # Convert to list and sort: primary batches first (descending), then others (descending)
        # Sort key: (0 if primary, 1 if not primary, then batch name for descending order)
        all_batches_list = sorted(all_batches_set, key=lambda x: (x not in primary_batches, x), reverse=False)
        # Reverse the entire list to get descending order within each group
        all_batches_list = [b for b in sorted(primary_batches, reverse=True)] + [b for b in sorted(all_batches_set - set(primary_batches), reverse=True)]
        
        current_app.logger.info(f'[get_batches_for_registration] All batches: {all_batches_list}')
        current_app.logger.info(f'[get_batches_for_registration] Returning primary_batches: {primary_batches}')
        
        return jsonify({
            'success': True,
            'batches': all_batches_list,
            'primary_batches': primary_batches  # For UI indication if needed
        })
    except Exception as e:
        current_app.logger.error(f'Error getting batches: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error fetching batches'}), 500


@course_management_bp.route('/coordinator/register-student/api/students', methods=['GET'])
@login_required
def get_students_for_course_registration():
    """Get students for course registration based on batch"""
    roles = parse_roles(current_user.role)
    if 'head' not in roles and 'dean' not in roles and 'teacher' not in roles:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    batch = request.args.get('batch', '').strip()
    search = request.args.get('search', '').strip()
    
    if not batch:
        return jsonify({'success': False, 'message': 'Batch is required'}), 400
    
    # Persist selected batch so coordinator register student page can pre-select it after redirect/reload
    session['course_registration_batch'] = batch
    
    try:
        current_app.logger.info(f'Loading students for batch: {batch}, search: {search}')
        
        if not Student:
            current_app.logger.error('Student model not available')
            return jsonify({'success': False, 'message': 'Student Management module not available'}), 503
        
        # Build query step by step - handle batch filtering
        try:
            # Filter by batch, excluding null/empty batches
            query = Student.query.filter(
                Student.batch == batch,
                Student.batch.isnot(None),
                Student.batch != ''
            )
            current_app.logger.info(f'Query built for batch: {batch}')
        except Exception as query_error:
            current_app.logger.error(f'Error building query: {query_error}', exc_info=True)
            import traceback
            current_app.logger.error(f'Query error traceback: {traceback.format_exc()}')
            return jsonify({'success': False, 'message': f'Error building query: {str(query_error)}'}), 500
        
        # Apply search filter
        if search:
            try:
                query = query.filter(
                    or_(
                        Student.name.ilike(f'%{search}%'),
                        Student.student_id.ilike(f'%{search}%')
                    )
                )
            except Exception as search_error:
                current_app.logger.warning(f'Error applying search filter: {search_error}')
                # Continue without search filter if it fails
        
        # Execute query
        try:
            students = query.order_by(Student.student_id.asc()).limit(500).all()
            current_app.logger.info(f'Found {len(students)} students for batch {batch}')
        except Exception as exec_error:
            current_app.logger.error(f'Error executing query: {exec_error}', exc_info=True)
            return jsonify({'success': False, 'message': f'Error executing query: {str(exec_error)}'}), 500
        
        # Get existing registrations for the selected course/session/year/term if provided
        course_code = request.args.get('course_code', '').strip()
        session_name = request.args.get('session', '').strip()
        year = request.args.get('year', '').strip()
        term = request.args.get('term', '').strip()
        
        registered_student_ids = set()
        if course_code and session_name and year and term:
            try:
                # Use raw SQL query to avoid carry_on column issue until migration is run
                from sqlalchemy import text
                sql = text("""
                    SELECT student_id 
                    FROM student_course_registration 
                    WHERE course_code = :course_code 
                    AND academic_session = :session 
                    AND year = :year 
                    AND term = :term
                """)
                result = db.session.execute(sql, {
                    'course_code': course_code,
                    'session': session_name,
                    'year': year,
                    'term': term
                })
                registered_student_ids = {row[0] for row in result}
                current_app.logger.info(f'Found {len(registered_student_ids)} already registered students')
            except Exception as reg_error:
                current_app.logger.warning(f'Error querying registrations: {reg_error}, continuing without registration check')
                # Continue without registration check
        
        # Build students list with safe attribute access
        students_list = []
        for s in students:
            try:
                student_data = {
                    'id': s.id,
                    'student_id': getattr(s, 'student_id', '') or '',
                    'name': getattr(s, 'name', '') or '',
                    'batch': getattr(s, 'batch', '') or '',
                    'is_registered': s.id in registered_student_ids
                }
                # Add optional fields if they exist
                if hasattr(s, 'email') and s.email:
                    student_data['email'] = s.email
                if hasattr(s, 'phone') and s.phone:
                    student_data['phone'] = s.phone
                students_list.append(student_data)
            except Exception as student_error:
                current_app.logger.warning(f'Error processing student {getattr(s, "id", "unknown")}: {student_error}', exc_info=True)
                continue
        
        return jsonify({
            'success': True,
            'students': students_list
        })
    except Exception as e:
        current_app.logger.error(f'Error in get_students_for_course_registration: {str(e)}', exc_info=True)
        import traceback
        error_trace = traceback.format_exc()
        current_app.logger.error(f'Full traceback: {error_trace}')
        return jsonify({
            'success': False, 
            'message': f'Error loading students: {str(e)}. Please check server logs for details.'
        }), 500


@course_management_bp.route('/curriculum/<int:curriculum_id>/year-term-config', methods=['POST'])
@login_required
def save_year_term_config(curriculum_id):
    """Save year/term configuration with one or more academic sessions."""
    curriculum = Curriculum.query.get_or_404(curriculum_id)
    
    data = request.get_json() or {}
    year = data.get('year', '').strip()
    term = data.get('term', '').strip()
    academic_session = data.get('academic_session', '').strip()
    
    if not year or not term:
        return jsonify({'success': False, 'message': 'Year and Term are required'}), 400
    
    try:
        session_configs_payload = data.get('session_configs')

        normalized_session_configs = []
        if isinstance(session_configs_payload, list):
            # New format: one year/term can have many academic sessions.
            merged_by_session = {}
            merged_session_name = {}
            session_order = []
            for item in session_configs_payload:
                if not isinstance(item, dict):
                    continue
                session_value = str(item.get('academic_session', '') or '').strip()
                raw_batches = item.get('batches', [])
                if isinstance(raw_batches, str):
                    raw_batches = [raw_batches]
                elif not isinstance(raw_batches, list):
                    raw_batches = []

                cleaned_batches = []
                seen_batches = set()
                for raw_batch in raw_batches:
                    batch_value = str(raw_batch or '').strip()
                    if not batch_value or batch_value in seen_batches:
                        continue
                    seen_batches.add(batch_value)
                    cleaned_batches.append(batch_value)

                # Skip fully empty rows (e.g., an untouched newly-added row).
                if not session_value and not cleaned_batches:
                    continue
                # Session name is required for a usable config row.
                if not session_value:
                    return jsonify({
                        'success': False,
                        'message': 'Each configuration row must include an Academic Session.'
                    }), 400

                # Keep session keys case-insensitive to avoid MySQL collation conflicts.
                session_key = session_value.casefold()
                if session_key not in merged_by_session:
                    merged_by_session[session_key] = []
                    merged_session_name[session_key] = session_value
                    session_order.append(session_key)
                merged_by_session[session_key].extend(cleaned_batches)

            for session_key in session_order:
                session_value = merged_session_name.get(session_key) or session_key
                deduped_batches = []
                seen = set()
                for batch_value in merged_by_session[session_key]:
                    if batch_value in seen:
                        continue
                    seen.add(batch_value)
                    deduped_batches.append(batch_value)

                if 'None' in deduped_batches:
                    batch_value = 'None'
                else:
                    batch_value = ','.join(deduped_batches) if deduped_batches else None

                normalized_session_configs.append({
                    'academic_session': session_value,
                    'batch': batch_value
                })
        else:
            # Legacy format fallback: a single row payload.
            batches = data.get('batches', [])
            if isinstance(batches, str):
                batches = [batches]
            elif not isinstance(batches, list):
                batches = []

            legacy_batch = data.get('batch', '').strip()
            if legacy_batch and not batches:
                batches = [legacy_batch]

            normalized_batches = []
            seen_batches = set()
            for raw_batch in batches:
                batch_value = str(raw_batch).strip()
                if not batch_value or batch_value in seen_batches:
                    continue
                seen_batches.add(batch_value)
                normalized_batches.append(batch_value)

            if 'None' in normalized_batches:
                batch = 'None'
            else:
                batch = ','.join(normalized_batches) if normalized_batches else None

            normalized_session_configs.append({
                'academic_session': academic_session if academic_session else None,
                'batch': batch
            })

        # Replace configs for this year/term in the active operational window only.
        _cyt_query().filter_by(
            curriculum_id=curriculum_id,
            year=year,
            term=term
        ).delete(synchronize_session=False)

        for cfg in normalized_session_configs:
            row = CurriculumYearTerm(
                curriculum_id=curriculum_id,
                year=year,
                term=term,
                academic_session=cfg['academic_session'],
                batch=cfg['batch']
            )
            if stamp_window_id:
                stamp_window_id(row)
            db.session.add(row)
        
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Configuration saved successfully',
            'saved_count': len(normalized_session_configs)
        })
    except IntegrityError as exc:
        db.session.rollback()
        raw_error = str(getattr(exc, 'orig', exc))
        current_app.logger.error(f'Year/term config integrity error: {raw_error}', exc_info=True)
        normalized_error = raw_error.lower()
        # Helpful message when production DB still has old unique key:
        # uq_curriculum_year_term(curriculum_id, year, term)
        if 'uq_curriculum_year_term' in normalized_error and 'session' not in normalized_error:
            return jsonify({
                'success': False,
                'message': (
                    'Database এখনও পুরনো unique rule ব্যবহার করছে। '
                    'Please update curriculum_year_term unique key to '
                    '(curriculum_id, year, term, academic_session) and try again.'
                )
            }), 400
        if 'uq_curriculum_year_term_session' in normalized_error or 'duplicate entry' in normalized_error:
            return jsonify({
                'success': False,
                'message': (
                    'এই Year/Term এ একই Academic Session আগেই আছে। '
                    'Please use a different session name.'
                )
            }), 400
        return jsonify({'success': False, 'message': 'Configuration conflicts with an existing row.'}), 400
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
                        configured_batches = [b.strip() for b in year_term_config.batch.split(',') if b.strip() and b.strip() != 'None']
                        if configured_batches:
                            batch = configured_batches[0]
                            current_app.logger.info(f'Using first configured batch from year-term config: {batch}')
                    if not academic_session and year_term_config.academic_session and year_term_config.academic_session.strip():
                        academic_session = year_term_config.academic_session.strip()
                        current_app.logger.info(f'Using academic_session from year-term config: {academic_session}')
            except Exception as e:
                current_app.logger.warning(f'Could not get year-term config: {e}')
        
        # Log final batch value before creating session
        current_app.logger.info(f'Final batch value before session creation: "{batch}"')

        window_id = _active_window_id()
        
        # Check if assignment already exists (scoped to operational window)
        existing_assignment_query = _csa_query().filter_by(
            course_id=course_id,
            teacher_id=teacher_id,
            section=section,
            year=year,
            term=term,
        ).filter(
            (CourseSessionAssignment.batch == batch) if batch else (CourseSessionAssignment.batch.is_(None))
        )
        existing_assignment = existing_assignment_query.first()
        
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
            if window_id is not None:
                split_group_parts.append(f'win{window_id}')
            
            # Create a unique string and hash it to ensure it fits in VARCHAR(36)
            # MD5 hash produces 32 characters, which fits perfectly in VARCHAR(36)
            unique_string = '_'.join(split_group_parts)
            split_group_id = hashlib.md5(unique_string.encode('utf-8')).hexdigest()
            
            # Check if there's already a session with this split_group_id
            # If yes, use the same split_group_id to link them
            existing_split_session = Session.query.filter_by(
                split_group_id=split_group_id,
                archived=False
            ).first()
            
            if existing_split_session:
                # Use the existing split_group_id to link sessions
                current_app.logger.info(f'Found existing split course session {existing_split_session.id} with split_group_id {split_group_id}, linking new session')
        
        # Reuse an existing matching session whenever possible (especially archived sessions
        # created during unassign), so attendance/history remains in a single session.
        normalized_academic_session = (academic_session or '').strip()
        all_matching_sessions = Session.query.filter_by(
            course_code=course.course_code,
            year=year,
            term=term
        ).all()

        reusable_session = None
        for existing_session in all_matching_sessions:
            existing_academic_session = (existing_session.academic_session or '').strip()
            if existing_academic_session != normalized_academic_session:
                continue

            if window_id is not None:
                sess_win = existing_session.window_id
                if sess_win is not None and sess_win != window_id:
                    continue
                if sess_win is None and window_id != 1:
                    continue

            # Check course scope conflicts on active sessions.
            if not existing_session.archived:
                if existing_session.course_scope == SCOPE_FULL and course_scope != SCOPE_FULL:
                    return jsonify({
                        'success': False,
                        'message': 'A full-course session already exists for this course. Delete/unassign it first to create section-specific sessions.'
                    }), 400
                if course_scope == SCOPE_FULL and existing_session.course_scope != SCOPE_FULL:
                    return jsonify({
                        'success': False,
                        'message': 'Section-specific sessions already exist for this course. Delete/unassign them first to create a full-course session.'
                    }), 400

            if existing_session.course_scope != course_scope:
                continue

            # Keep split link consistent if split scope is used.
            if split_group_id and existing_session.split_group_id and existing_session.split_group_id != split_group_id:
                continue

            linked_assignment = _csa_query().filter_by(session_id=existing_session.id).first()
            if linked_assignment and not existing_session.archived:
                # Active linked session already exists for this scope.
                return jsonify({
                    'success': False,
                    'message': f'A session for this course and section is already assigned to {linked_assignment.teacher.name if linked_assignment.teacher else "another teacher"}.'
                }), 400

            # Prefer reusing archived/unlinked sessions and avoid creating a fresh session.
            reusable_session = existing_session
            if existing_session.archived:
                break

        reused_existing_session = reusable_session is not None
        if reused_existing_session:
            session_obj = reusable_session
            session_obj.archived = False
            session_obj.teacher_id = teacher_id
            session_obj.academic_session = academic_session
            session_obj.course_name = course.course_name
            session_obj.course_type = _normalize_session_course_type(course.course_type)
            session_obj.category = course.category
            session_obj.course_scope = course_scope
            session_obj.split_group_id = split_group_id
            if window_id is not None:
                session_obj.window_id = window_id
            ClassStudent.query.filter_by(session_id=session_obj.id).update(
                {'teacher_id': teacher_id},
                synchronize_session=False
            )
            db.session.flush()
            current_app.logger.info(f'Reusing existing session {session_obj.id} instead of creating a new one')
        else:
            # Create Session in Class Management
            session_obj = Session(
                year=year,
                term=term,
                academic_session=academic_session,
                course_code=course.course_code,
                course_name=course.course_name,
                teacher_id=teacher_id,
                course_type=_normalize_session_course_type(course.course_type),
                category=course.category,
                course_scope=course_scope,
                split_group_id=split_group_id,
                window_id=window_id,
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
                    
                    # Check if student is registered for this course (finalized registration only)
                    if StudentCourseRegistration and session_obj.course_code and session_obj.academic_session and session_obj.year and session_obj.term:
                        registration = StudentCourseRegistration.query.filter_by(
                            student_id=student.id,
                            course_code=session_obj.course_code,
                            academic_session=session_obj.academic_session,
                            year=session_obj.year,
                            term=session_obj.term,
                            status='finalized'
                        ).first()
                        
                        if not registration:
                            current_app.logger.info(f'Student {student.student_id} ({student.name}) not registered for course {session_obj.course_code}, skipping...')
                            continue
                    
                    class_student = ClassStudent(
                        student_id=student.student_id,
                        name=student.name,
                        session_id=session_obj.id,
                        teacher_id=teacher_id
                    )
                    db.session.add(class_student)
                    db.session.flush()  # Flush to get class_student.id before carry on
                    
                    # Carry on assessment marks if enabled in registration
                    try:
                        from blueprints.class_management.routes import _carry_on_assessment_marks
                        _carry_on_assessment_marks(class_student, session_obj)
                    except Exception as carry_on_error:
                        current_app.logger.warning(f'Error carrying on marks for {student.student_id}: {carry_on_error}')
                    
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
            window_id=window_id,
            session_created=True,
            session_id=session_obj.id
        )
        db.session.add(assignment)
        
        db.session.commit()
        
        message = f'Teacher assigned and session {"restored" if reused_existing_session else "created"} successfully!'
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

        if get_for_window:
            assignment = get_for_window(CourseSessionAssignment, assignment_id)
        else:
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
                    
                    # 9. Delete split course invites (where this session is the inviter)
                    try:
                        ClassSplitInvite.query.filter_by(inviter_session_id=session_id).delete(synchronize_session=False)
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
        if get_for_window:
            assignment = get_for_window(CourseSessionAssignment, assignment_id)
        else:
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
        assignments = _csa_query().filter_by(course_id=course_id).order_by(
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
