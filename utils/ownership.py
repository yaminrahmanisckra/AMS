"""Helpers for resolving the Teacher record tied to the logged-in user and
verifying that a user actually owns (teaches) a given class session.

These helpers exist because ``Teacher`` and ``User`` are separate tables with
independent primary keys. Several older routes mistakenly compared
``Teacher.id`` to ``User.id`` (or vice versa), which could let one teacher
edit or delete another teacher's data whenever the IDs happened to collide.

AUTHZ-07: Caller identity is ``users.teacher_id`` only — never
``Teacher.name == user.full_name`` (name spoofing / takeover).

AUTHZ-08: Teaching Assistants are granted attendance/marks only for sessions
that match an active ``DutyAssignment`` with ``duty_type=teaching_assistant``.
"""

from role_utils import is_admin, is_teaching_assistant


def normalize_course_code(code) -> str:
    """Uppercase course code with spaces/punctuation collapsed for matching."""
    if not code:
        return ''
    return ''.join(ch for ch in str(code).upper() if ch.isalnum())


def resolve_caller_teacher(user):
    """Return the ``Teacher`` row linked via ``user.teacher_id``.

    Name-based matching is intentionally not used (AUTHZ-07). Returns
    ``None`` when the user has no ``teacher_id`` or the linked row is missing.
    """
    if not user:
        return None

    from blueprints.class_management.models import Teacher

    teacher_id = getattr(user, 'teacher_id', None)
    if not teacher_id:
        return None
    return Teacher.query.get(teacher_id)


def resolve_caller_student(user):
    """Return the roster ``Student`` row for a user (username == student_id)."""
    if not user:
        return None
    username = getattr(user, 'username', None)
    if not username:
        return None
    from blueprints.student_management.models import Student
    return Student.query.filter_by(student_id=username).first()


def active_ta_duties_for_user(user):
    """Active Teaching Assistant duty rows for the caller's student account."""
    student = resolve_caller_student(user)
    if not student:
        return []
    from blueprints.course_management.models import DutyAssignment
    try:
        from utils.window_utils import query_for_window
        return query_for_window(DutyAssignment).filter_by(
            duty_type='teaching_assistant',
            student_id=student.id,
            status='active',
        ).all()
    except Exception:
        return DutyAssignment.query.filter_by(
            duty_type='teaching_assistant',
            student_id=student.id,
            status='active',
        ).all()


def duty_matches_class_session(duty, session_obj) -> bool:
    """True when a TA duty's course/session/year/term align with ``session_obj``.

    Duties without a course code are treated as legacy/global and never match
    (Head must re-assign with course + academic context).
    """
    if not duty or not session_obj:
        return False
    duty_code = normalize_course_code(getattr(duty, 'course_code', None))
    if not duty_code:
        return False
    if duty_code != normalize_course_code(getattr(session_obj, 'course_code', None)):
        return False
    for attr in ('academic_session', 'year', 'term'):
        duty_val = getattr(duty, attr, None)
        if duty_val and duty_val != getattr(session_obj, attr, None):
            return False
    duty_window = getattr(duty, 'window_id', None)
    session_window = getattr(session_obj, 'window_id', None)
    if duty_window and session_window and duty_window != session_window:
        return False
    return True


def user_is_ta_for_session(user, session_obj) -> bool:
    """True if the user is acting as TA and assigned to this class session."""
    if not user or not session_obj or not is_teaching_assistant(user):
        return False
    for duty in active_ta_duties_for_user(user):
        if duty_matches_class_session(duty, session_obj):
            return True
    return False


def sessions_for_ta(user):
    """Class sessions the TA may operate (attendance / marks) in this window."""
    duties = [d for d in active_ta_duties_for_user(user) if normalize_course_code(d.course_code)]
    if not duties:
        return []
    from blueprints.class_management.models import Session
    try:
        from utils.window_utils import query_for_window
        query = query_for_window(Session).filter_by(archived=False)
    except Exception:
        query = Session.query.filter_by(archived=False)
    sessions = query.all()
    matched = []
    for session_obj in sessions:
        for duty in duties:
            if duty_matches_class_session(duty, session_obj):
                matched.append(session_obj)
                break
    return matched


def user_owns_class_session(user, session_obj):
    """True if ``user`` is allowed to modify data belonging to ``session_obj``.

    Administrators always pass. Everyone else must resolve to a ``Teacher``
    record whose id matches ``session_obj.teacher_id``.
    """
    if not user or not session_obj:
        return False

    if is_admin(user):
        return True

    teacher = resolve_caller_teacher(user)
    if not teacher:
        return False

    return teacher.id == getattr(session_obj, 'teacher_id', None)


def user_can_operate_class_session(user, session_obj):
    """Owner/admin or assigned TA may take attendance / enter marks."""
    if user_owns_class_session(user, session_obj):
        return True
    return user_is_ta_for_session(user, session_obj)
