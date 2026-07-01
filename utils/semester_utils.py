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
        ActiveSemesterConfig.academic_session.desc(),
        ActiveSemesterConfig.year.asc(),
        ActiveSemesterConfig.term.asc()
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
