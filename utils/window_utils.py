"""
Utility functions for Active Window (operational partition) management.
"""
from datetime import datetime

from flask import session
from sqlalchemy import or_

from extensions import db
from blueprints.course_management.models import OperationalWindow


DEFAULT_WINDOW_ID = 1

WINDOW_EXEMPT_ENDPOINTS = frozenset({
    'static',
    'auth.login',
    'auth.logout',
    'auth.select_window',
    'auth.set_window',
    'auth.no_active_window',
    'auth.login_as',
    'auth.stop_login_as',
})


def get_active_windows():
    """Return all active operational windows."""
    return OperationalWindow.query.filter_by(is_active=True).order_by(
        OperationalWindow.id.asc()
    ).all()


def get_window_by_id(window_id):
    if not window_id:
        return None
    try:
        window_id = int(window_id)
    except (TypeError, ValueError):
        return None
    return OperationalWindow.query.get(window_id)


def get_session_window_id():
    """Current user's selected window from Flask session."""
    raw = session.get('active_window_id')
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def set_session_window_id(window_id):
    session['active_window_id'] = int(window_id)


def clear_session_window_id():
    session.pop('active_window_id', None)


def role_needs_window_selection(active_role):
    """Operational users pick a window when multiple are active."""
    return active_role in ('teacher', 'student', 'head', 'dean')


def user_bypasses_window_selection(user, active_role=None):
    """Only admin accounts skip the window picker."""
    from role_utils import is_admin

    return is_admin(user)


def resolve_window_after_login(user, active_role):
    """
    Set session window when only one is active.
    Returns redirect endpoint name or None if caller should continue.
    """
    if user_bypasses_window_selection(user, active_role):
        return None

    if not role_needs_window_selection(active_role):
        return None

    windows = get_active_windows()
    if not windows:
        return 'auth.no_active_window'
    if len(windows) == 1:
        set_session_window_id(windows[0].id)
        return None
    if get_session_window_id() not in {w.id for w in windows}:
        return 'auth.select_window'
    return None


def ensure_valid_session_window(user, active_role):
    """
    Validate session window on each request.
    Returns redirect endpoint name or None.
    """
    if user_bypasses_window_selection(user, active_role):
        return None

    if not role_needs_window_selection(active_role):
        return None

    windows = get_active_windows()
    active_ids = {w.id for w in windows}

    if not windows:
        clear_session_window_id()
        return 'auth.no_active_window'

    if len(windows) == 1:
        set_session_window_id(windows[0].id)
        return None

    current_id = get_session_window_id()
    if current_id not in active_ids:
        clear_session_window_id()
        return 'auth.select_window'

    return None


def get_effective_window_id(admin_override=False):
    """
    Window id for filtering/creating records.
    Admin without selection may use None (no filter) or explicit session window.
    """
    window_id = get_session_window_id()
    if window_id is not None:
        return window_id
    if admin_override:
        return None
    windows = get_active_windows()
    if len(windows) == 1:
        return windows[0].id
    return DEFAULT_WINDOW_ID


def filter_by_active_window(query, model, admin_override=False):
    """Filter query to the user's selected operational window.

    SECURITY NOTE: rows with window_id IS NULL are treated as "universal" and are
    returned for EVERY window (see the `or_(... .is_(None))` below). This is
    intentional for legacy/shared rows created before windows existed, but it
    means any row that is never stamped with a window_id (e.g. a bug in
    stamp_window_id/ensure_record_in_window, or a manual DB insert) silently
    becomes visible across all operational windows instead of being isolated.
    When adding new window-scoped models/tables, make sure every write path
    sets window_id explicitly — don't rely on this fallback for isolation.
    """
    if admin_override:
        return query

    window_id = get_effective_window_id(admin_override=False)
    if window_id is None:
        return query

    if not hasattr(model, 'window_id'):
        return query

    return query.filter(
        or_(
            getattr(model, 'window_id') == window_id,
            getattr(model, 'window_id').is_(None),
        )
    )


def query_for_window(model, admin_override=None):
    """Start a model query scoped to the active operational window."""
    if admin_override is None:
        try:
            from flask_login import current_user
            from role_utils import is_admin
            admin_override = current_user.is_authenticated and is_admin(current_user)
        except Exception:
            admin_override = False
    return filter_by_active_window(model.query, model, admin_override=admin_override)


def get_for_window(model, record_id, admin_override=None):
    """Fetch one row by id within the active operational window."""
    if record_id is None:
        return None
    return query_for_window(model, admin_override=admin_override).filter_by(id=record_id).first()


def get_or_404_for_window(model, record_id, admin_override=None):
    """Fetch one row by id within the active window or abort 404."""
    from flask import abort
    record = get_for_window(model, record_id, admin_override=admin_override)
    if record is None:
        abort(404)
    return record


def stamp_window_id(obj, window_id=None):
    """Set window_id on a new record when the model supports it."""
    if not hasattr(obj, 'window_id'):
        return obj
    if obj.window_id is not None:
        return obj
    if window_id is None:
        window_id = get_effective_window_id()
    obj.window_id = window_id
    return obj


def ensure_record_in_window(record, admin_override=None):
    """Abort 404 if record belongs to another window."""
    if record is None:
        return record
    if admin_override is None:
        try:
            from flask_login import current_user
            from role_utils import is_admin
            admin_override = current_user.is_authenticated and is_admin(current_user)
        except Exception:
            admin_override = False
    if admin_override:
        return record
    if not hasattr(record, 'window_id'):
        return record
    window_id = get_effective_window_id()
    if window_id is None:
        return record
    if record.window_id is not None and record.window_id != window_id:
        from flask import abort
        abort(404)
    return record


def filter_by_window_sessions(query, session_id_column, session_model=None, admin_override=None):
    """Filter rows that belong to class sessions in the active operational window."""
    if admin_override is None:
        try:
            from flask_login import current_user
            from role_utils import is_admin
            admin_override = current_user.is_authenticated and is_admin(current_user)
        except Exception:
            admin_override = False
    if session_model is None:
        from blueprints.class_management.models import Session as ClassSession
        session_model = ClassSession
    session_ids_q = filter_by_active_window(
        session_model.query.with_entities(session_model.id),
        session_model,
        admin_override=admin_override,
    )
    return query.filter(session_id_column.in_(session_ids_q))


def create_operational_window(name, description=None, academic_session=None,
                              year=None, term=None, batch=None,
                              status=OperationalWindow.STATUS_RUNNING,
                              activated_by=None, is_active=True):
    now = datetime.utcnow()
    window = OperationalWindow(
        name=name.strip(),
        description=(description or '').strip() or None,
        academic_session=(academic_session or '').strip() or None,
        year=(year or '').strip() or None,
        term=(term or '').strip() or None,
        batch=(batch or '').strip() or None,
        status=status or OperationalWindow.STATUS_RUNNING,
        is_active=bool(is_active),
        activated_by=activated_by,
        activated_at=now,
    )
    db.session.add(window)
    db.session.commit()
    return window


def update_operational_window(window_id, name, description=None):
    window = OperationalWindow.query.get_or_404(window_id)
    name = (name or '').strip()
    if not name:
        raise ValueError('Window name is required')
    window.name = name
    if description is not None:
        window.description = (description or '').strip() or None
    db.session.commit()
    return window


def set_window_active(window_id, activated_by=None):
    window = OperationalWindow.query.get_or_404(window_id)
    window.is_active = True
    window.deactivated_at = None
    if activated_by:
        window.activated_by = activated_by
    window.activated_at = datetime.utcnow()
    db.session.commit()
    return window


def deactivate_window(window_id):
    window = OperationalWindow.query.get_or_404(window_id)
    window.is_active = False
    window.deactivated_at = datetime.utcnow()
    db.session.commit()
    return window


def get_active_window_info():
    return [w.to_dict() for w in get_active_windows()]


def get_curriculum_batches(curriculum, window_id=None):
    """Window-scoped applicable batches for a curriculum."""
    if curriculum is None:
        return []
    return curriculum.get_batches_list(window_id=window_id)


def course_is_offered(course, window_id=None):
    """Window-scoped offered flag for a course."""
    if course is None:
        return False
    return course.is_offered(window_id=window_id)


def filter_offered_courses(query, window_id=None):
    """Filter a Course query to rows offered in the active operational window."""
    from sqlalchemy import and_, exists, or_

    from blueprints.course_management.models import Course, CourseWindowOffered

    if window_id is None:
        window_id = get_effective_window_id(admin_override=False)
    if window_id is None:
        return query.filter(Course.offered.is_(True))

    window_row = CourseWindowOffered
    has_window_row = exists().where(
        and_(
            window_row.course_id == Course.id,
            window_row.window_id == window_id,
        )
    )
    window_offered = exists().where(
        and_(
            window_row.course_id == Course.id,
            window_row.window_id == window_id,
            window_row.offered.is_(True),
        )
    )
    fallback_offered = and_(~has_window_row, Course.offered.is_(True))
    return query.filter(or_(window_offered, fallback_offered))
