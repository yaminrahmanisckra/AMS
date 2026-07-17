"""
Utility functions for Active Semester Management
"""
import re
from extensions import db
from sqlalchemy import or_, and_
from blueprints.course_management.models import ActiveSemesterConfig


def _resolve_window_id_for_filter(window_id=None):
    """Resolve window_id for semester filtering from explicit arg or user session."""
    if window_id is not None:
        try:
            return int(window_id)
        except (TypeError, ValueError):
            return None
    try:
        from utils.window_utils import get_effective_window_id, DEFAULT_WINDOW_ID
        resolved = get_effective_window_id(admin_override=False)
        return resolved if resolved is not None else DEFAULT_WINDOW_ID
    except ImportError:
        return 1


def get_active_semesters_for_user(admin_override=False, batch=None):
    """Active semesters for the current user's window, or all windows for admin."""
    if admin_override:
        return get_active_semesters(batch=batch, window_id=None)
    return get_active_semesters(batch=batch, window_id=_resolve_window_id_for_filter(None))


def get_active_semester_info_for_user(admin_override=False, batch=None):
    """Dict list of active semesters for the current user's window."""
    return [sem.to_dict() for sem in get_active_semesters_for_user(admin_override=admin_override, batch=batch)]


def get_active_semesters(batch=None, window_id=None):
    """
    Get active semester configurations, optionally scoped to a window.

    Args:
        batch: Optional batch to filter by. If None, returns all active semesters for the window.
        window_id: Optional operational window id. When None, returns all active semesters (admin list).

    Returns:
        List of ActiveSemesterConfig objects
    """
    query = ActiveSemesterConfig.query.filter_by(is_active=True)

    if window_id is not None:
        try:
            window_id = int(window_id)
        except (TypeError, ValueError):
            window_id = None
        if window_id is not None:
            query = query.filter(ActiveSemesterConfig.window_id == window_id)

    if batch is not None:
        query = query.filter(
            (ActiveSemesterConfig.batch == batch) |
            (ActiveSemesterConfig.batch.is_(None))
        )

    return query.order_by(
        ActiveSemesterConfig.window_id.is_(None),
        ActiveSemesterConfig.window_id.asc(),
        ActiveSemesterConfig.academic_session.desc(),
        ActiveSemesterConfig.year.asc(),
        ActiveSemesterConfig.term.asc(),
        ActiveSemesterConfig.batch.asc(),
    ).all()


def is_semester_active(academic_session, year, term, batch=None, window_id=None):
    """
    Check if a specific semester is active within a window.

    Args:
        academic_session: Academic session string
        year: Year string
        term: Term string
        batch: Optional batch string
        window_id: Optional operational window id (defaults to current session window)

    Returns:
        Boolean indicating if the semester is active
    """
    resolved_window_id = _resolve_window_id_for_filter(window_id)

    query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True,
        window_id=resolved_window_id,
    )

    if batch is not None:
        query = query.filter(
            (ActiveSemesterConfig.batch == batch) |
            (ActiveSemesterConfig.batch.is_(None))
        )

    return query.first() is not None


def _normalize_year_term(value):
    """Normalize year/term values for comparison (e.g., 'First' == '1st' == '1')"""
    if not value:
        return ''
    value_str = str(value).strip().lower()
    if value_str.endswith(' year'):
        value_str = value_str[:-5].strip()
    if value_str.endswith(' term'):
        value_str = value_str[:-5].strip()

    year_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second',
        '3': 'third', '3rd': 'third', 'third': 'third',
        '4': 'fourth', '4th': 'fourth', 'fourth': 'fourth',
        '5': 'fifth', '5th': 'fifth', 'fifth': 'fifth',
        'llm': 'fifth'
    }

    term_map = {
        '1': 'first', '1st': 'first', 'first': 'first',
        '2': 'second', '2nd': 'second', 'second': 'second'
    }

    normalized = year_map.get(value_str, value_str)
    if normalized != value_str:
        return normalized

    return term_map.get(value_str, value_str)


def _normalize_batch_tokens(value):
    """
    Build resilient batch tokens for matching across inconsistent formats.
    """
    if value is None:
        return []
    raw = str(value).strip().lower()
    if not raw:
        return []
    tokens = set()

    for comma_chunk in raw.split(','):
        chunk = comma_chunk.strip()
        if not chunk:
            continue
        compact = ''.join(ch for ch in chunk if ch.isalnum())
        if compact:
            tokens.add(compact)

        for part in re.split(r'[^a-z0-9]+', chunk):
            part = part.strip()
            if part:
                tokens.add(part)

    whole_compact = ''.join(ch for ch in raw if ch.isalnum())
    if whole_compact:
        tokens.add(whole_compact)

    return sorted(tokens)


def _year_variations_for_semester(active_year_norm):
    """Build lowercase year aliases used in semester matching."""
    variations = {active_year_norm}
    alias_map = {
        'first': ['1', '1st', 'first', 'first year'],
        'second': ['2', '2nd', 'second', 'second year'],
        'third': ['3', '3rd', 'third', 'third year'],
        'fourth': ['4', '4th', 'fourth', 'fourth year'],
        'fifth': ['5', '5th', 'fifth', 'fifth year', 'llm'],
        'llm': ['5', '5th', 'fifth', 'fifth year', 'llm'],
    }
    variations.update(alias_map.get(active_year_norm, []))
    return sorted(variations)


def _term_variations_for_semester(active_term_norm):
    """Build lowercase term aliases used in semester matching."""
    variations = {active_term_norm}
    alias_map = {
        'first': ['1', '1st', 'first', 'first term'],
        'second': ['2', '2nd', 'second', 'second term'],
    }
    variations.update(alias_map.get(active_term_norm, []))
    return sorted(variations)


def _build_semester_match_condition(model, semester, lenient_session=True):
    """
    Build one SQLAlchemy condition that matches a single ActiveSemesterConfig row.
    """
    from sqlalchemy import func

    active_year_norm = _normalize_year_term(semester.year)
    active_term_norm = _normalize_year_term(semester.term)

    model_year_lower = func.lower(func.trim(func.cast(getattr(model, 'year'), db.String)))
    model_term_lower = func.lower(func.trim(func.cast(getattr(model, 'term'), db.String)))

    year_condition = model_year_lower.in_(_year_variations_for_semester(active_year_norm))
    term_condition = model_term_lower.in_(_term_variations_for_semester(active_term_norm))

    if semester.academic_session:
        active_session_norm = str(semester.academic_session).strip().lower()
        model_session_norm = func.lower(func.trim(func.coalesce(getattr(model, 'academic_session'), '')))
        if lenient_session:
            academic_session_condition = or_(
                model_session_norm == '',
                model_session_norm == active_session_norm,
            )
        else:
            academic_session_condition = model_session_norm == active_session_norm
    else:
        academic_session_condition = True

    condition = and_(
        academic_session_condition,
        year_condition,
        term_condition,
    )

    if semester.batch and hasattr(model, 'batch'):
        sem_batch_tokens = _normalize_batch_tokens(semester.batch)
        if sem_batch_tokens:
            model_batch_raw = func.lower(
                func.trim(func.cast(getattr(model, 'batch'), db.String))
            )
            model_batch_norm = func.lower(
                func.replace(
                    model_batch_raw,
                    ' ',
                    '',
                )
            )

            token_overlap_conditions = []
            for token in sem_batch_tokens:
                token_overlap_conditions.extend([
                    model_batch_norm == token,
                    model_batch_norm.like(f'%{token}%'),
                    model_batch_norm.like(f'{token},%'),
                    model_batch_norm.like(f'%,{token}'),
                    model_batch_norm.like(f'%,{token},%'),
                    model_batch_raw.like(f'%{token}%'),
                ])

            batch_condition = or_(
                getattr(model, 'batch').is_(None),
                getattr(model, 'batch') == '',
                *token_overlap_conditions,
            )
            condition = and_(condition, batch_condition)

    return condition


def filter_by_semester_config(query, model, semester, lenient_session=True):
    """Filter a query to records matching one active semester configuration."""
    if not semester:
        return query.filter(False)
    return query.filter(_build_semester_match_condition(model, semester, lenient_session=lenient_session))


def semester_context_label(semester):
    """Human-readable label for one active semester row."""
    parts = []
    if semester.year:
        parts.append(str(semester.year).strip())
    if semester.term:
        parts.append(str(semester.term).strip())
    if semester.academic_session:
        parts.append(str(semester.academic_session).strip())
    if semester.batch:
        parts.append(f'Batch {semester.batch}')
    return ' · '.join(parts)


def filter_by_active_semester(query, model, batch=None, admin_override=False, window_id=None):
    """
    Filter a query to only include records from active semesters for the current window.
    """
    if admin_override:
        return query

    resolved_window_id = _resolve_window_id_for_filter(window_id)
    active_semesters = get_active_semesters(batch=batch, window_id=resolved_window_id)

    if not active_semesters:
        return query.filter(False)

    try:
        from flask import current_app
        active_sem_info = [
            f"win{s.window_id}-{s.academic_session}-{s.year}-{s.term}-{s.batch or 'ALL'}"
            for s in active_semesters
        ]
        current_app.logger.info(f'Active semesters for filtering (window {resolved_window_id}): {active_sem_info}')
    except Exception:
        pass

    conditions = []
    for sem in active_semesters:
        from sqlalchemy import func
        active_year_norm = _normalize_year_term(sem.year)
        active_term_norm = _normalize_year_term(sem.term)

        if sem.academic_session:
            model_session_norm = func.lower(func.trim(func.cast(getattr(model, 'academic_session'), db.String)))
            active_session_norm = str(sem.academic_session).strip().lower()
            academic_session_condition = model_session_norm == active_session_norm
        else:
            academic_session_condition = getattr(model, 'academic_session').is_(None)

        model_year_lower = func.lower(func.trim(func.cast(getattr(model, 'year'), db.String)))
        model_term_lower = func.lower(func.trim(func.cast(getattr(model, 'term'), db.String)))

        year_variations = [active_year_norm]
        if active_year_norm == 'first':
            year_variations.extend(['1', '1st', 'first'])
        elif active_year_norm == 'second':
            year_variations.extend(['2', '2nd', 'second'])
        elif active_year_norm == 'third':
            year_variations.extend(['3', '3rd', 'third'])
        elif active_year_norm == 'fourth':
            year_variations.extend(['4', '4th', 'fourth'])
        elif active_year_norm == 'fifth':
            year_variations.extend(['5', '5th', 'fifth', 'llm'])
        elif active_year_norm == 'llm':
            year_variations.extend(['5', '5th', 'fifth', 'llm'])

        term_variations = [active_term_norm]
        if active_term_norm == 'first':
            term_variations.extend(['1', '1st', 'first'])
        elif active_term_norm == 'second':
            term_variations.extend(['2', '2nd', 'second'])

        year_condition = model_year_lower.in_(year_variations)
        term_condition = model_term_lower.in_(term_variations)

        condition = and_(
            academic_session_condition,
            year_condition,
            term_condition
        )

        if sem.batch and hasattr(model, 'batch'):
            sem_batch_tokens = _normalize_batch_tokens(sem.batch)
            if sem_batch_tokens:
                model_batch_raw = func.lower(
                    func.trim(func.cast(getattr(model, 'batch'), db.String))
                )
                model_batch_norm = func.lower(
                    func.replace(
                        model_batch_raw,
                        ' ',
                        ''
                    )
                )

                token_overlap_conditions = []
                for token in sem_batch_tokens:
                    token_overlap_conditions.extend([
                        model_batch_norm == token,
                        model_batch_norm.like(f'%{token}%'),
                        model_batch_norm.like(f'{token},%'),
                        model_batch_norm.like(f'%,{token}'),
                        model_batch_norm.like(f'%,{token},%'),
                        model_batch_raw.like(f'%{token}%')
                    ])

                batch_condition = or_(
                    getattr(model, 'batch').is_(None),
                    *token_overlap_conditions
                )
                condition = and_(condition, batch_condition)

        conditions.append(condition)

    if conditions:
        filtered_query = query.filter(or_(*conditions))

        try:
            from flask import current_app
            current_app.logger.info(
                f'Applied active semester filter with {len(conditions)} condition(s) for window {resolved_window_id}'
            )
        except Exception:
            pass

        return filtered_query

    return query.filter(False)


def get_active_semester_info(batch=None, window_id=None):
    """Get human-readable information about active semesters."""
    active_semesters = get_active_semesters(batch=batch, window_id=window_id)
    return [sem.to_dict() for sem in active_semesters]


def set_active_semester(academic_session, year, term, batch=None, activated_by=None,
                        deactivate_others=False, window_id=None):
    """
    Set a semester as active for a specific operational window.
    """
    from datetime import datetime

    if window_id is None:
        raise ValueError('window_id is required for active semester configuration')

    try:
        window_id = int(window_id)
    except (TypeError, ValueError):
        raise ValueError('Invalid window_id')

    deactivate_others = False

    existing_query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True,
        window_id=window_id,
    )

    if batch is not None:
        existing_query = existing_query.filter_by(batch=batch)
    else:
        existing_query = existing_query.filter(ActiveSemesterConfig.batch.is_(None))

    existing = existing_query.first()

    if existing:
        if activated_by:
            existing.activated_by = activated_by
        existing.activated_at = datetime.utcnow()
        db.session.commit()
        return existing

    if deactivate_others:
        other_semesters_query = ActiveSemesterConfig.query.filter_by(
            is_active=True,
            window_id=window_id,
        )

        if batch is not None:
            other_semesters_query = other_semesters_query.filter(
                (ActiveSemesterConfig.batch == batch) |
                (ActiveSemesterConfig.batch.is_(None))
            )
        else:
            other_semesters_query = other_semesters_query.filter(
                ActiveSemesterConfig.batch.is_(None)
            )

        for sem in other_semesters_query.all():
            sem.is_active = False
            sem.deactivated_at = datetime.utcnow()

    new_config = ActiveSemesterConfig(
        window_id=window_id,
        academic_session=academic_session,
        year=year,
        term=term,
        batch=batch,
        is_active=True,
        activated_by=activated_by
    )

    db.session.add(new_config)
    db.session.commit()

    return new_config


def deactivate_semester(academic_session, year, term, batch=None, window_id=None):
    """Deactivate a specific semester within a window."""
    from datetime import datetime

    if window_id is None:
        raise ValueError('window_id is required to deactivate a semester')

    try:
        window_id = int(window_id)
    except (TypeError, ValueError):
        raise ValueError('Invalid window_id')

    query = ActiveSemesterConfig.query.filter_by(
        academic_session=academic_session,
        year=year,
        term=term,
        is_active=True,
        window_id=window_id,
    )

    if batch is not None:
        query = query.filter_by(batch=batch)
    else:
        query = query.filter(ActiveSemesterConfig.batch.is_(None))

    semester = query.first()

    if semester:
        semester.is_active = False
        semester.deactivated_at = datetime.utcnow()
        db.session.commit()
        return True

    return False


def _parse_batch_values(batch_text):
    if not batch_text:
        return []
    return [
        batch.strip()
        for batch in str(batch_text).split(',')
        if batch.strip() and batch.strip() != 'None'
    ]


def _window_rows_filter(model, window_id):
    """Match rows for a specific operational window."""
    from utils.window_utils import DEFAULT_WINDOW_ID

    window_id = int(window_id)
    if window_id == DEFAULT_WINDOW_ID:
        return or_(
            model.window_id == window_id,
            model.window_id.is_(None),
        )
    return model.window_id == window_id


def _merge_session_combo(sessions_dict, academic_session, year, term, batches=None):
    academic_session = (academic_session or '').strip()
    year = (year or '').strip()
    term = (term or '').strip()
    if not academic_session or not year or not term:
        return

    key = f'{academic_session}|{year}|{term}'
    if key not in sessions_dict:
        sessions_dict[key] = {
            'academic_session': academic_session,
            'year': year,
            'term': term,
            'batches': [],
        }

    for batch in batches or []:
        if batch and batch not in sessions_dict[key]['batches']:
            sessions_dict[key]['batches'].append(batch)


def build_available_sessions_for_window(window_id):
    """
    Build session/year/term/batch combinations scoped to one operational window.
    """
    from blueprints.course_management.models import (
        CurriculumYearTerm,
        CourseSessionAssignment,
        StudentCourseRegistration,
        CurriculumApplicableBatch,
    )
    from blueprints.student_management.models import Student

    try:
        window_id = int(window_id)
    except (TypeError, ValueError):
        return []

    sessions_dict = {}

    available_sessions_data = CurriculumYearTerm.query.with_entities(
        CurriculumYearTerm.academic_session,
        CurriculumYearTerm.year,
        CurriculumYearTerm.term,
        CurriculumYearTerm.batch,
    ).filter(
        CurriculumYearTerm.academic_session.isnot(None),
        CurriculumYearTerm.year.isnot(None),
        CurriculumYearTerm.term.isnot(None),
        _window_rows_filter(CurriculumYearTerm, window_id),
    ).distinct().order_by(
        CurriculumYearTerm.academic_session.desc(),
        CurriculumYearTerm.year.asc(),
        CurriculumYearTerm.term.asc(),
    ).all()

    for row in available_sessions_data:
        _merge_session_combo(
            sessions_dict,
            row[0],
            row[1],
            row[2],
            _parse_batch_values(row[3]),
        )

    assignment_rows = CourseSessionAssignment.query.with_entities(
        CourseSessionAssignment.academic_session,
        CourseSessionAssignment.year,
        CourseSessionAssignment.term,
        CourseSessionAssignment.batch,
    ).filter(
        CourseSessionAssignment.academic_session.isnot(None),
        CourseSessionAssignment.year.isnot(None),
        CourseSessionAssignment.term.isnot(None),
        _window_rows_filter(CourseSessionAssignment, window_id),
    ).distinct().all()

    for row in assignment_rows:
        _merge_session_combo(
            sessions_dict,
            row[0],
            row[1],
            row[2],
            _parse_batch_values(row[3]),
        )

    registration_batch_rows = db.session.query(
        StudentCourseRegistration.academic_session,
        StudentCourseRegistration.year,
        StudentCourseRegistration.term,
        Student.batch,
    ).join(
        Student, Student.id == StudentCourseRegistration.student_id,
    ).filter(
        StudentCourseRegistration.academic_session.isnot(None),
        StudentCourseRegistration.year.isnot(None),
        StudentCourseRegistration.term.isnot(None),
        Student.batch.isnot(None),
        Student.batch != '',
        _window_rows_filter(StudentCourseRegistration, window_id),
    ).distinct().all()

    for row in registration_batch_rows:
        _merge_session_combo(sessions_dict, row[0], row[1], row[2], [row[3]])

    config_rows = ActiveSemesterConfig.query.filter_by(
        window_id=window_id,
    ).with_entities(
        ActiveSemesterConfig.academic_session,
        ActiveSemesterConfig.year,
        ActiveSemesterConfig.term,
        ActiveSemesterConfig.batch,
    ).distinct().all()

    for row in config_rows:
        batches = [row[3]] if row[3] else []
        _merge_session_combo(sessions_dict, row[0], row[1], row[2], batches)

    applicable_batch_rows = CurriculumApplicableBatch.query.filter_by(
        window_id=window_id,
    ).with_entities(
        CurriculumApplicableBatch.applicable_batches,
    ).all()

    applicable_batches = set()
    for row in applicable_batch_rows:
        applicable_batches.update(_parse_batch_values(row[0]))

    if applicable_batches:
        for session_data in sessions_dict.values():
            for batch in sorted(applicable_batches):
                if batch not in session_data['batches']:
                    session_data['batches'].append(batch)

    available_sessions = list(sessions_dict.values())
    for session_data in available_sessions:
        session_data['batches'] = sorted(session_data['batches'])

    available_sessions.sort(
        key=lambda s: (s['academic_session'] or '', s['year'] or '', s['term'] or ''),
        reverse=True,
    )
    return available_sessions


def get_window_semester_defaults(window):
    """Resolve default session/year/term/batch for an operational window."""
    from blueprints.course_management.models import OperationalWindow

    if not window or not isinstance(window, OperationalWindow):
        return {
            'academic_session': '',
            'year': '',
            'term': '',
            'batch': '',
        }

    defaults = {
        'academic_session': (window.academic_session or '').strip(),
        'year': (window.year or '').strip(),
        'term': (window.term or '').strip(),
        'batch': (window.batch or '').strip(),
    }

    if not all([defaults['academic_session'], defaults['year'], defaults['term']]):
        active = ActiveSemesterConfig.query.filter_by(
            window_id=window.id,
            is_active=True,
        ).order_by(
            ActiveSemesterConfig.activated_at.desc(),
        ).first()
        if active:
            defaults['academic_session'] = defaults['academic_session'] or active.academic_session
            defaults['year'] = defaults['year'] or active.year
            defaults['term'] = defaults['term'] or active.term
            if not defaults['batch']:
                defaults['batch'] = (active.batch or '').strip()

    sessions = build_available_sessions_for_window(window.id)
    if sessions and not all([defaults['academic_session'], defaults['year'], defaults['term']]):
        match = sessions[0]
        defaults['academic_session'] = defaults['academic_session'] or match['academic_session']
        defaults['year'] = defaults['year'] or match['year']
        defaults['term'] = defaults['term'] or match['term']

    if defaults['batch']:
        batch_values = set()
        for session_data in sessions:
            if (
                session_data['academic_session'] == defaults['academic_session']
                and session_data['year'] == defaults['year']
                and session_data['term'] == defaults['term']
            ):
                batch_values.update(session_data['batches'])
        if defaults['batch'] not in batch_values:
            defaults['batch'] = ''

    return defaults
