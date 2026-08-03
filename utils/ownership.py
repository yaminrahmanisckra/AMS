"""Helpers for resolving the Teacher record tied to the logged-in user and
verifying that a user actually owns (teaches) a given class session.

These helpers exist because ``Teacher`` and ``User`` are separate tables with
independent primary keys. Several older routes mistakenly compared
``Teacher.id`` to ``User.id`` (or vice versa), which could let one teacher
edit or delete another teacher's data whenever the IDs happened to collide.
"""

from role_utils import is_admin


def resolve_caller_teacher(user):
    """Return the ``Teacher`` row that corresponds to the given user.

    Resolution order:
    1. ``user.teacher_id`` (explicit link set by an admin), looked up via
       ``Teacher.query.get``.
    2. An exact (case-sensitive) match between ``Teacher.name`` and
       ``user.full_name``.

    Returns ``None`` if the user has no linked/matching teacher record.
    """
    if not user:
        return None

    from blueprints.class_management.models import Teacher

    teacher_id = getattr(user, 'teacher_id', None)
    if teacher_id:
        teacher = Teacher.query.get(teacher_id)
        if teacher:
            return teacher

    full_name = getattr(user, 'full_name', None)
    if full_name:
        teacher = Teacher.query.filter_by(name=full_name).first()
        if teacher:
            return teacher

    return None


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
