from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, send_file, current_app
from flask_login import login_required, current_user
from utils.window_utils import (
    query_for_window,
    stamp_window_id,
    get_effective_window_id,
    get_or_404_for_window,
    DEFAULT_WINDOW_ID,
)
from sqlalchemy import or_, func, text, inspect
from role_utils import is_admin, parse_roles, role_required
from extensions import db
from .models import Teacher, Room, AssignedCourse, Routine, SavedRoutine
from blueprints.course_management.models import Course, DutyAssignment
from .forms import TeacherForm, RoomForm, AssignCourseForm
from datetime import datetime
from utils.timezone import format_bd
from utils.tenant import current_tenant
from collections import defaultdict
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
import os
import sys
import random

routine_management_bp = Blueprint('routine_management', __name__,
                                  template_folder='templates',
                                  static_folder='static')


def _routine_window_id():
    """Always use the user's selected operational window in Routine Management."""
    window_id = get_effective_window_id(admin_override=False)
    return window_id if window_id is not None else DEFAULT_WINDOW_ID


def _window_scope_filter(model, window_id=None):
    window_id = _routine_window_id() if window_id is None else window_id
    if window_id == DEFAULT_WINDOW_ID:
        return or_(
            model.window_id == window_id,
            model.window_id.is_(None),
        )
    return model.window_id == window_id


def _query_for_routine_window(model):
    return query_for_window(model, admin_override=False)


def _parse_batch_values(batch_text):
    if not batch_text:
        return []
    return [
        batch.strip()
        for batch in str(batch_text).split(',')
        if batch.strip() and batch.strip().lower() != 'none'
    ]


def _is_retake_remark(remark_value):
    remark_normalized = str(remark_value or '').strip().lower()
    return remark_normalized in {'retake', 're-retake', 're retake', 'reretake'}


def _active_semesters_for_routine():
    from utils.semester_utils import get_active_semesters

    window_id = _routine_window_id()
    semesters = get_active_semesters(window_id=window_id)
    if semesters:
        return semesters
    # Selected window has no active semesters — show all so routine is not blocked.
    return get_active_semesters(window_id=None)


def _semester_field_matches(left_value, right_value):
    from utils.semester_utils import _normalize_year_term

    return _normalize_year_term(left_value) == _normalize_year_term(right_value)


def _batch_values(batch_text):
    values = _parse_batch_values(batch_text)
    if values:
        return values
    cleaned = str(batch_text or '').strip()
    return [cleaned] if cleaned else []


def _batch_matches_value(batch_text, target_batch):
    target = str(target_batch or '').strip()
    if not target:
        return False
    return target in _batch_values(batch_text)


def _record_matches_semester(academic_session, year, term, batch, semester):
    session_value = str(academic_session or '').strip()
    semester_session = str(semester.academic_session or '').strip()
    if session_value and semester_session and session_value != semester_session:
        return False
    if not _semester_field_matches(year, semester.year):
        return False
    if not _semester_field_matches(term, semester.term):
        return False
    if semester.batch:
        return _batch_matches_value(batch, semester.batch)
    return True


def _semester_group_key(semester):
    """Group key: same session + year + term (+ window) share one routine dropdown entry."""
    return (
        str(getattr(semester, 'academic_session', None) or '').strip(),
        str(getattr(semester, 'year', None) or '').strip(),
        str(getattr(semester, 'term', None) or '').strip(),
        getattr(semester, 'window_id', None),
    )


def _semester_contexts_for_routine():
    """Active semester options for the routine sidebar.

    Multiple ActiveSemesterConfig rows that share the same academic session,
    year, and term (different batches) collapse into one dropdown entry.
    """
    contexts = []
    seen = {}

    for semester in _active_semesters_for_routine():
        key = _semester_group_key(semester)
        batch = str(semester.batch or '').strip()
        if batch.lower() == 'none':
            batch = ''

        if key in seen:
            existing = contexts[seen[key]]
            existing['semester_ids'].append(semester.id)
            if batch and batch not in existing['batches']:
                existing['batches'].append(batch)
            continue

        # Label without batch — batches are merged under one year/term/session
        parts = []
        if semester.year:
            parts.append(str(semester.year).strip())
        if semester.term:
            parts.append(str(semester.term).strip())
        if semester.academic_session:
            parts.append(str(semester.academic_session).strip())
        label = ' · '.join(parts) if parts else f'Semester #{semester.id}'
        if semester.operational_window and semester.window_id != _routine_window_id():
            label = f'{semester.operational_window.name} · {label}'

        seen[key] = len(contexts)
        contexts.append({
            'id': semester.id,
            'semester_ids': [semester.id],
            'label': label,
            'academic_session': str(semester.academic_session or '').strip(),
            'year': str(semester.year or '').strip(),
            'term': str(semester.term or '').strip(),
            'batch': '',
            'batches': [batch] if batch else [],
            'window_id': semester.window_id,
        })
    return contexts


def _sibling_semesters_for(semester):
    """All active semester rows sharing session/year/term with the given one."""
    if not semester:
        return []
    key = _semester_group_key(semester)
    return [s for s in _active_semesters_for_routine() if _semester_group_key(s) == key]


def _get_active_semester_by_id(semester_id):
    from blueprints.course_management.models import ActiveSemesterConfig

    if not semester_id:
        return None
    try:
        semester_id = int(semester_id)
    except (TypeError, ValueError):
        return None

    return ActiveSemesterConfig.query.filter_by(
        id=semester_id,
        is_active=True,
    ).first()


def _year_term_matches_semester(year, term, semester):
    """True when record year/term align with an active semester row."""
    if not semester:
        return False
    return (
        _semester_field_matches(year, semester.year)
        and _semester_field_matches(term, semester.term)
    )


def _assignment_matches_semester_record(assignment, semester):
    """
    Match assignment to active semester by year/term (and academic_session when both set).

    assignment.batch is often stale or empty when saved from curriculum, so
    routine uses the semester the user selected for the batch label.
    """
    if not assignment or not semester:
        return False
    a_sess = str(getattr(assignment, 'academic_session', None) or '').strip()
    s_sess = str(getattr(semester, 'academic_session', None) or '').strip()
    if a_sess and s_sess and a_sess != s_sess:
        return False
    return _year_term_matches_semester(
        getattr(assignment, 'year', None),
        getattr(assignment, 'term', None),
        semester,
    )


def _course_matches_semester(course, semester):
    if not course or not semester:
        return False
    year = getattr(course, 'year', None) or getattr(course, 'display_year', None)
    term = getattr(course, 'term', None) or getattr(course, 'display_term', None)
    return _year_term_matches_semester(year, term, semester)


def _collect_assignments_for_semester(semester):
    """Gather teacher assignments for one active semester using layered fallbacks."""
    from blueprints.course_management.models import CourseSessionAssignment
    from blueprints.class_management.models import Session
    from sqlalchemy.orm import joinedload

    if not semester:
        return []

    load_options = (
        joinedload(CourseSessionAssignment.course),
        joinedload(CourseSessionAssignment.teacher),
    )
    matched = []
    seen_ids = set()

    def _add_assignment(assignment):
        if not assignment or assignment.id in seen_ids:
            return
        if not assignment.course:
            return
        seen_ids.add(assignment.id)
        matched.append(assignment)

    def _scan_query(query):
        for assignment in query.options(*load_options).all():
            if _assignment_matches_semester_record(assignment, semester):
                _add_assignment(assignment)
            elif assignment.course and _course_matches_semester(assignment.course, semester):
                _add_assignment(assignment)

    _scan_query(_query_for_routine_window(CourseSessionAssignment))
    if not matched:
        _scan_query(CourseSessionAssignment.query)

    if not matched:
        session_rows = _query_for_routine_window(Session).filter(
            or_(Session.archived.is_(False), Session.archived.is_(None)),
        ).all()
        if not session_rows:
            session_rows = Session.query.filter(
                or_(Session.archived.is_(False), Session.archived.is_(None)),
            ).all()

        session_ids = {
            row.id for row in session_rows
            if _year_term_matches_semester(row.year, row.term, semester)
        }
        if session_ids:
            for assignment in CourseSessionAssignment.query.options(*load_options).filter(
                CourseSessionAssignment.session_id.in_(session_ids),
            ).all():
                _add_assignment(assignment)

    current_app.logger.info(
        'Routine semester %s (%s/%s session=%s batch=%s window=%s) -> %s assignment(s)',
        semester.id,
        semester.year,
        semester.term,
        semester.academic_session,
        semester.batch,
        _routine_window_id(),
        len(matched),
    )
    return matched


def _assignments_for_semester(semester):
    return _collect_assignments_for_semester(semester)


def _assignments_for_routine_batch(batch):
    """Legacy batch-only lookup: merge assignments from all active semesters with this batch."""
    assignments = []
    seen_ids = set()
    for semester in _active_semesters_for_routine():
        if semester.batch and not _batch_matches_value(semester.batch, batch):
            continue
        for assignment in _assignments_for_semester(semester):
            if assignment.id in seen_ids:
                continue
            seen_ids.add(assignment.id)
            assignments.append(assignment)
    return assignments


def _matches_any_active_semester(academic_session, year, term, batch=None):
    for semester in _active_semesters_for_routine():
        if _record_matches_semester(academic_session, year, term, batch, semester):
            return True
    return False


def _registration_matches_semester(registration, semester, student_batch=None):
    if student_batch is None:
        student_batch = str(getattr(getattr(registration, 'student', None), 'batch', '') or '').strip()
        if not student_batch and hasattr(registration, 'student_id'):
            from blueprints.student_management.models import Student
            student = Student.query.get(registration.student_id)
            student_batch = str(getattr(student, 'batch', '') or '').strip()
    if not _semester_field_matches(registration.year, semester.year):
        return False
    if not _semester_field_matches(registration.term, semester.term):
        return False
    semester_batch = str(semester.batch or '').strip()
    if semester_batch:
        return _batch_matches_value(student_batch, semester.batch)
    return True


def _is_non_merged_retake_registration(registration):
    return (
        _is_retake_remark(getattr(registration, 'remark', None))
        and not getattr(registration, 'use_relevant_for_committee', True)
    )


def _batches_for_active_semesters():
    """Batch numbers derived from active semester contexts (legacy helper)."""
    batches = set()
    for context in _semester_contexts_for_routine():
        for batch_value in context.get('batches') or []:
            batch_value = str(batch_value or '').strip()
            if batch_value:
                batches.add(batch_value)
        batch_value = str(context.get('batch') or '').strip()
        if batch_value:
            batches.add(batch_value)
    return {batch for batch in batches if batch and batch.lower() != 'none'}


def _build_routine_course_entry(assignment, batch):
    from blueprints.class_management.models import Teacher

    if not assignment or not assignment.course:
        return None

    course = assignment.course
    teacher = assignment.teacher
    if not teacher and assignment.teacher_id:
        teacher = Teacher.query.get(assignment.teacher_id)

    display_batch = str(batch or assignment.batch or '').strip()
    credit = float(course.credit or 0)
    course_type = course.course_type or 'Theory'
    section = assignment.section or 'Full'

    if course_type == 'Sessional':
        total_classes = int(credit * 2)
    else:
        total_classes = int(credit)

    if section in ['A', 'B']:
        classes_per_week = total_classes // 2
    else:
        classes_per_week = total_classes

    return {
        'assigned_id': str(assignment.id),
        'course_code': course.course_code or '',
        'course_name': course.course_name or '',
        'course_type': course_type,
        'credit': credit,
        'part': f'Part {section}' if section in ['A', 'B'] else 'Full',
        'classes_per_week': classes_per_week,
        'is_shared_slot': False,
        'teacher_id': teacher.id if teacher else None,
        'year': assignment.year or '',
        'term': assignment.term or '',
        'batch': display_batch,
        'teachers': [{
            'id': teacher.id,
            'name': teacher.name,
            'short_name': teacher.call_sign or getattr(teacher, 'short_name', ''),
        }] if teacher else [],
    }


def _assignment_part_label(section):
    section = str(section or '').strip()
    if section in ('A', 'B'):
        return f'Part {section}'
    return 'Full'


def _sync_routine_teachers_from_assignment(assignment, new_teacher, old_teacher_id=None):
    """Update denormalized teacher fields on matching routine rows when curriculum assignment changes."""
    from sqlalchemy import text, inspect

    if not assignment or not new_teacher:
        return 0

    course = assignment.course
    course_code = (course.course_code if course else '') or ''
    course_code = str(course_code).strip()
    if not course_code:
        return 0

    call_sign = new_teacher.call_sign or getattr(new_teacher, 'short_name', '') or ''
    year = str(assignment.year or '').strip()
    term = str(assignment.term or '').strip()
    batch = str(assignment.batch or '').strip()
    part = _assignment_part_label(assignment.section)

    try:
        routine_columns = {col['name'] for col in inspect(db.engine).get_columns('routine')}
    except Exception:
        routine_columns = set()

    where_parts = [
        "course_code = :code",
        "COALESCE(year, '') = :year",
        "COALESCE(term, '') = :term",
    ]
    params = {
        'new_tid': new_teacher.id,
        'call_sign': call_sign,
        'code': course_code,
        'year': year,
        'term': term,
    }

    if 'batch' in routine_columns and batch:
        where_parts.append("(COALESCE(batch, '') = :batch OR COALESCE(batch, '') = '')")
        params['batch'] = batch

    if 'part' in routine_columns and part:
        where_parts.append("(COALESCE(part, '') = :part OR COALESCE(part, '') = '' OR :part = 'Full')")
        params['part'] = part

    if old_teacher_id:
        where_parts.append("(teacher_id = :old_tid OR teacher_id IS NULL)")
        params['old_tid'] = old_teacher_id

    if 'is_custom' in routine_columns:
        where_parts.append("(is_custom IS NULL OR is_custom = 0)")

    sql = f"""
        UPDATE routine
        SET teacher_id = :new_tid, teacher_short_name = :call_sign
        WHERE {' AND '.join(where_parts)}
    """
    try:
        result = db.session.execute(text(sql), params)
        return result.rowcount or 0
    except Exception as e:
        current_app.logger.warning(f'Could not sync routine teachers for assignment {getattr(assignment, "id", None)}: {e}')
        return 0


def _enrich_routine_entries_with_live_teachers(routine_data, persist=False, saved_routine_id=None):
    """Overlay current curriculum teacher/callsign onto loaded routine entries.

    When persist=True, also write updated teacher fields back to the routine table
    so exports/PDFs stay in sync without requiring a manual Save.
    """
    from blueprints.course_management.models import CourseSessionAssignment
    from sqlalchemy import text, inspect

    if not routine_data:
        return routine_data

    try:
        assignments = _query_for_routine_window(CourseSessionAssignment).all()
    except Exception as e:
        current_app.logger.warning(f'Could not load assignments to enrich routine teachers: {e}')
        return routine_data

    by_key = {}
    by_nobatch = {}
    by_loose = {}
    by_code_part = {}
    part_ab = {}  # (code, year, term, batch) -> {'A': payload, 'B': payload}

    def _put(store, key, value):
        prev = store.get(key)
        if not prev or (value.get('assignment_id') or 0) >= (prev.get('assignment_id') or 0):
            store[key] = value

    for assignment in assignments:
        course = assignment.course
        if not course or not course.course_code:
            continue
        code = str(course.course_code).strip()
        year = str(assignment.year or '').strip()
        term = str(assignment.term or '').strip()
        batch = str(assignment.batch or '').strip()
        part = _assignment_part_label(assignment.section)
        teacher = assignment.teacher
        if not teacher and assignment.teacher_id:
            teacher = Teacher.query.get(assignment.teacher_id)
        payload = {
            'teacher_id': teacher.id if teacher else assignment.teacher_id,
            'teacher_short_name': (
                (teacher.call_sign or getattr(teacher, 'short_name', '') or '') if teacher else ''
            ),
            'year': year,
            'term': term,
            'batch': batch,
            'part': part,
            'assignment_id': assignment.id,
            'teachers': [{
                'id': teacher.id,
                'name': teacher.name,
                'short_name': teacher.call_sign or getattr(teacher, 'short_name', ''),
            }] if teacher else [],
        }

        _put(by_key, f'{code}|{year}|{term}|{batch}|{part}', payload)
        _put(by_nobatch, f'{code}|{year}|{term}|{part}', payload)
        _put(by_loose, f'{code}|{batch}|{part}', payload)
        _put(by_code_part, f'{code}|{part}', payload)

        section = str(assignment.section or '').strip()
        if section in ('A', 'B'):
            for ab_batch in ({batch, ''} if batch else {''}):
                ab_map = part_ab.setdefault((code, year, term, ab_batch), {})
                prev = ab_map.get(section)
                if not prev or (payload.get('assignment_id') or 0) >= (prev.get('assignment_id') or 0):
                    ab_map[section] = payload

    # Build Shared overlays from live Part A+B teachers
    for (code, year, term, batch), parts in part_ab.items():
        if 'A' not in parts and 'B' not in parts:
            continue
        teachers = []
        shorts = []
        primary_tid = None
        for sec in ('A', 'B'):
            p = parts.get(sec)
            if not p:
                continue
            for t in (p.get('teachers') or []):
                if t.get('id') is None:
                    continue
                if any(str(existing.get('id')) == str(t.get('id')) for existing in teachers):
                    continue
                teachers.append(t)
                if t.get('short_name'):
                    shorts.append(t['short_name'])
            if primary_tid is None:
                primary_tid = p.get('teacher_id')
        shared_payload = {
            'teacher_id': primary_tid,
            'teacher_short_name': '/'.join(shorts),
            'year': year,
            'term': term,
            'batch': batch,
            'part': 'Shared',
            'assignment_id': max((parts[s].get('assignment_id') or 0) for s in parts),
            'teachers': teachers,
        }
        _put(by_key, f'{code}|{year}|{term}|{batch}|Shared', shared_payload)
        _put(by_nobatch, f'{code}|{year}|{term}|Shared', shared_payload)
        _put(by_loose, f'{code}|{batch}|Shared', shared_payload)
        _put(by_code_part, f'{code}|Shared', shared_payload)

    pending_writes = []
    for entry in routine_data:
        if entry.get('is_custom'):
            continue
        code = str(entry.get('course_code') or '').strip()
        if not code:
            continue
        year = str(entry.get('year') or '').strip()
        term = str(entry.get('term') or '').strip()
        batch = str(entry.get('batch') or '').strip()
        part = str(entry.get('part') or 'Full').strip() or 'Full'
        day = entry.get('day') or ''
        slot = entry.get('slot') or ''
        room_number = entry.get('room_number') or ''

        match = by_key.get(f'{code}|{year}|{term}|{batch}|{part}')
        if not match:
            match = by_nobatch.get(f'{code}|{year}|{term}|{part}')
        if not match:
            match = by_loose.get(f'{code}|{batch}|{part}')
        if not match:
            match = by_code_part.get(f'{code}|{part}')
        if not match:
            continue

        new_short = match.get('teacher_short_name') or ''
        new_tid = match.get('teacher_id')
        old_short = str(entry.get('teacher_short_name') or '')
        old_tid = entry.get('teacher_id')

        teacher_changed = (
            (new_short and new_short != old_short) or
            (new_tid and str(new_tid) != str(old_tid or '')) or
            (not new_short and old_short) or
            (not new_tid and old_tid)
        )

        entry['teacher_short_name'] = new_short
        entry['teacher_id'] = new_tid
        if match.get('teachers') is not None:
            entry['teachers'] = match.get('teachers')
        if not year and match.get('year'):
            entry['year'] = match['year']
        if not term and match.get('term'):
            entry['term'] = match['term']
        if not batch and match.get('batch'):
            entry['batch'] = match['batch']

        if persist and teacher_changed and day and slot and room_number:
            pending_writes.append({
                'new_tid': new_tid,
                'call_sign': new_short,
                'day': day,
                'slot': slot,
                'room': room_number,
                'code': code,
                'saved_routine_id': saved_routine_id,
            })

    if persist and pending_writes:
        try:
            routine_columns = {col['name'] for col in inspect(db.engine).get_columns('routine')}
            has_saved_id = 'saved_routine_id' in routine_columns
            for write in pending_writes:
                where = "day = :day AND time_slot = :slot AND room_number = :room AND course_code = :code"
                params = dict(write)
                if has_saved_id and saved_routine_id:
                    where += " AND saved_routine_id = :saved_routine_id"
                else:
                    params.pop('saved_routine_id', None)
                db.session.execute(
                    text(f"UPDATE routine SET teacher_id = :new_tid, teacher_short_name = :call_sign WHERE {where}"),
                    params,
                )
            db.session.commit()
            current_app.logger.info(f'Persisted live teacher sync on {len(pending_writes)} routine row(s)')
        except Exception as e:
            db.session.rollback()
            current_app.logger.warning(f'Could not persist routine teacher sync: {e}')

    return routine_data


def _find_assignment_for_registration(registration, batch, semester=None):
    from blueprints.course_management.models import CourseSessionAssignment

    assignments = (
        _assignments_for_semester(semester)
        if semester is not None
        else _assignments_for_routine_batch(batch)
    )
    for assignment in assignments:
        if registration.course_id and assignment.course_id != registration.course_id:
            continue
        if not registration.course_id:
            course_code = str(registration.course_code or '').strip()
            if course_code and assignment.course and (assignment.course.course_code or '').strip() != course_code:
                continue
        if _semester_field_matches(assignment.year, registration.year) and _semester_field_matches(
            assignment.term, registration.term
        ):
            session_value = str(assignment.academic_session or '').strip()
            reg_session = str(registration.academic_session or '').strip()
            if not session_value or not reg_session or session_value == reg_session:
                return assignment
    return None


def _teacher_ids_linked_to_routine_window():
    """Teachers referenced by window-scoped routine assignments."""
    from blueprints.course_management.models import CourseSessionAssignment

    teacher_ids = set()
    for row in _query_for_routine_window(AssignedCourse).with_entities(AssignedCourse.teacher_id).distinct():
        if row[0]:
            teacher_ids.add(row[0])
    for row in _query_for_routine_window(CourseSessionAssignment).with_entities(
        CourseSessionAssignment.teacher_id,
    ).distinct():
        if row[0]:
            teacher_ids.add(row[0])
    for row in _query_for_routine_window(Routine).with_entities(Routine.teacher_id).filter(
        Routine.teacher_id.isnot(None),
    ).distinct():
        if row[0]:
            teacher_ids.add(row[0])
    return teacher_ids


def get_teachers_for_routine_window():
    """Teachers scoped to the current operational window."""
    from role_utils import get_teachers_excluding_head

    scoped_ids = {
        row[0] for row in _query_for_routine_window(Teacher).with_entities(Teacher.id)
    }
    allowed_ids = scoped_ids | _teacher_ids_linked_to_routine_window()
    return [t for t in get_teachers_excluding_head() if t.id in allowed_ids]


def get_rooms_for_routine_window():
    return _query_for_routine_window(Room).order_by(Room.room_number).all()


def _course_ids_for_routine_window():
    from blueprints.course_management.models import CourseSessionAssignment, CourseWindowOffered

    window_id = _routine_window_id()
    course_ids = set()

    for row in _query_for_routine_window(CourseSessionAssignment).with_entities(
        CourseSessionAssignment.course_id,
    ).distinct():
        if row[0]:
            course_ids.add(row[0])
    for row in _query_for_routine_window(AssignedCourse).with_entities(AssignedCourse.course_id).distinct():
        if row[0]:
            course_ids.add(row[0])
    for row in db.session.query(CourseWindowOffered.course_id).filter_by(
        window_id=window_id,
        offered=True,
    ):
        if row[0]:
            course_ids.add(row[0])

    for course in Course.query.all():
        if course.is_offered(window_id):
            course_ids.add(course.id)

    return course_ids


def get_courses_for_routine_window():
    course_ids = _course_ids_for_routine_window()
    if not course_ids:
        return []
    return Course.query.filter(Course.id.in_(course_ids)).order_by(Course.course_code).all()


def _get_teacher_for_routine_or_404(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    allowed_ids = {t.id for t in get_teachers_for_routine_window()}
    if teacher.id not in allowed_ids:
        from flask import abort
        abort(404)
    return teacher


def _get_room_for_routine_or_404(room_id):
    return get_or_404_for_window(Room, room_id, admin_override=False)


def _window_sql_clause(column='window_id'):
    """Append to raw SQL WHERE clauses for saved_routine / routine tables."""
    window_id = _routine_window_id()
    if window_id == DEFAULT_WINDOW_ID:
        return f' AND ({column} = :_window_id OR {column} IS NULL)', {'_window_id': window_id}
    return f' AND {column} = :_window_id', {'_window_id': window_id}


def _get_saved_routine_or_404(saved_routine_id):
    return get_or_404_for_window(SavedRoutine, saved_routine_id, admin_override=False)


def _current_window_id():
    return _routine_window_id()


# Main dashboard for routine management
@routine_management_bp.route('/')
@login_required
def index():
    can_edit = can_edit_routine()
    # If user doesn't have Routine Maker assignment, redirect to public routines
    if not can_edit:
        return redirect(url_for('routine_management.public_routines'))
    
    # Use raw SQL to avoid ORM relationship issues
    from sqlalchemy import text
    try:
        wclause, wparams = _window_sql_clause()
        result = db.session.execute(text(f"""
            SELECT id, year, name, is_revealed, created_at, updated_at 
            FROM saved_routine 
            WHERE 1=1{wclause}
            ORDER BY year DESC
        """), wparams)
        rows = result.fetchall()
        
        # Convert to objects for template compatibility
        saved_routines = []
        for row in rows:
            # Format dates for display (UTC → Bangladesh Time)
            updated_at_display = format_bd(row[5] or row[4], '%Y-%m-%d %H:%M', default='N/A')
            
            sr = type('SavedRoutine', (), {
                'id': row[0],
                'year': row[1],
                'name': row[2] or row[1],
                'is_revealed': row[3] if row[3] is not None else False,
                'created_at': row[4],
                'updated_at': row[5],
                'updated_at_display': updated_at_display
            })()
            saved_routines.append(sr)
    except Exception as e:
        current_app.logger.error(f'Error loading saved routines: {e}', exc_info=True)
        saved_routines = []
    
    return render_template('routine_management/index.html', 
                          saved_routines=saved_routines,
                          can_edit=can_edit)

# Public Routines - Accessible to all users (students and non-routine maker teachers)
@routine_management_bp.route('/public-routines')
@login_required
def public_routines():
    """View public (revealed) routines - accessible to all users"""
    from utils.dashboard_settings import require_student_dashboard_card, require_officer_dashboard_card
    blocked = require_student_dashboard_card('class_routine')
    if blocked:
        return blocked
    blocked = require_officer_dashboard_card('class_routine')
    if blocked:
        return blocked
    from sqlalchemy import text
    
    can_edit = can_edit_routine()
    
    # If user can edit, they should use the main dashboard instead
    if can_edit:
        return redirect(url_for('routine_management.index'))
    
    try:
        wclause, wparams = _window_sql_clause()
        result = db.session.execute(text(f"""
            SELECT id, year, name, is_revealed, created_at, updated_at 
            FROM saved_routine 
            WHERE is_revealed = 1{wclause}
            ORDER BY year DESC
        """), wparams)
        rows = result.fetchall()
        
        # Convert to objects for template compatibility
        revealed_routines = []
        for row in rows:
            updated_at_display = format_bd(row[5] or row[4], '%Y-%m-%d %H:%M', default='N/A')
            
            sr = type('SavedRoutine', (), {
                'id': row[0],
                'year': row[1],
                'name': row[2] or row[1],
                'is_revealed': row[3] if row[3] is not None else False,
                'created_at': row[4],
                'updated_at': row[5],
                'updated_at_display': updated_at_display
            })()
            revealed_routines.append(sr)
    except Exception as e:
        current_app.logger.error(f'Error loading revealed routines: {e}', exc_info=True)
        revealed_routines = []
    
    return render_template('routine_management/public_routines.html', 
                          revealed_routines=revealed_routines,
                          can_edit=False)

# Teacher Management
@routine_management_bp.route('/teachers', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'head', 'officer')
def manage_teachers():
    form = TeacherForm()
    if form.validate_on_submit():
        new_teacher = Teacher(name=form.name.data, short_name=form.short_name.data, institute=current_tenant().institute_label)
        stamp_window_id(new_teacher)
        db.session.add(new_teacher)
        db.session.commit()
        flash('Teacher added successfully!', 'success')
        return redirect(url_for('routine_management.manage_teachers'))
    # Get teachers excluding Head, Teaching Assistants, and Admin users
    teachers = get_teachers_for_routine_window()
    return render_template('routine_management/teachers.html', form=form, teachers=teachers)

@routine_management_bp.route('/teacher/edit/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'head', 'officer')
def edit_teacher(id):
    from user_models import User
    
    teacher = _get_teacher_for_routine_or_404(id)
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
@role_required('admin', 'head')
def delete_teacher(id):
    """Delete a teacher and all related data"""
    teacher = _get_teacher_for_routine_or_404(id)
    
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
        
        # Delete assigned courses and routine entries for this teacher (all windows)
        AssignedCourse.query.filter_by(teacher_id=id).delete(synchronize_session=False)
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
@login_required
@role_required('admin', 'head', 'officer')
def manage_rooms():
    form = RoomForm()
    if form.validate_on_submit():
        new_room = Room(room_number=form.room_number.data)
        stamp_window_id(new_room)
        db.session.add(new_room)
        db.session.commit()
        flash('Room added successfully!', 'success')
        return redirect(url_for('routine_management.manage_rooms'))
    rooms = get_rooms_for_routine_window()
    return render_template('routine_management/rooms.html', form=form, rooms=rooms)

@routine_management_bp.route('/room/delete/<int:id>', methods=['POST'])
@login_required
@role_required('admin', 'head', 'officer')
def delete_room(id):
    """Delete a room"""
    try:
        room = _get_room_for_routine_or_404(id)
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
    form.teacher.choices = [(t.id, f"{t.name} ({t.short_name})") for t in get_teachers_for_routine_window()]

    # Centralized logic to get available courses
    all_assignments = _query_for_routine_window(AssignedCourse).all()
    assigned_parts_by_course = defaultdict(set)
    for a in all_assignments:
        assigned_parts_by_course[a.course_id].add(a.part)

    fully_assigned_course_ids = {
        cid for cid, parts in assigned_parts_by_course.items()
        if 'Full' in parts or {'Part A', 'Part B'}.issubset(parts)
    }
    
    available_courses = [
        c for c in get_courses_for_routine_window()
        if c.id not in fully_assigned_course_ids
    ]
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
        stamp_window_id(assignment)
        db.session.add(assignment)
        db.session.commit()
        flash('Course assigned successfully!', 'success')
        return redirect(url_for('routine_management.assign_course'))

    # Logic to display existing assignments
    assignments_by_teacher = defaultdict(lambda: {'assignments': [], 'total_credit': 0.0})
    all_assignments_sorted = _query_for_routine_window(AssignedCourse).join(Teacher).order_by(Teacher.name, AssignedCourse.id.desc()).all()

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
    assignment = get_or_404_for_window(AssignedCourse, id, admin_override=False)
    form = AssignCourseForm(obj=assignment)
    form.teacher.choices = [(t.id, f"{t.name} ({t.short_name})") for t in get_teachers_for_routine_window()]
    form.course.choices = [(assignment.course.id, f"{assignment.course.course_code} - {assignment.course.course_name}")]

    other_assignments = _query_for_routine_window(AssignedCourse).filter(
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
        assignment = get_or_404_for_window(AssignedCourse, id, admin_override=False)
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
        routine_maker = _query_for_routine_window(DutyAssignment).filter_by(
            assigned_teacher_id=teacher.id,
            duty_type='routine_maker',
            status='active'
        ).first()
        if routine_maker:
            return True
    
    # No Routine Maker assignment - user can only view, not edit
    return False


def _resolve_current_teacher():
    """Best-effort Teacher row for the logged-in user."""
    full_name = (getattr(current_user, 'full_name', None) or '').strip()
    if not full_name:
        return None

    teacher = Teacher.query.filter_by(name=full_name).first()
    if teacher:
        return teacher

    teacher = Teacher.query.filter(func.lower(Teacher.name) == full_name.lower()).first()
    if teacher:
        return teacher

    teacher = Teacher.query.filter(func.lower(Teacher.name).like(f'%{full_name.lower()}%')).first()
    return teacher


def _collect_teacher_assigned_course_codes(teacher):
    """Course codes assigned to a teacher (curriculum + routine maker tables + placed routine cells)."""
    from blueprints.course_management.models import CourseSessionAssignment

    codes = set()
    if not teacher:
        return codes

    # Primary source used by routine maker course palette
    for assignment in _query_for_routine_window(CourseSessionAssignment).filter_by(
        teacher_id=teacher.id
    ).all():
        course = getattr(assignment, 'course', None)
        code = str(getattr(course, 'course_code', '') or '').strip()
        if code:
            codes.add(code)

    # Legacy / alternate assignment table
    for assignment in _query_for_routine_window(AssignedCourse).filter_by(
        teacher_id=teacher.id
    ).all():
        course = getattr(assignment, 'course', None)
        code = str(getattr(course, 'course_code', '') or '').strip()
        if code:
            codes.add(code)

    # Codes already placed on routines for this teacher in the current window
    short_names = {
        str(getattr(teacher, 'call_sign', '') or '').strip(),
        str(getattr(teacher, 'short_name', '') or '').strip(),
    }
    short_names = {s for s in short_names if s}

    routine_filters = [Routine.teacher_id == teacher.id]
    if short_names:
        routine_filters.append(Routine.teacher_short_name.in_(list(short_names)))
        # Shared teachers may be stored as "AB/CD"
        for short in short_names:
            routine_filters.append(Routine.teacher_short_name.ilike(f'%{short}%'))

    routine_rows = _query_for_routine_window(Routine).filter(or_(*routine_filters)).all()
    for row in routine_rows:
        code = str(getattr(row, 'course_code', '') or '').strip()
        if code:
            codes.add(code)

    return codes


def _get_viewer_course_filter_context():
    """Course codes for filter presets (student registered / teacher assigned)."""
    from role_utils import has_teacher_privileges
    from utils.window_utils import filter_by_active_window

    roles = parse_roles(getattr(current_user, 'role', None))
    is_student = 'student' in roles and not has_teacher_privileges(current_user)

    if is_student:
        from blueprints.student_management.models import Student
        from blueprints.course_management.models import StudentCourseRegistration

        codes = []
        student = Student.query.filter_by(student_id=getattr(current_user, 'username', None)).first()
        if student:
            query = StudentCourseRegistration.query.filter(
                StudentCourseRegistration.student_id == student.id,
                StudentCourseRegistration.status != 'archived',
            )
            try:
                query = filter_by_active_window(query, StudentCourseRegistration, admin_override=False)
            except Exception:
                pass
            codes = sorted({
                str(reg.course_code or '').strip()
                for reg in query.all()
                if str(reg.course_code or '').strip()
            })
        return {
            'viewer_type': 'student',
            'my_course_codes': codes,
            'my_courses_label': 'My registered courses',
            'my_teacher_id': None,
            'my_teacher_shorts': [],
        }

    if has_teacher_privileges(current_user):
        teacher = _resolve_current_teacher()
        codes = sorted(_collect_teacher_assigned_course_codes(teacher)) if teacher else []
        shorts = []
        teacher_id = None
        if teacher:
            teacher_id = teacher.id
            for value in (
                getattr(teacher, 'call_sign', None),
                getattr(teacher, 'short_name', None),
            ):
                text_value = str(value or '').strip()
                if text_value and text_value not in shorts:
                    shorts.append(text_value)
        return {
            'viewer_type': 'teacher',
            'my_course_codes': codes,
            'my_courses_label': 'My assigned courses',
            'my_teacher_id': teacher_id,
            'my_teacher_shorts': shorts,
        }

    return {
        'viewer_type': 'other',
        'my_course_codes': [],
        'my_courses_label': 'My courses',
        'my_teacher_id': None,
        'my_teacher_shorts': [],
    }


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
            routine_maker = _query_for_routine_window(DutyAssignment).filter(
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
            discipline_head = _query_for_routine_window(DutyAssignment).filter(
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
    """View routine - accessible to all users, but only routine makers can edit"""
    from utils.dashboard_settings import require_student_dashboard_card, require_officer_dashboard_card
    blocked = require_student_dashboard_card('class_routine')
    if blocked:
        return blocked
    blocked = require_officer_dashboard_card('class_routine')
    if blocked:
        return blocked
    from blueprints.course_management.models import Curriculum
    from sqlalchemy import text, inspect

    can_edit = can_edit_routine()
    
    # Get saved_routine_id from URL query params
    saved_routine_id = request.args.get('saved_routine_id', type=int)
    
    # If no saved_routine_id provided and user can't edit, redirect to public routines
    if not saved_routine_id and not can_edit:
        return redirect(url_for('routine_management.public_routines'))
    
    # Load saved routine if ID provided
    current_saved_routine = None
    if saved_routine_id:
        current_saved_routine = _get_saved_routine_or_404(saved_routine_id)
        if not current_saved_routine:
            flash('Routine not found', 'error')
            if can_edit:
                return redirect(url_for('routine_management.index'))
            else:
                return redirect(url_for('routine_management.public_routines'))
        
        # For non-editors, check if the routine is revealed (public)
        if not can_edit and not current_saved_routine.is_revealed:
            flash('This routine is not available for viewing.', 'warning')
            return redirect(url_for('routine_management.public_routines'))
    
    # Get all teachers (for display purposes)
    teachers_list = get_teachers_for_routine_window()
    teachers = [{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in teachers_list]
    
    # Get all curricula for selection
    curricula = Curriculum.query.order_by(Curriculum.name.desc()).all()
    
    rooms = get_rooms_for_routine_window()
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]

    # If editing/viewing a saved routine, load its custom time slots + break settings
    lunch_after_slot = 3
    break_type = 'lunch'
    break_time_label = '01:00 PM - 02:00 PM'
    if saved_routine_id:
        try:
            # Load time slots (if routine_time_slot exists)
            try:
                rows = db.session.execute(
                    text("SELECT time_slot FROM routine_time_slot WHERE saved_routine_id = :id ORDER BY display_order"),
                    {'id': saved_routine_id}
                ).fetchall()
                loaded_slots = [r[0] for r in rows if r and r[0]]
                if loaded_slots:
                    time_slots = loaded_slots
            except Exception as e:
                current_app.logger.warning(f'Could not load routine_time_slot for view_routine {saved_routine_id}: {e}')

            # Load break settings if columns exist in saved_routine
            sr_cols = [c['name'] for c in inspect(db.engine).get_columns('saved_routine')]
            if 'lunch_after_slot' in sr_cols and 'break_type' in sr_cols and 'break_time_label' in sr_cols:
                br = db.session.execute(
                    text("SELECT lunch_after_slot, break_type, break_time_label FROM saved_routine WHERE id = :id"),
                    {'id': saved_routine_id}
                ).fetchone()
                if br:
                    lunch_after_slot = br[0] if br[0] is not None else 3
                    break_type = (br[1] or 'lunch').strip() or 'lunch'
                    break_time_label = (br[2] or '01:00 PM - 02:00 PM').strip() or '01:00 PM - 02:00 PM'
        except Exception as e:
            current_app.logger.warning(f'Could not load saved routine meta for view_routine {saved_routine_id}: {e}')

    # can_edit is already defined at the beginning of this function
    viewer_filter = _get_viewer_course_filter_context()
    return render_template('routine_management/routine_new.html', 
                           teachers=teachers, rooms=rooms, days=days, 
                           time_slots=time_slots, curricula=curricula,
                           can_edit=can_edit,
                           saved_routine_id=saved_routine_id,
                           current_saved_routine=current_saved_routine,
                           lunch_after_slot=lunch_after_slot,
                           break_type=break_type,
                           break_time_label=break_time_label,
                           viewer_type=viewer_filter.get('viewer_type', 'other'),
                           my_course_codes=viewer_filter.get('my_course_codes', []),
                           my_courses_label=viewer_filter.get('my_courses_label', 'My courses'),
                           my_teacher_id=viewer_filter.get('my_teacher_id'),
                           my_teacher_shorts=viewer_filter.get('my_teacher_shorts', []))

# Generate Routine (Only for Routine Makers)
@routine_management_bp.route('/generate_routine')
@login_required
def generate_routine():
    from blueprints.course_management.models import Curriculum
    from sqlalchemy import text, inspect
    
    # Only routine makers can access this route
    can_edit = can_edit_routine()
    if not can_edit:
        flash('You do not have permission to edit routines.', 'warning')
        return redirect(url_for('routine_management.public_routines'))
    
    # Get saved_routine_id from URL query params
    saved_routine_id = request.args.get('saved_routine_id', type=int)
    
    # Load saved routine if ID provided
    current_saved_routine = None
    if saved_routine_id:
        current_saved_routine = _get_saved_routine_or_404(saved_routine_id)
        if not current_saved_routine:
            flash('Routine not found', 'error')
            return redirect(url_for('routine_management.index'))
    
    # Get all teachers
    teachers_list = get_teachers_for_routine_window()
    teachers = [{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in teachers_list]
    
    # Get all curricula for selection
    curricula = Curriculum.query.order_by(Curriculum.name.desc()).all()
    
    rooms = get_rooms_for_routine_window()
    days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = [
        "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
        "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM", 
        "04:00 PM - 04:50 PM"
    ]

    # If editing a saved routine, load its custom time slots + break settings
    lunch_after_slot = 3
    break_type = 'lunch'
    break_time_label = '01:00 PM - 02:00 PM'
    if saved_routine_id:
        try:
            try:
                rows = db.session.execute(
                    text("SELECT time_slot FROM routine_time_slot WHERE saved_routine_id = :id ORDER BY display_order"),
                    {'id': saved_routine_id}
                ).fetchall()
                loaded_slots = [r[0] for r in rows if r and r[0]]
                if loaded_slots:
                    time_slots = loaded_slots
            except Exception as e:
                current_app.logger.warning(f'Could not load routine_time_slot for generate_routine {saved_routine_id}: {e}')

            sr_cols = [c['name'] for c in inspect(db.engine).get_columns('saved_routine')]
            if 'lunch_after_slot' in sr_cols and 'break_type' in sr_cols and 'break_time_label' in sr_cols:
                br = db.session.execute(
                    text("SELECT lunch_after_slot, break_type, break_time_label FROM saved_routine WHERE id = :id"),
                    {'id': saved_routine_id}
                ).fetchone()
                if br:
                    lunch_after_slot = br[0] if br[0] is not None else 3
                    break_type = (br[1] or 'lunch').strip() or 'lunch'
                    break_time_label = (br[2] or '01:00 PM - 02:00 PM').strip() or '01:00 PM - 02:00 PM'
        except Exception as e:
            current_app.logger.warning(f'Could not load saved routine meta for generate_routine {saved_routine_id}: {e}')

    # can_edit is already defined at the beginning of this function
    viewer_filter = _get_viewer_course_filter_context()
    return render_template('routine_management/routine_new.html', 
                           teachers=teachers, rooms=rooms, days=days, 
                           time_slots=time_slots, curricula=curricula,
                           can_edit=can_edit,
                           saved_routine_id=saved_routine_id,
                           current_saved_routine=current_saved_routine,
                           lunch_after_slot=lunch_after_slot,
                           break_type=break_type,
                           break_time_label=break_time_label,
                           viewer_type=viewer_filter.get('viewer_type', 'other'),
                           my_course_codes=viewer_filter.get('my_course_codes', []),
                           my_courses_label=viewer_filter.get('my_courses_label', 'My courses'),
                           my_teacher_id=viewer_filter.get('my_teacher_id'),
                           my_teacher_shorts=viewer_filter.get('my_teacher_shorts', []))

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
        teacher = _get_teacher_for_routine_or_404(teacher_id)
        if not teacher:
            return jsonify([])
        
        # Get all CourseSessionAssignment for this teacher (no filters for now)
        assignments = _query_for_routine_window(CourseSessionAssignment).filter_by(teacher_id=teacher_id).all()
        
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
            
            # FIXED: Use floor division for individual parts
            # For odd credit courses, remaining class goes to shared slot
            if section in ['A', 'B']:
                classes_per_week = total_classes // 2
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

            # Handle shared courses (odd-credit courses with Part A and Part B)
            if total_classes % 2 == 1 and section == 'A':
                # Check if there's a Part B assignment for the same course
                other_assignment = _query_for_routine_window(CourseSessionAssignment).filter(
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
    teachers_list = get_teachers_for_routine_window()
    return jsonify([{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in teachers_list])

@routine_management_bp.route('/api/batches')
@login_required
def get_batches():
    """Active semester contexts for the routine course sidebar."""
    try:
        window_id = _routine_window_id()
        contexts = _semester_contexts_for_routine()
        batches = sorted(_batches_for_active_semesters(), reverse=True)
        current_app.logger.info(
            f'Loaded {len(contexts)} active-semester context(s) for window {window_id}'
        )

        return jsonify({
            'success': True,
            'contexts': contexts,
            'batches': batches,
            'window_id': window_id,
        }), 200

    except Exception as e:
        current_app.logger.error(f'Error getting batches: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error getting batches: {str(e)}',
            'contexts': [],
            'batches': []
        }), 500

@routine_management_bp.route('/api/courses/batch-wise')
@login_required
def get_courses_batch_wise():
    """Courses for one active semester context (preferred) or legacy batch number."""
    try:
        from blueprints.course_management.models import StudentCourseRegistration
        from blueprints.student_management.models import Student

        semester_id = request.args.get('semester_id', type=int)
        batch = request.args.get('batch', '').strip()
        semester = _get_active_semester_by_id(semester_id)
        sibling_semesters = _sibling_semesters_for(semester) if semester else []
        sibling_batches = []
        for sib in sibling_semesters:
            sib_batch = str(sib.batch or '').strip()
            if sib_batch and sib_batch.lower() != 'none' and sib_batch not in sibling_batches:
                sibling_batches.append(sib_batch)

        if semester:
            # Merged year/term context: do not pin courses to a single batch
            batch = ''
        elif not batch:
            return jsonify({
                'success': False,
                'message': 'semester_id or batch parameter is required'
            }), 400

        response_key = (
            f"{semester.year}_{semester.term}_{semester.academic_session or 'na'}"
            if semester else (batch or 'all')
        )

        if semester:
            if semester.window_id and semester.window_id != _routine_window_id():
                current_app.logger.warning(
                    'Routine window %s loading semester %s from window %s',
                    _routine_window_id(),
                    semester.id,
                    semester.window_id,
                )
            assignments = _assignments_for_semester(semester)
        else:
            allowed_batches = _batches_for_active_semesters()
            if batch and batch not in allowed_batches:
                return jsonify({
                    'success': True,
                    'courses': [],
                    'courses_by_batch': {response_key: []},
                }), 200
            assignments = _assignments_for_routine_batch(batch)

        current_app.logger.info(
            f'Found {len(assignments)} assignment(s) for '
            f'semester_id={semester_id} siblings={len(sibling_semesters)} '
            f'batches={sibling_batches or [batch]} window={_routine_window_id()}'
        )

        courses_by_batch = {response_key: []}
        courses_list = []
        seen_keys = set()
        part_a_assignments = {}
        # Track newest assigned_id per (dedupe_key, batch) so same-batch reassigns
        # replace the teacher instead of stacking stale ones.
        batch_assignment_ids = {}

        def _parse_assigned_id(value):
            raw = str(value or '').strip()
            if not raw:
                return 0
            # Shared ids look like shared_12_34 — use max numeric fragment
            nums = [int(p) for p in raw.replace('shared_', '').split('_') if p.isdigit()]
            return max(nums) if nums else 0

        def _append_course_entry(course_data):
            if not course_data:
                return
            # Dedupe by course identity (not teacher/batch) so multi-batch
            # registrations for the same year/term don't duplicate cards.
            dedupe_key = (
                course_data.get('course_code'),
                course_data.get('part'),
                course_data.get('year'),
                course_data.get('term'),
            )
            new_batch = str(course_data.get('batch') or '').strip()
            new_aid = _parse_assigned_id(course_data.get('assigned_id'))

            if dedupe_key in seen_keys:
                for existing in courses_list:
                    if (
                        existing.get('course_code') == course_data.get('course_code')
                        and existing.get('part') == course_data.get('part')
                        and existing.get('year') == course_data.get('year')
                        and existing.get('term') == course_data.get('term')
                    ):
                        is_shared = bool(
                            course_data.get('is_shared_slot') or existing.get('is_shared_slot')
                        )
                        existing_batch = str(existing.get('batch') or '').strip()
                        batch_key = (dedupe_key, new_batch or existing_batch)
                        prev_aid = batch_assignment_ids.get(batch_key, 0)
                        same_or_blank_batch = (
                            (new_batch and existing_batch and new_batch == existing_batch)
                            or (not new_batch and not existing_batch)
                            or (bool(new_batch) != bool(existing_batch))  # one side blank
                        )

                        if not is_shared and same_or_blank_batch:
                            # Same offering (incl. blank-batch legacy rows): keep newest CSA only
                            if new_aid >= prev_aid:
                                existing['teachers'] = list(course_data.get('teachers') or [])
                                existing['teacher_id'] = course_data.get('teacher_id')
                                existing['assigned_id'] = course_data.get('assigned_id')
                                if new_batch:
                                    existing['batch'] = new_batch
                                batch_assignment_ids[batch_key] = new_aid
                                batch_assignment_ids[(dedupe_key, existing_batch)] = new_aid
                            break

                        # Distinct non-empty batches: merge teachers onto one card
                        existing_ids = {
                            str(t.get('id')) for t in (existing.get('teachers') or []) if t.get('id') is not None
                        }
                        for teacher in (course_data.get('teachers') or []):
                            tid = teacher.get('id')
                            if tid is not None and str(tid) not in existing_ids:
                                existing.setdefault('teachers', []).append(teacher)
                                existing_ids.add(str(tid))
                        if new_aid >= prev_aid:
                            batch_assignment_ids[batch_key] = new_aid
                        break
                return
            seen_keys.add(dedupe_key)
            batch_assignment_ids[(dedupe_key, new_batch)] = new_aid
            courses_by_batch[response_key].append(course_data)
            courses_list.append(course_data)

        for assignment in assignments:
            course_data = _build_routine_course_entry(assignment, assignment.batch or '')
            if not course_data:
                continue
            _append_course_entry(course_data)

            section = assignment.section or 'Full'
            credit = float(assignment.course.credit or 0)
            course_type = assignment.course.course_type or 'Theory'
            total_classes = int(credit * 2) if course_type == 'Sessional' else int(credit)
            if section == 'A' and total_classes % 2 == 1:
                part_a_assignments[assignment.course_id] = {
                    'assignment': assignment,
                    'course': assignment.course,
                    'teacher': assignment.teacher,
                    'course_data': course_data,
                }

        for assignment in assignments:
            section = assignment.section or 'Full'
            if section != 'B':
                continue
            course_id = assignment.course_id
            if course_id not in part_a_assignments:
                continue

            part_a_data = part_a_assignments[course_id]
            course = part_a_data['course']
            teacher_a = part_a_data['teacher']
            teacher_b = assignment.teacher
            shared_entry = {
                'assigned_id': f"shared_{part_a_data['assignment'].id}_{assignment.id}",
                'course_code': course.course_code or '',
                'course_name': f"{course.course_name or ''} (Shared)",
                'course_type': course.course_type or 'Theory',
                'credit': float(course.credit or 0),
                'part': 'Shared',
                'classes_per_week': 1,
                'is_shared_slot': True,
                'teacher_id': teacher_a.id if teacher_a else None,
                'year': assignment.year or '',
                'term': assignment.term or '',
                'batch': assignment.batch or '',
                'teachers': [],
            }
            if teacher_a:
                shared_entry['teachers'].append({
                    'id': teacher_a.id,
                    'name': teacher_a.name,
                    'short_name': teacher_a.call_sign or getattr(teacher_a, 'short_name', ''),
                })
            if teacher_b:
                shared_entry['teachers'].append({
                    'id': teacher_b.id,
                    'name': teacher_b.name,
                    'short_name': teacher_b.call_sign or getattr(teacher_b, 'short_name', ''),
                })
            _append_course_entry(shared_entry)

        registration_query = (
            db.session.query(StudentCourseRegistration, Student.batch)
            .join(Student, Student.id == StudentCourseRegistration.student_id)
            .filter(
                StudentCourseRegistration.status != 'archived',
                _window_scope_filter(StudentCourseRegistration, _routine_window_id()),
            )
        )
        if sibling_batches:
            registration_query = registration_query.filter(Student.batch.in_(sibling_batches))
        elif batch:
            registration_query = registration_query.filter(Student.batch == batch)

        for registration, student_batch in registration_query.all():
            if not _is_non_merged_retake_registration(registration):
                continue
            # Match any sibling semester (same session/year/term, any batch)
            if sibling_semesters:
                if not any(
                    _registration_matches_semester(registration, sib, student_batch)
                    for sib in sibling_semesters
                ):
                    continue
            elif semester and not _registration_matches_semester(registration, semester, student_batch):
                continue
            elif not semester and not _matches_any_active_semester(
                registration.academic_session,
                registration.year,
                registration.term,
                student_batch,
            ):
                continue
            assignment = _find_assignment_for_registration(
                registration, student_batch or batch, semester=semester
            )
            if not assignment:
                continue
            course_data = _build_routine_course_entry(assignment, assignment.batch or student_batch or '')
            if course_data:
                course_data['course_name'] = f"{course_data['course_name']} (Retake)"
            _append_course_entry(course_data)

        current_app.logger.info(
            f'Returning {len(courses_list)} courses for semester_id={semester_id} '
            f'batches={sibling_batches or [batch]}'
        )

        return jsonify({
            'success': True,
            'courses': courses_list,
            'courses_by_batch': courses_by_batch,
            'semester_id': semester.id if semester else None,
            'semester_ids': [s.id for s in sibling_semesters] if sibling_semesters else (
                [semester.id] if semester else []
            ),
            'batch': batch,
            'batches': sibling_batches or ([batch] if batch else []),
            'window_id': _routine_window_id(),
        }), 200

    except Exception as e:
        current_app.logger.error(f'Error getting batch courses: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error getting courses: {str(e)}',
            'courses_by_batch': {}
        }), 500

@routine_management_bp.route('/api/courses-by-batch')
@login_required
def get_courses_by_batch():
    """Alternative endpoint for batch courses"""
    return get_courses_batch_wise()


@routine_management_bp.route('/api/routine/auto-fill', methods=['POST'])
@login_required
def auto_fill_routine():
    """Conflict-free greedy placement. Returns the same routine[] shape as /api/routine/save."""
    if not can_edit_routine():
        return jsonify({'success': False, 'message': 'You do not have permission to edit routine.'}), 403
    data = request.get_json(silent=True) or {}
    days = data.get('days') or ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday']
    time_slots = data.get('time_slots') or []
    rooms = data.get('rooms') or []
    courses = data.get('courses') or []
    existing = data.get('existing') or []
    keep_existing = bool(data.get('keep_existing', True))
    preferences = data.get('preferences') or {}
    prompt = data.get('prompt') or preferences.get('prompt') or ''
    clear_selected = bool(data.get('clear_selected'))
    clear_course_ids = data.get('clear_course_ids') or []
    if clear_selected and not clear_course_ids:
        clear_course_ids = [
            str(c.get('assigned_id') or c.get('id') or c.get('course_code') or '').strip()
            for c in courses
            if (c.get('assigned_id') or c.get('id') or c.get('course_code'))
        ]

    if not rooms:
        rooms = [{'id': r.id, 'room_number': r.room_number} for r in get_rooms_for_routine_window()]
    if not time_slots:
        time_slots = [
            "09:10 AM - 10:00 AM", "10:10 AM - 11:00 AM", "11:10 AM - 12:00 PM",
            "12:10 PM - 01:00 PM", "02:00 PM - 02:50 PM", "03:00 PM - 03:50 PM",
            "04:00 PM - 04:50 PM",
        ]
    if not courses:
        return jsonify({'success': False, 'message': 'অটো-সাজানোর জন্য অন্তত একটি সাবজেক্ট বেছে নিন।'}), 400

    from utils.routine_solver import auto_place

    result = auto_place(
        days=days,
        time_slots=time_slots,
        rooms=rooms,
        courses=courses,
        existing=existing,
        keep_existing=keep_existing,
        preferences=preferences,
        prompt=prompt,
        clear_course_ids=clear_course_ids if clear_selected else None,
    )
    return jsonify({
        'success': True,
        'routine': result.get('routine') or [],
        'unplaced': result.get('unplaced') or [],
        'explanations': result.get('explanations') or [],
        'preferences_applied': result.get('preferences_applied') or {},
    })


@routine_management_bp.route('/api/routine/save', methods=['POST'])
@login_required
def save_routine():
    """
    SMART & RELIABLE ROUTINE SAVE FUNCTION
    - Handles all edge cases
    - Uses ORM with fallback to raw SQL
    - Comprehensive error handling
    - Detailed logging
    """
    try:
        # 1. Permission check
        if not can_edit_routine():
            current_app.logger.warning(f'User {current_user.id} attempted to save routine without permission')
            return jsonify({
                'success': False,
                'message': 'You do not have permission to edit routine.',
                'error_type': 'permission_denied'
            }), 403
        
        # 2. Get and validate JSON data
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'message': 'No data provided',
                    'error_type': 'no_data'
                }), 400
        except Exception as json_error:
            current_app.logger.error(f'JSON parse error: {json_error}')
            return jsonify({
                'success': False,
                'message': 'Invalid JSON data',
                'error_type': 'json_error',
                'details': str(json_error)
            }), 400
        
        saved_routine_id = data.get('saved_routine_id')
        routine_entries = data.get('routine', [])
        
        current_app.logger.info(f'Saving routine: saved_routine_id={saved_routine_id}, entries={len(routine_entries)}')
        
        # 3. Validate saved_routine_id if provided
        routine_window_id = _current_window_id()
        if saved_routine_id:
            saved_routine = _get_saved_routine_or_404(saved_routine_id)
            routine_window_id = saved_routine.window_id or routine_window_id
        
        # 4. Check database schema dynamically
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        try:
            columns_info = inspector.get_columns('routine')
            available_columns = [col['name'] for col in columns_info]
            has_saved_routine_id = 'saved_routine_id' in available_columns
            current_app.logger.info(f'Database columns: {available_columns}')
        except Exception as schema_error:
            current_app.logger.error(f'Schema check error: {schema_error}', exc_info=True)
            return jsonify({
                'success': False,
                'message': 'Database schema error. Please contact administrator.',
                'error_type': 'schema_error',
                'details': str(schema_error)
            }), 500
        
        # 5. Validate and prepare entries
        validated_entries = []
        validation_errors = []
        for idx, entry in enumerate(routine_entries):
            # Required fields
            day = entry.get('day', '').strip() if entry.get('day') else ''
            slot = entry.get('slot', '').strip() if entry.get('slot') else ''
            room_id = entry.get('room_id')
            
            if not day or not slot or not room_id:
                validation_errors.append(f'Entry {idx+1}: Missing required fields (day, slot, or room_id)')
                continue
            
            # Validate room exists
            try:
                room = _get_room_for_routine_or_404(int(room_id))
                if not room:
                    validation_errors.append(f'Entry {idx+1}: Room ID {room_id} not found')
                    continue
            except (ValueError, TypeError):
                validation_errors.append(f'Entry {idx+1}: Invalid room_id {room_id}')
                continue
            
            # Prepare entry data
            is_custom = entry.get('is_custom', False)
            custom_course_name = entry.get('custom_course_name', '').strip() or None
            course_code = entry.get('course_code', '').strip() or None
            
            # For custom entries, ensure course_code is set from custom_course_name if needed
            if is_custom and custom_course_name and not course_code:
                course_code = custom_course_name
            
            # Normalize teacher_id: empty string or invalid value -> None (avoids INTEGER/FK error on insert)
            tid = entry.get('teacher_id')
            try:
                teacher_id = int(tid) if tid not in (None, '') else None
            except (ValueError, TypeError):
                teacher_id = None
            
            validated_entries.append({
                'day': day,
                'slot': slot,
                'room': room,
                'course_code': course_code,
                'teacher_short_name': entry.get('teacher_short_name', '').strip() or None,
                'part': entry.get('part', 'Full').strip() or None,
                'teacher_id': teacher_id,
                'is_shared': entry.get('is_shared', False),
                'shared_with': entry.get('shared_with', '').strip() or None,
                'year': entry.get('year', '').strip() or None,
                'term': entry.get('term', '').strip() or None,
                'batch': entry.get('batch', '').strip() or None,
                'color_code': entry.get('color_code', '').strip() or None,
                'is_custom': is_custom,
                'custom_course_name': custom_course_name,
                'placement_order': entry.get('placement_order')
            })
        
        if validation_errors:
            current_app.logger.warning(f'Validation errors: {validation_errors}')
        # 6. Delete existing entries (use raw SQL for reliability)
        try:
            if saved_routine_id and has_saved_routine_id:
                # Delete by saved_routine_id
                db.session.execute(
                    text("DELETE FROM routine WHERE saved_routine_id = :saved_routine_id"),
                    {'saved_routine_id': saved_routine_id}
                )
                current_app.logger.info(f'Deleted existing routines for saved_routine_id={saved_routine_id}')
            elif saved_routine_id:
                # saved_routine_id column doesn't exist, delete all
                db.session.execute(text("DELETE FROM routine"))
                current_app.logger.warning('saved_routine_id column missing, deleted all routines')
            else:
                # No saved_routine_id provided, delete routines without saved_routine_id
                if has_saved_routine_id:
                    db.session.execute(
                        text("DELETE FROM routine WHERE saved_routine_id IS NULL")
                    )
                else:
                    db.session.execute(text("DELETE FROM routine"))
                current_app.logger.info('Deleted existing routines (no saved_routine_id)')
        except Exception as delete_error:
            db.session.rollback()
            current_app.logger.error(f'Error deleting existing routines: {delete_error}', exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Failed to clear existing routine: {str(delete_error)}',
                'error_type': 'delete_error',
                'details': str(delete_error)
            }), 500
        
        # 7. If no entries to save, commit deletion and return
        if not validated_entries:
            try:
                db.session.commit()
                current_app.logger.info('Routine cleared successfully (no entries to save)')
                return jsonify({
                    'success': True,
                    'message': 'Routine cleared successfully!',
                    'entries_saved': 0
                }), 200
            except Exception as commit_error:
                db.session.rollback()
                current_app.logger.error(f'Error committing clear: {commit_error}', exc_info=True)
                return jsonify({
                    'success': False,
                    'message': f'Failed to clear routine: {str(commit_error)}',
                    'error_type': 'commit_error'
                }), 500
        
        # 8. Insert new entries using RAW SQL (bypass ORM schema mismatch)
        saved_count = 0
        errors = []
        
        # Build column list based on what's in database
        base_columns = ['day', 'time_slot', 'room_number', 'course_code', 'teacher_short_name', 
                       'part', 'is_shared', 'shared_with', 'teacher_id', 'year', 'term']
        
        # Check for additional columns
        optional_columns = ['batch', 'color_code', 'is_custom', 'custom_course_name', 'placement_order']
        for col in optional_columns:
            if col in available_columns:
                base_columns.append(col)
        
        # Add saved_routine_id only if it exists in database
        if has_saved_routine_id:
            base_columns.append('saved_routine_id')
        if 'window_id' in available_columns:
            base_columns.append('window_id')
        
        # Build INSERT SQL
        column_names = ', '.join(base_columns)
        placeholders = ', '.join([f':{col}' for col in base_columns])
        insert_sql = f"INSERT INTO routine ({column_names}) VALUES ({placeholders})"
        
        current_app.logger.info(f'Insert SQL: {insert_sql}')
        
        # routine.course_code is VARCHAR(20); custom entry text can be longer - truncate for DB
        course_code_max_len = 20
        for entry_data in validated_entries:
            try:
                course_code_val = (entry_data['course_code'] or '')[:course_code_max_len]
                # Build parameters dict
                params = {
                    'day': entry_data['day'],
                    'time_slot': entry_data['slot'],
                    'room_number': entry_data['room'].room_number,
                    'course_code': course_code_val,
                    'teacher_short_name': entry_data['teacher_short_name'],
                    'part': entry_data['part'],
                    'is_shared': 1 if entry_data['is_shared'] else 0,
                    'shared_with': entry_data['shared_with'],
                    'teacher_id': entry_data['teacher_id'],
                    'year': entry_data['year'],
                    'term': entry_data['term']
                }
                
                # Add optional columns if they exist
                if 'batch' in base_columns:
                    params['batch'] = entry_data['batch']
                if 'color_code' in base_columns:
                    params['color_code'] = entry_data['color_code']
                if 'is_custom' in base_columns:
                    params['is_custom'] = 1 if entry_data['is_custom'] else 0
                if 'custom_course_name' in base_columns:
                    params['custom_course_name'] = entry_data['custom_course_name']
                if 'placement_order' in base_columns:
                    params['placement_order'] = entry_data['placement_order']
                
                # Add saved_routine_id if column exists
                if has_saved_routine_id:
                    params['saved_routine_id'] = saved_routine_id
                if 'window_id' in base_columns:
                    params['window_id'] = routine_window_id
                
                # Execute raw SQL INSERT
                db.session.execute(text(insert_sql), params)
                saved_count += 1
                
            except Exception as entry_error:
                error_msg = f"Error creating entry for {entry_data['day']} {entry_data['slot']}: {str(entry_error)}"
                errors.append(error_msg)
                current_app.logger.error(error_msg, exc_info=True)
                # Continue with other entries
        
        # 9. Commit transaction
        try:
            db.session.commit()
            current_app.logger.info(f'Successfully saved {saved_count} routine entries')
            # Emit WebSocket event if available
            try:
                from utils.websocket_events import emit_routine_updated
                emit_routine_updated({'updated_at': datetime.utcnow().isoformat()})
            except Exception as ws_error:
                current_app.logger.warning(f'WebSocket error (non-critical): {ws_error}')
            
            # Build success message
            message = f'Routine saved successfully! {saved_count} entries saved.'
            if errors:
                message += f' {len(errors)} entries had errors.'
            if validation_errors:
                message += f' {len(validation_errors)} entries were skipped due to validation errors.'
            
            return jsonify({
                'success': True,
                'message': message,
                'entries_saved': saved_count,
                'entries_total': len(validated_entries),
                'errors': errors if errors else None,
                'validation_errors': validation_errors if validation_errors else None
            }), 200
            
        except Exception as commit_error:
            db.session.rollback()
            current_app.logger.error(f'Error committing routine save: {commit_error}', exc_info=True)
            
            # Provide helpful error message
            error_msg = str(commit_error)
            if 'no such column' in error_msg.lower() or 'Unknown column' in error_msg:
                error_msg = 'Database schema mismatch. Please run database migrations.'
            elif 'UNIQUE constraint' in error_msg or 'unique constraint' in error_msg:
                error_msg = 'Duplicate entry detected. Please check for conflicts.'
            elif 'NOT NULL constraint' in error_msg or 'NOT NULL' in error_msg:
                error_msg = 'Required field missing. Please check your data.'
            
            return jsonify({
                'success': False,
                'message': f'Failed to save routine: {error_msg}',
                'error_type': 'commit_error',
                'details': str(commit_error),
                'entries_saved': saved_count
            }), 500
    
    except Exception as e:
        # Catch-all for any unexpected errors
        db.session.rollback()
        current_app.logger.error(f'Unexpected error in save_routine: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}',
            'error_type': 'unexpected_error',
            'details': str(e)
        }), 500

@routine_management_bp.route('/api/routine/clear', methods=['POST'])
@login_required
def clear_routine():
    if not can_edit_routine():
        return jsonify({'message': 'You do not have permission to clear routine.'}), 403
    
    try:
        _query_for_routine_window(Routine).delete()
        db.session.commit()
        return jsonify({'message': 'Routine cleared successfully!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 500

# Saved Routines API Endpoints
@routine_management_bp.route('/api/saved-routines', methods=['GET'])
@login_required
def get_saved_routines():
    """Get all saved routines using raw SQL"""
    from sqlalchemy import text
    try:
        wclause, wparams = _window_sql_clause()
        result = db.session.execute(text(f"""
            SELECT id, year, name, is_revealed, created_at, updated_at 
            FROM saved_routine 
            WHERE 1=1{wclause}
            ORDER BY year DESC
        """), wparams)
        rows = result.fetchall()
        
        routines_data = []
        for row in rows:
            routines_data.append({
                'id': row[0],
                'year': row[1],
                'name': row[2] or row[1],
                'is_revealed': row[3] if row[3] is not None else False,
                'created_at': row[4].isoformat() if row[4] else None,
                'updated_at': row[5].isoformat() if row[5] else None
            })
        return jsonify(routines_data), 200
    except Exception as e:
        current_app.logger.error(f'Error getting saved routines: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error fetching saved routines: {str(e)}'
        }), 500

@routine_management_bp.route('/api/saved-routines', methods=['POST'])
@login_required
def create_saved_routine():
    """Create a new saved routine using raw SQL"""
    from sqlalchemy import text
    
    try:
        if not can_edit_routine():
            return jsonify({
                'success': False,
                'message': 'You do not have permission to create saved routines.'
            }), 403
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        year = data.get('year', '').strip()
        name = data.get('name', '').strip()
        
        if not year:
            return jsonify({
                'success': False,
                'message': 'Year is required'
            }), 400
        
        # Check if year already exists in this window
        wclause, wparams = _window_sql_clause()
        result = db.session.execute(
            text(f"SELECT id FROM saved_routine WHERE year = :year{wclause}"),
            {'year': year, **wparams}
        )
        existing = result.fetchone()
        
        if existing:
            return jsonify({
                'success': False,
                'message': f'A routine for year {year} already exists.'
            }), 400
        
        # Create new saved routine using raw SQL
        user_id = current_user.id if current_user.is_authenticated else None
        window_id = _current_window_id()
        
        from sqlalchemy import inspect
        sr_cols = {c['name'] for c in inspect(db.engine).get_columns('saved_routine')}
        if 'window_id' in sr_cols:
            db.session.execute(
                text("""
                    INSERT INTO saved_routine (year, name, is_revealed, created_by_id, window_id, created_at, updated_at)
                    VALUES (:year, :name, 0, :created_by_id, :window_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    'year': year,
                    'name': name if name else None,
                    'created_by_id': user_id,
                    'window_id': window_id,
                }
            )
        else:
            db.session.execute(
                text("""
                    INSERT INTO saved_routine (year, name, is_revealed, created_by_id, created_at, updated_at)
                    VALUES (:year, :name, 0, :created_by_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {
                    'year': year,
                    'name': name if name else None,
                    'created_by_id': user_id
                }
            )
        db.session.commit()
        
        # Get the inserted ID
        result = db.session.execute(
            text(f"SELECT id FROM saved_routine WHERE year = :year{wclause}"),
            {'year': year, **wparams}
        )
        row = result.fetchone()
        new_id = row[0] if row else None
        
        current_app.logger.info(f'Created saved routine: year={year}, id={new_id}')
        
        return jsonify({
            'success': True,
            'message': 'Saved routine created successfully!',
            'id': new_id,
            'year': year,
            'name': name or year
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating saved routine: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error creating saved routine: {str(e)}'
        }), 500

@routine_management_bp.route('/api/saved-routines/<int:saved_routine_id>', methods=['GET'])
@login_required
def get_saved_routine(saved_routine_id):
    """Get a specific saved routine with its entries using raw SQL"""
    from sqlalchemy import text, inspect
    
    try:
        sr = _get_saved_routine_or_404(saved_routine_id)
        sr_row = (sr.id, sr.year, sr.name, sr.is_revealed)
        
        # Optional: load break settings from saved_routine if columns exist
        inspector = inspect(db.engine)
        sr_columns = [col['name'] for col in inspector.get_columns('saved_routine')]
        lunch_after_slot = 3
        break_type = 'lunch'
        break_time_label = '01:00 PM - 02:00 PM'
        if 'lunch_after_slot' in sr_columns and 'break_type' in sr_columns and 'break_time_label' in sr_columns:
            br = db.session.execute(
                text("SELECT lunch_after_slot, break_type, break_time_label FROM saved_routine WHERE id = :id"),
                {'id': saved_routine_id}
            ).fetchone()
            if br:
                lunch_after_slot = br[0] if br[0] is not None else 3
                break_type = (br[1] or 'lunch').strip() or 'lunch'
                break_time_label = (br[2] or '01:00 PM - 02:00 PM').strip() or '01:00 PM - 02:00 PM'
        
        # Load time slots for this saved routine (from routine_time_slot)
        time_slots_list = []
        try:
            rts_rows = db.session.execute(
                text("SELECT time_slot FROM routine_time_slot WHERE saved_routine_id = :id ORDER BY display_order"),
                {'id': saved_routine_id}
            ).fetchall()
            time_slots_list = [r[0] for r in rts_rows if r[0]]
        except Exception as e:
            current_app.logger.warning(f'Could not load routine_time_slot for {saved_routine_id}: {e}')
        
        # Get all rooms
        all_rooms = {r.room_number: r.id for r in get_rooms_for_routine_window()}
        
        # Check if saved_routine_id column exists in routine table
        routine_columns = [col['name'] for col in inspector.get_columns('routine')]
        has_saved_routine_id = 'saved_routine_id' in routine_columns
        
        routine_data = []
        if has_saved_routine_id:
            # Check which optional columns exist
            has_is_custom = 'is_custom' in routine_columns
            has_custom_course_name = 'custom_course_name' in routine_columns
            has_batch = 'batch' in routine_columns
            has_color_code = 'color_code' in routine_columns
            
            # Build dynamic SQL based on available columns
            select_columns = ['day', 'time_slot', 'room_number', 'course_code', 'teacher_short_name', 
                             'part', 'is_shared', 'shared_with', 'teacher_id', 'year', 'term']
            if has_batch:
                select_columns.append('batch')
            if has_color_code:
                select_columns.append('color_code')
            if has_is_custom:
                select_columns.append('is_custom')
            if has_custom_course_name:
                select_columns.append('custom_course_name')
            
            sql = f"SELECT {', '.join(select_columns)} FROM routine WHERE saved_routine_id = :id"
            
            # Get routine entries using raw SQL
            result = db.session.execute(text(sql), {'id': saved_routine_id})
            rows = result.fetchall()
            
            for row in rows:
                entry = {
                    "day": row[0] or '',
                    "slot": row[1] or '',
                    "room_id": all_rooms.get(row[2]),
                    "room_number": row[2] or '',
                    "course_code": row[3] or '',
                    "teacher_short_name": row[4] or '',
                    "part": row[5] or '',
                    "is_shared": row[6] or False,
                    "shared_with": row[7] or '',
                    "teacher_id": row[8],
                    "year": row[9] or '',
                    "term": row[10] or '',
                    "batch": '',
                    "color_code": '',
                    "is_custom": False,
                    "custom_course_name": ''
                }
                
                # Add optional columns if they exist
                col_idx = 11
                if has_batch:
                    entry["batch"] = row[col_idx] or ''
                    col_idx += 1
                if has_color_code:
                    entry["color_code"] = row[col_idx] or ''
                    col_idx += 1
                if has_is_custom:
                    # Convert MySQL TINYINT(1) to boolean (0/1 -> False/True)
                    is_custom_val = row[col_idx]
                    entry["is_custom"] = bool(is_custom_val) if is_custom_val is not None else False
                    col_idx += 1
                if has_custom_course_name:
                    entry["custom_course_name"] = row[col_idx] or ''
                    col_idx += 1
                
                # Debug log for custom entries
                if entry.get("is_custom"):
                    current_app.logger.info(f"Loading custom entry: day={entry['day']}, slot={entry['slot']}, "
                                         f"course_code={entry.get('course_code')}, "
                                         f"custom_course_name={entry.get('custom_course_name')}")
                
                routine_data.append(entry)
        
        # Overlay live curriculum teacher/callsign so grid stays in sync (and persist to DB)
        _enrich_routine_entries_with_live_teachers(
            routine_data, persist=True, saved_routine_id=saved_routine_id
        )

        payload = {
            'id': sr_row[0],
            'year': sr_row[1],
            'name': sr_row[2] or sr_row[1],
            'is_revealed': sr_row[3] if sr_row[3] is not None else False,
            'routine': routine_data,
            'time_slots': time_slots_list,
            'lunch_after_slot': lunch_after_slot,
            'break_type': break_type,
            'break_time_label': break_time_label
        }
        return jsonify(payload), 200
        
    except Exception as e:
        current_app.logger.error(f'Error getting saved routine {saved_routine_id}: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error fetching saved routine: {str(e)}'
        }), 500

@routine_management_bp.route('/api/saved-routines/<int:saved_routine_id>/duplicate', methods=['POST'])
@login_required
def duplicate_saved_routine(saved_routine_id):
    """Duplicate a saved routine (new year/name, copy all entries and time slots)."""
    from sqlalchemy import text, inspect
    try:
        if not can_edit_routine():
            return jsonify({'success': False, 'message': 'You do not have permission to duplicate routines.'}), 403
        src_sr = _get_saved_routine_or_404(saved_routine_id)
        src = (src_sr.id, src_sr.year, src_sr.name, src_sr.is_revealed)
        if not src:
            return jsonify({'success': False, 'message': 'Saved routine not found.'}), 404
        src_year, src_name = src[1], (src[2] or src[1])
        wclause, wparams = _window_sql_clause()
        window_id = _current_window_id()
        # Unique new year: "2026 (Copy)", "2026 (Copy 2)", ...
        new_year = src_year + " (Copy)"
        n = 1
        while True:
            existing = db.session.execute(
                text(f"SELECT id FROM saved_routine WHERE year = :y{wclause}"),
                {'y': new_year, **wparams}
            ).fetchone()
            if not existing:
                break
            n += 1
            new_year = f"{src_year} (Copy {n})"
        new_name = (src_name or src_year) + " (Copy)" if n == 1 else f"{src_name or src_year} (Copy {n})"
        user_id = current_user.id if current_user.is_authenticated else None
        # Insert new saved_routine
        inspector = inspect(db.engine)
        sr_cols = [c['name'] for c in inspector.get_columns('saved_routine')]
        has_window_col = 'window_id' in sr_cols
        if 'lunch_after_slot' in sr_cols and 'break_type' in sr_cols and 'break_time_label' in sr_cols:
            br = db.session.execute(
                text("SELECT lunch_after_slot, break_type, break_time_label FROM saved_routine WHERE id = :id"),
                {'id': saved_routine_id}
            ).fetchone()
            if has_window_col:
                db.session.execute(
                    text("""
                        INSERT INTO saved_routine (year, name, is_revealed, created_by_id, window_id, created_at, updated_at, lunch_after_slot, break_type, break_time_label)
                        VALUES (:year, :name, 0, :uid, :window_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :la, :bt, :btrl)
                    """),
                    {
                        'year': new_year, 'name': new_name, 'uid': user_id, 'window_id': window_id,
                        'la': br[0] if br and br[0] is not None else 3,
                        'bt': (br[1] or 'lunch') if br else 'lunch',
                        'btrl': (br[2] or '01:00 PM - 02:00 PM') if br else '01:00 PM - 02:00 PM'
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO saved_routine (year, name, is_revealed, created_by_id, created_at, updated_at, lunch_after_slot, break_type, break_time_label)
                        VALUES (:year, :name, 0, :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :la, :bt, :btrl)
                    """),
                    {
                        'year': new_year, 'name': new_name, 'uid': user_id,
                        'la': br[0] if br and br[0] is not None else 3,
                        'bt': (br[1] or 'lunch') if br else 'lunch',
                        'btrl': (br[2] or '01:00 PM - 02:00 PM') if br else '01:00 PM - 02:00 PM'
                    }
                )
        elif has_window_col:
            db.session.execute(
                text("""
                    INSERT INTO saved_routine (year, name, is_revealed, created_by_id, window_id, created_at, updated_at)
                    VALUES (:year, :name, 0, :uid, :window_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {'year': new_year, 'name': new_name, 'uid': user_id, 'window_id': window_id}
            )
        else:
            db.session.execute(
                text("""
                    INSERT INTO saved_routine (year, name, is_revealed, created_by_id, created_at, updated_at)
                    VALUES (:year, :name, 0, :uid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {'year': new_year, 'name': new_name, 'uid': user_id}
            )
        db.session.flush()
        new_id_row = db.session.execute(
            text(f"SELECT id FROM saved_routine WHERE year = :y{wclause}"),
            {'y': new_year, **wparams}
        ).fetchone()
        new_id = new_id_row[0] if new_id_row else None
        if not new_id:
            db.session.rollback()
            return jsonify({'success': False, 'message': 'Failed to create duplicate routine.'}), 500
        # Copy routine entries
        routine_cols = [c['name'] for c in inspector.get_columns('routine')]
        if 'saved_routine_id' in routine_cols:
            copy_cols = [c for c in routine_cols if c != 'id']
            sel_cols = [c if c != 'saved_routine_id' else f":new_id AS saved_routine_id" for c in copy_cols]
            placeholders = {c: c for c in copy_cols if c != 'saved_routine_id'}
            # INSERT INTO routine (cols...) SELECT col1, col2, ..., :new_id FROM routine WHERE saved_routine_id = :sid
            sel_list = ", ".join(c if c != "saved_routine_id" else ":new_id" for c in copy_cols)
            # Use literal new_id in SELECT
            db.session.execute(
                text(f"""
                    INSERT INTO routine ({", ".join(copy_cols)})
                    SELECT {", ".join(c if c != 'saved_routine_id' else str(new_id) for c in copy_cols)}
                    FROM routine WHERE saved_routine_id = :sid
                """),
                {'sid': saved_routine_id}
            )
        # Copy time slots
        try:
            rts = db.session.execute(
                text("SELECT time_slot, display_order FROM routine_time_slot WHERE saved_routine_id = :id ORDER BY display_order"),
                {'id': saved_routine_id}
            ).fetchall()
            for r in rts:
                rts_cols = {c['name'] for c in inspector.get_columns('routine_time_slot')}
                if 'window_id' in rts_cols:
                    db.session.execute(
                        text("""
                            INSERT INTO routine_time_slot (saved_routine_id, time_slot, display_order, is_active, window_id, created_at)
                            VALUES (:sid, :ts, :ord, 1, :window_id, CURRENT_TIMESTAMP)
                        """),
                        {'sid': new_id, 'ts': r[0], 'ord': r[1], 'window_id': window_id}
                    )
                else:
                    db.session.execute(
                        text("""
                            INSERT INTO routine_time_slot (saved_routine_id, time_slot, display_order, is_active, created_at)
                            VALUES (:sid, :ts, :ord, 1, CURRENT_TIMESTAMP)
                        """),
                        {'sid': new_id, 'ts': r[0], 'ord': r[1]}
                    )
        except Exception as e:
            current_app.logger.warning(f'Could not copy routine_time_slot: {e}')
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Routine duplicated as "{new_year}".',
            'id': new_id,
            'year': new_year,
            'name': new_name
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error duplicating saved routine: {e}', exc_info=True)
        return jsonify({'success': False, 'message': f'Failed to duplicate: {str(e)}'}), 500


@routine_management_bp.route('/api/saved-routines/<int:saved_routine_id>', methods=['DELETE'])
@login_required
def delete_saved_routine(saved_routine_id):
    """
    100% RAW SQL DELETE - NO ORM
    ORM causes 'no such column' errors, so we use pure SQL
    """
    from sqlalchemy import text, inspect
    
    try:
        if not can_edit_routine():
            return jsonify({
                'success': False,
                'message': 'You do not have permission to delete saved routines.'
            }), 403
        
        # Step 1: Check if saved routine exists (window-scoped)
        try:
            sr = _get_saved_routine_or_404(saved_routine_id)
            saved_year = sr.year or 'Unknown'
        except Exception:
            return jsonify({
                'success': False,
                'message': f'Saved routine with ID {saved_routine_id} does not exist.'
            }), 404
        
        current_app.logger.info(f'Deleting saved routine: id={saved_routine_id}, year={saved_year}')
        
        # Step 2: Check if routine table has saved_routine_id column
        inspector = inspect(db.engine)
        routine_columns = [col['name'] for col in inspector.get_columns('routine')]
        has_saved_routine_id = 'saved_routine_id' in routine_columns
        
        current_app.logger.info(f'routine table columns: {routine_columns}')
        current_app.logger.info(f'has_saved_routine_id: {has_saved_routine_id}')
        
        # Step 3: Delete routine entries using RAW SQL
        deleted_routines = 0
        if has_saved_routine_id:
            result = db.session.execute(
                text("DELETE FROM routine WHERE saved_routine_id = :id"),
                {'id': saved_routine_id}
            )
            deleted_routines = result.rowcount
            current_app.logger.info(f'Deleted {deleted_routines} routine entries')
        else:
            # No saved_routine_id column - just skip routine deletion
            current_app.logger.warning('saved_routine_id column missing in routine table, skipping routine entries deletion')
        
        # Step 4: Delete saved_routine using RAW SQL
        result = db.session.execute(
            text("DELETE FROM saved_routine WHERE id = :id"),
            {'id': saved_routine_id}
        )
        
        # Step 5: Commit
        db.session.commit()
        
        current_app.logger.info(f'Successfully deleted saved routine: id={saved_routine_id}')
        
        return jsonify({
            'success': True,
            'message': f'Saved routine deleted successfully! ({deleted_routines} routine entries removed)'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error deleting saved routine {saved_routine_id}: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error deleting saved routine: {str(e)}',
            'details': str(e)
        }), 500

@routine_management_bp.route('/api/saved-routines/<int:saved_routine_id>/toggle-reveal', methods=['POST'])
@login_required
def toggle_reveal_saved_routine(saved_routine_id):
    """Toggle reveal status of a saved routine using raw SQL"""
    from sqlalchemy import text, inspect
    
    try:
        if not can_edit_routine():
            return jsonify({
                'success': False,
                'message': 'You do not have permission to toggle reveal status.'
            }), 403
        
        # Check if is_revealed column exists
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('saved_routine')]
        
        if 'is_revealed' not in columns:
            return jsonify({
                'success': False,
                'message': 'Reveal feature is not available. Please run database migrations.'
            }), 400
        
        sr = _get_saved_routine_or_404(saved_routine_id)
        current_is_revealed = sr.is_revealed if sr.is_revealed is not None else False
        new_is_revealed = not current_is_revealed
        
        # Update using raw SQL
        db.session.execute(
            text("UPDATE saved_routine SET is_revealed = :is_revealed WHERE id = :id"),
            {'is_revealed': 1 if new_is_revealed else 0, 'id': saved_routine_id}
        )
        db.session.commit()
        
        current_app.logger.info(f'Toggled reveal for saved routine: id={saved_routine_id}, is_revealed={new_is_revealed}')
        
        return jsonify({
            'success': True,
            'message': 'Reveal status updated successfully!',
            'is_revealed': new_is_revealed
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error toggling reveal for saved routine {saved_routine_id}: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error updating reveal status: {str(e)}'
        }), 500

@routine_management_bp.route('/api/time-slots', methods=['POST'])
@login_required
def save_time_slots():
    """Save custom time slots and break settings for a saved routine"""
    try:
        from sqlalchemy import inspect
        data = request.get_json() or {}
        saved_routine_id = data.get('saved_routine_id')
        time_slots = data.get('time_slots', [])
        lunch_after_slot = data.get('lunch_after_slot', 3)
        break_type_val = (data.get('break_type') or 'lunch').strip() or 'lunch'
        break_time_label = (data.get('break_time') or data.get('break_time_label') or '01:00 PM - 02:00 PM').strip() or '01:00 PM - 02:00 PM'
        
        if not saved_routine_id:
            return jsonify({'success': False, 'message': 'No saved routine ID provided'}), 400
        
        # Check if routine exists
        saved_routine = _get_saved_routine_or_404(saved_routine_id)
        slot_window_id = saved_routine.window_id or _current_window_id()
        
        # Delete existing time slots for this routine
        try:
            db.session.execute(
                text("DELETE FROM routine_time_slot WHERE saved_routine_id = :id"),
                {'id': saved_routine_id}
            )
        except Exception as e:
            current_app.logger.warning(f'Could not delete time slots (table may not exist): {e}')
        
        # Insert new time slots
        for idx, slot in enumerate(time_slots):
            try:
                rts_cols = {c['name'] for c in inspect(db.engine).get_columns('routine_time_slot')}
                if 'window_id' in rts_cols:
                    db.session.execute(
                        text("""
                            INSERT INTO routine_time_slot (saved_routine_id, time_slot, display_order, is_active, window_id, created_at)
                            VALUES (:saved_routine_id, :time_slot, :display_order, 1, :window_id, CURRENT_TIMESTAMP)
                        """),
                        {
                            'saved_routine_id': saved_routine_id,
                            'time_slot': slot,
                            'display_order': idx,
                            'window_id': slot_window_id,
                        }
                    )
                else:
                    db.session.execute(
                        text("""
                            INSERT INTO routine_time_slot (saved_routine_id, time_slot, display_order, is_active, created_at)
                            VALUES (:saved_routine_id, :time_slot, :display_order, 1, CURRENT_TIMESTAMP)
                        """),
                        {
                            'saved_routine_id': saved_routine_id,
                            'time_slot': slot,
                            'display_order': idx
                        }
                    )
            except Exception as insert_error:
                current_app.logger.warning(f'Could not insert time slot {slot}: {insert_error}')
        
        # Save break settings to saved_routine if columns exist
        try:
            sr_columns = [col['name'] for col in inspect(db.engine).get_columns('saved_routine')]
            if 'lunch_after_slot' in sr_columns and 'break_type' in sr_columns and 'break_time_label' in sr_columns:
                db.session.execute(
                    text("""
                        UPDATE saved_routine SET lunch_after_slot = :la, break_type = :bt, break_time_label = :btrl
                        WHERE id = :id
                    """),
                    {'la': lunch_after_slot, 'bt': break_type_val, 'btrl': break_time_label, 'id': saved_routine_id}
                )
        except Exception as br_err:
            current_app.logger.warning(f'Could not save break settings (columns may not exist): {br_err}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Time slots saved successfully!'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error saving time slots: {e}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error saving time slots: {str(e)}'
        }), 500

@routine_management_bp.route('/api/routine/load')
def load_routine():
    routine_entries = _query_for_routine_window(Routine).all()
    all_rooms = {r.room_number: r.id for r in get_rooms_for_routine_window()}
    allowed_teacher_ids = {t.id for t in get_teachers_for_routine_window()}
    window_courses_by_code = {c.course_code: c for c in get_courses_for_routine_window()}

    routine_data = []
    scheduled_courses = set()
    for entry in routine_entries:
        # Track scheduled course codes
        if entry.course_code:
            scheduled_courses.add(entry.course_code)
        teachers_info = []
        if entry.is_shared and entry.shared_with:
            short_names = [name.strip() for name in entry.shared_with.split('/')]
            if allowed_teacher_ids:
                all_involved_teachers = Teacher.query.filter(
                    Teacher.short_name.in_(short_names),
                    Teacher.id.in_(allowed_teacher_ids),
                ).all()
            else:
                all_involved_teachers = []
            teachers_info = [{'id': t.id, 'name': t.name, 'short_name': t.call_sign or t.short_name} for t in all_involved_teachers]
        elif entry.teacher_id and entry.teacher_id in allowed_teacher_ids:
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
                    from blueprints.course_management.models import CourseSessionAssignment
                    course = window_courses_by_code.get(entry.course_code)
                    if course:
                        # Then find the assignment for this teacher and course
                        assignment = _query_for_routine_window(CourseSessionAssignment).filter_by(
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
        routine_list = data.get('routine', []) or []
        title_text = request.args.get('title', 'Class Routine')
        date_text = request.args.get('date', '')

        # Optional course-code filter (view-only client select-before-download)
        course_codes_filter = data.get('course_codes')
        if isinstance(course_codes_filter, list) and course_codes_filter:
            allowed_codes = {
                str(code).strip()
                for code in course_codes_filter
                if str(code).strip()
            }
            if allowed_codes:
                routine_list = [
                    item for item in routine_list
                    if str((item or {}).get('course_code') or '').strip() in allowed_codes
                ]

        # Create a mapping from the list for easy lookup
        # Use day, slot (which may be edited), and room_id as key
        routine_map = {}
        for item in routine_list:
            key = (item['day'], item['slot'], item['room_id'])
            routine_map[key] = item

        buffer = BytesIO()
        # Use A4 landscape for compact single-page output
        from reportlab.lib.pagesizes import A4
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                leftMargin=0.25*inch, rightMargin=0.25*inch,
                                topMargin=0.15*inch, bottomMargin=0.15*inch)
        
        styles = getSampleStyleSheet()
        # Compact header styles
        h1_centered = ParagraphStyle(name='h1_centered', parent=styles['h1'], alignment=TA_CENTER, fontSize=11, spaceAfter=2)
        h2_centered = ParagraphStyle(name='h2_centered', parent=styles['h2'], alignment=TA_CENTER, fontSize=9, spaceAfter=1)
        h3_centered = ParagraphStyle(name='h3_centered', parent=styles['h3'], alignment=TA_CENTER, fontSize=8, spaceAfter=1)
        
        # Compact body text style
        body_text_style = ParagraphStyle(name='BodyText', parent=styles['Normal'], alignment=TA_CENTER, fontSize=6, leading=7)

        elements = []
        
        formatted_date = ''
        if date_text:
            try:
                dt = datetime.strptime(date_text, '%Y-%m-%d')
                formatted_date = dt.strftime('%d-%m-%Y')
            except ValueError:
                formatted_date = date_text # Fallback to raw date

        elements.append(Paragraph(current_tenant().university_name, h1_centered))
        elements.append(Paragraph(current_tenant().name, h2_centered))
        elements.append(Paragraph(title_text, h3_centered))
        if formatted_date:
            elements.append(Paragraph(f"Effective from {formatted_date}", h3_centered))
        elements.append(Spacer(1, 0.04*inch))

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
        
        rooms_db = get_rooms_for_routine_window()
        
        # Get lunch position, break time and break type from frontend (default: after 4th slot, index 3)
        lunch_after_slot = request.args.get('lunch_after_slot', 3, type=int)
        break_time_str = request.args.get('break_time', '01:00 PM - 02:00 PM')
        break_type_param = (request.args.get('break_type') or 'lunch').strip().lower()
        break_cell_label = 'Prayer Break' if break_type_param == 'prayer' else 'LUNCH'
        
        # Helper function to convert time to compact format (9:10-10:00)
        def compact_time(time_str):
            import re
            # Extract times like "09:10 AM - 10:00 AM" or "9:10 AM-10:00 AM"
            match = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)?\s*[-–]\s*(\d{1,2}):(\d{2})\s*(AM|PM)?', time_str, re.IGNORECASE)
            if match:
                h1, m1, ap1, h2, m2, ap2 = match.groups()
                return f"{int(h1)}:{m1}-{int(h2)}:{m2}"
            return time_str.replace(' - ', '-').replace(' AM', '').replace(' PM', '')
        
        # Prepare header: Day, Room, then time slots with lunch inserted after selected slot
        header = ['Day', 'Room']
        break_col_index = None
        
        for idx, slot in enumerate(time_slots):
            header.append(compact_time(slot))
            # Insert break after the selected slot (use editable break time from frontend)
            if idx == lunch_after_slot:
                header.append(compact_time(break_time_str))
                break_col_index = len(header) - 1
        
        table_data = [header]

        # High-contrast categorical palette — MUST match frontend (routine_new.html batchColors)
        batch_colors_hex = [
            '#E11D48',  # Rose red
            '#2563EB',  # Strong blue
            '#16A34A',  # Green
            '#EA580C',  # Orange
            '#7C3AED',  # Violet
            '#0891B2',  # Cyan
            '#CA8A04',  # Gold
            '#BE185D',  # Magenta
            '#1E3A8A',  # Navy
            '#365314',  # Olive
            '#9A3412',  # Brown
            '#0F766E',  # Deep teal
        ]

        def hex_to_rgb_color(hex_color):
            """Convert hex color to reportlab Color with transparency"""
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            return colors.Color(r, g, b, alpha=0.25)

        def _year_term_rank(value):
            v = str(value or '').strip().lower()
            if v.endswith(' year'):
                v = v[:-5].strip()
            if v.endswith(' term'):
                v = v[:-5].strip()
            ranking = {
                'first': 1, '1st': 1, '1': 1,
                'second': 2, '2nd': 2, '2': 2,
                'third': 3, '3rd': 3, '3': 3,
                'fourth': 4, '4th': 4, '4': 4,
                'fifth': 5, '5th': 5, '5': 5,
            }
            if v in ranking:
                return ranking[v]
            try:
                return int(v)
            except (TypeError, ValueError):
                return 99

        def get_color_key(cell_data):
            """year|term so multi-batch same semester share one color; fallback to batch."""
            year = str((cell_data or {}).get('year') or '').strip()
            term = str((cell_data or {}).get('term') or '').strip()
            if year or term:
                return '|'.join(p for p in (year, term) if p)
            return str((cell_data or {}).get('batch') or '').strip()

        def color_key_sort(key):
            parts = str(key).split('|')
            year = parts[0] if parts else ''
            term = parts[1] if len(parts) > 1 else ''
            return (_year_term_rank(year), _year_term_rank(term), str(key))

        # Sequential assignment (sorted year/term) — same approach as frontend
        unique_keys = sorted({
            get_color_key(cell_data)
            for cell_data in routine_map.values()
            if get_color_key(cell_data)
        }, key=color_key_sort)
        batch_color_map = {
            key: hex_to_rgb_color(batch_colors_hex[index % len(batch_colors_hex)])
            for index, key in enumerate(unique_keys)
        }
        cell_batch_colors = []  # Store (row, col, color) for cells with batches
        
        # Data rows
        current_row = 1  # Start from 1 (0 is header)
        break_spans = []  # (col, start_row, end_row) for merged break cells
        for day in days:
            day_first_row = current_row
            for i, room in enumerate(rooms_db):
                row = []
                if i == 0:
                    row.append(Paragraph(f"<b>{day}</b>", body_text_style))
                else:
                    row.append("")
                row.append(Paragraph(str(room.room_number), body_text_style))
                
                # Insert time slots with lunch after selected slot
                current_col = 2  # Start from column 2 (0=Day, 1=Room)
                for idx, slot in enumerate(time_slots):
                    # Find cell data - match by day, slot (which may have been edited), and room_id
                    cell_data = routine_map.get((day, slot, room.id))
                    
                    if cell_data:
                        # Handle custom entries - use custom_course_name if available
                        is_custom = cell_data.get('is_custom', False)
                        custom_name = cell_data.get('custom_course_name', '')
                        course_code = cell_data.get('course_code', '')
                        
                        # For custom entries, prefer custom_course_name, then course_code
                        display_name = custom_name if (is_custom and custom_name) else course_code
                        
                        teacher_short = cell_data.get('teacher_short_name', '')
                        
                        # Build cell content
                        if teacher_short:
                            cell_content = f"<b>{display_name}</b><br/>({teacher_short})"
                        else:
                            cell_content = f"<b>{display_name}</b>"
                        
                        row.append(Paragraph(cell_content, body_text_style))
                        
                        # Track semester-group color (year+term; same as frontend)
                        color_key = get_color_key(cell_data)
                        if color_key and color_key in batch_color_map:
                            cell_batch_colors.append((current_row, current_col, batch_color_map[color_key]))
                    else:
                        row.append("")
                    
                    current_col += 1
                    
                    # Insert break (Prayer/Lunch) after the selected slot
                    if idx == lunch_after_slot:
                        # Show break label only once per day (first room row)
                        if i == 0:
                            row.append(Paragraph(break_cell_label, body_text_style))
                        else:
                            row.append("")
                        current_col += 1
                
                table_data.append(row)
                current_row += 1

            # After finishing all rooms for this day, record span for break column
            if break_col_index is not None and current_row - 1 >= day_first_row:
                break_spans.append((break_col_index, day_first_row, current_row - 1))

        # Compact column widths for A4 landscape
        num_time_cols = len(time_slots) + 1  # +1 for lunch
        # A4 landscape width ~11.69", minus margins ~0.5" = ~11.19" usable
        # Day=0.55", Room=0.45", remaining for time slots
        day_width = 0.55 * inch
        room_width = 0.45 * inch
        remaining_width = 11.0 * inch - day_width - room_width
        time_slot_width = remaining_width / num_time_cols
        
        col_widths = [day_width, room_width]
        for idx in range(num_time_cols):
            col_widths.append(time_slot_width)

        table = Table(table_data, colWidths=col_widths)
        
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('BACKGROUND', (0, 1), (0, -1), colors.Color(0.95, 0.95, 0.95)),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.black),
        ])

        # Row span for Day column
        num_rooms = len(rooms_db) if rooms_db else 1
        for i, day in enumerate(days):
            start_row = 1 + (i * num_rooms)
            end_row = start_row + num_rooms - 1
            if num_rooms > 1:
                style.add('SPAN', (0, start_row), (0, end_row))
                style.add('VALIGN', (0, start_row), (0, end_row), 'MIDDLE')
            # Slightly thicker border above each day's first row for visual separation
            if start_row > 1:
                style.add('LINEABOVE', (0, start_row), (-1, start_row), 1, colors.black)
        
        # Row span for break column (Prayer/Lunch) - merge per day
        for col_idx, start_row, end_row in break_spans:
            if end_row > start_row:
                style.add('SPAN', (col_idx, start_row), (col_idx, end_row))
                style.add('VALIGN', (col_idx, start_row), (col_idx, end_row), 'MIDDLE')
        
        # Apply batch colors to cells
        for row_idx, col_idx, batch_color in cell_batch_colors:
            style.add('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), batch_color)

        table.setStyle(style)
        elements.append(table)
        
        # ========== PAGE 2: Year/Term-wise Course Summary ==========
        from blueprints.course_management.models import Course
        from blueprints.class_management.models import Teacher
        from collections import defaultdict
        
        elements.append(PageBreak())
        
        elements.append(Paragraph("Year/Term-wise Course Summary", h1_centered))
        elements.append(Spacer(1, 0.08*inch))

        # Build mapping: (year, term, course_code) -> {name, teachers}
        summary_map = {}
        for item in routine_list:
            # Skip custom entries (e.g., Academic Committee Meeting)
            if item.get('is_custom'):
                continue

            course_code = (item.get('course_code') or '').strip()
            if not course_code:
                continue
            year_key = (item.get('year') or '').strip() or 'N/A'
            term_key = (item.get('term') or '').strip() or 'N/A'

            # Build teacher labels from embedded teachers info if available
            teacher_labels = set()
            teachers_info = item.get('teachers') or []
            for t in teachers_info:
                name = (t.get('name') or '').strip()
                short = (t.get('short_name') or '').strip()
                if name and short:
                    teacher_labels.add(f"{name} ({short})")
                elif name:
                    teacher_labels.add(name)
                elif short:
                    teacher_labels.add(short)

            # Fallback: if no detailed teachers info, use teacher_short_name from routine item
            if not teacher_labels:
                short_str = (item.get('teacher_short_name') or '').strip()
                if short_str:
                    # Shared teachers may be separated by '/'
                    for short in [s.strip() for s in short_str.split('/') if s.strip()]:
                        teacher_obj = Teacher.query.filter(
                            (Teacher.short_name == short) | (Teacher.call_sign == short)
                        ).first()
                        if teacher_obj:
                            label = f"{(teacher_obj.name or '').strip()} ({(teacher_obj.call_sign or teacher_obj.short_name or short).strip()})"
                        else:
                            label = short
                        teacher_labels.add(label)

            key = (year_key, term_key, course_code)
            if key not in summary_map:
                summary_map[key] = {
                    'course_code': course_code,
                    'course_name': '',
                    'teachers': set()
                }
            summary_map[key]['teachers'].update(teacher_labels)

        # Resolve course names in one query
        all_codes = {k[2] for k in summary_map.keys() if k[2]}
        if all_codes:
            window_courses = {c.course_code: c for c in get_courses_for_routine_window()}
            code_to_name = {
                code: (window_courses[code].course_name or '')
                for code in all_codes
                if code in window_courses
            }
            for key, info in summary_map.items():
                if not info['course_name']:
                    info['course_name'] = code_to_name.get(info['course_code'], '')

        # Group by (year, term)
        grouped = defaultdict(list)
        for (year_key, term_key, _code), info in summary_map.items():
            grouped[(year_key, term_key)].append(info)

        # Sort groups by year/term for stable output using custom academic ordering
        year_order_map = {label: i + 1 for i, label in enumerate(current_tenant().year_labels_in_order)}
        term_order_map = {
            'First': 1,
            'Second': 2,
        }

        def sort_key(item):
            (year_label, term_label), _courses = item
            y_key = str(year_label or '').strip()
            t_key = str(term_label or '').strip()
            y_rank = year_order_map.get(y_key, 99)
            t_rank = term_order_map.get(t_key, 99)
            return (y_rank, t_rank, y_key, t_key)

        sorted_groups = sorted(grouped.items(), key=sort_key)

        # For tight layout, smaller fonts and compact tables
        table_header_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ])
        
        # Build year/term tables and arrange in two columns per page
        group_blocks = []
        for (year_key, term_key), courses_in_group in sorted_groups:
            section_title = f"Year: {year_key}  |  Term: {term_key}"
            title_para = Paragraph(section_title, h3_centered)

            data = [["SI", "Course Code", "Course Name", "Teacher(s)"]]
            for idx, info in enumerate(sorted(courses_in_group, key=lambda c: c['course_code']), 1):
                teacher_text = ', '.join(sorted(info['teachers'])) if info['teachers'] else ''
                data.append([
                    Paragraph(str(idx), body_text_style),
                    Paragraph(info['course_code'], body_text_style),
                    Paragraph(info['course_name'], body_text_style),
                    Paragraph(teacher_text, body_text_style),
                ])

            # Compact inner table widths so each summary table comfortably fits inside one outer column.
            # Sum of widths (0.25 + 0.65 + 1.15 + 1.15 = 3.2\") is < outer column width (3.6\").
            col_widths = [0.25*inch, 0.65*inch, 1.15*inch, 1.15*inch]
            summary_table = Table(data, colWidths=col_widths)
            summary_table.setStyle(table_header_style)

            # A block is title + small spacer + table
            group_blocks.append([title_para, Spacer(1, 0.02*inch), summary_table])

        # Arrange blocks in 2-column layout
        two_col_rows = []
        for i in range(0, len(group_blocks), 2):
            left_block = group_blocks[i]
            right_block = group_blocks[i + 1] if i + 1 < len(group_blocks) else ""
            two_col_rows.append([left_block, right_block])

        if two_col_rows:
            # Outer two-column layout; leave a clear gutter between columns
            outer_table = Table(two_col_rows, colWidths=[3.6*inch, 3.6*inch])
            outer_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            elements.append(outer_table)
        
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
    teachers = get_teachers_for_routine_window()
    for teacher in teachers:
        assignments = _query_for_routine_window(AssignedCourse).filter_by(teacher_id=teacher.id).all()
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
    courses = get_courses_for_routine_window()
    for course in courses:
        assignments = _query_for_routine_window(AssignedCourse).filter_by(course_id=course.id).all()
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
