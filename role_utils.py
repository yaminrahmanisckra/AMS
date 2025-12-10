"""Shared role definitions and helpers for privilege checks."""

ADMIN_ROLE = 'admin'
ROLE_CHOICES = [
    (ADMIN_ROLE, 'Administrator'),
    ('dean', 'Dean'),
    ('head', 'Head of Discipline'),
    ('teacher', 'Teacher'),
    ('teaching_assistant', 'Teaching Assistant'),
    ('officer', 'Officer'),
    ('student', 'Student'),
]

ROLE_LABELS = {key: label for key, label in ROLE_CHOICES}
NON_ADMIN_ROLE_CHOICES = [choice for choice in ROLE_CHOICES if choice[0] != ADMIN_ROLE]
ASSIGNABLE_ROLE_KEYS = [key for key, _ in NON_ADMIN_ROLE_CHOICES]
# Teachers cannot self-register - only admin can create teacher accounts
SELF_SIGNUP_ROLE_CHOICES = [choice for choice in NON_ADMIN_ROLE_CHOICES if choice[0] not in ['student', 'teacher']]
SELF_SIGNUP_ROLE_KEYS = [key for key, _ in SELF_SIGNUP_ROLE_CHOICES]

DEFAULT_USER_ROLE = 'student'
DEFAULT_TEACHING_ROLE = 'teacher'

CORE_ROLES = {'dean', 'head', 'teacher'}
TEACHING_ROLES = CORE_ROLES | {'teaching_assistant'}
STAFF_ROLES = TEACHING_ROLES | {'officer'}


def get_teachers_excluding_head():
    """Get all teachers excluding Head of the Discipline and Teaching Assistants.
    This function should be used in all places where teacher lists are displayed.
    """
    try:
        from blueprints.class_management.models import Teacher
        from user_models import User
        from sqlalchemy import or_
        from extensions import db
        
        if not Teacher:
            return []
        
        # Get all teachers
        all_teachers = Teacher.query.order_by(Teacher.name).all()
        
        # Get Head of the Discipline users
        head_users = User.query.filter(
            or_(
                User.role.like('%head%'),
                User.role == 'head'
            )
        ).all()
        head_names = {user.full_name for user in head_users}
        
        # Get Teaching Assistant users
        ta_users = User.query.filter(
            or_(
                User.role.like('%teaching_assistant%'),
                User.role.like('%teaching assistant%'),
                User.role == 'teaching_assistant',
                User.role == 'teaching assistant'
            )
        ).all()
        ta_names = {user.full_name for user in ta_users}
        
        # Filter out Head of the Discipline and Teaching Assistants from teachers list
        excluded_names = head_names | ta_names
        teachers = [teacher for teacher in all_teachers if teacher.name not in excluded_names]
        return teachers
    except ImportError:
        return []
    except Exception as e:
        # Log error but don't fail - return all teachers as fallback
        try:
            from flask import current_app
            current_app.logger.warning(f'Error filtering teachers: {e}')
        except:
            pass
        # Fallback: get all teachers if filtering fails
        try:
            from blueprints.class_management.models import Teacher
            return Teacher.query.order_by(Teacher.name).all() if Teacher else []
        except:
            return []


def _coerce_role_values(role_field) -> list[str]:
    """Return lowercase role tokens from strings, iterables, or None."""
    if role_field is None or role_field == '':
        return []
    if isinstance(role_field, (list, tuple, set)):
        parts = role_field
    else:
        text = str(role_field).replace(';', ',')
        parts = text.split(',')
    return [part.strip().lower() for part in parts if part and part.strip()]


def normalize_role_list(role_field) -> list[str]:
    """Return roles in canonical order, filtered to known keys."""
    requested = set(_coerce_role_values(role_field))
    normalized = []
    for key, _ in ROLE_CHOICES:
        if key in requested and key not in normalized:
            normalized.append(key)
    return normalized


def parse_roles(role_field) -> list[str]:
    roles = normalize_role_list(role_field)
    return roles or [DEFAULT_USER_ROLE]


def serialize_roles(role_field) -> str:
    roles = normalize_role_list(role_field)
    if not roles:
        roles = [DEFAULT_USER_ROLE]
    return ','.join(roles)


def get_primary_role(role_field) -> str:
    roles = parse_roles(role_field)
    return roles[0]


def role_label(role_field) -> str:
    roles = parse_roles(role_field)
    labels = [ROLE_LABELS.get(role, role.replace('_', ' ').title()) for role in roles]
    return ', '.join(labels)


def get_effective_roles(user) -> list[str]:
    """Return the roles that should apply for privilege checks (active role first)."""
    if not user:
        return []
    active = getattr(user, 'active_role', None)
    if active:
        return parse_roles(active)
    return parse_roles(getattr(user, 'role', None))


def validate_role_selection(selected_roles) -> tuple[bool, list[str] | str]:
    """Validate complex role combinations. Returns (is_valid, data_or_error)."""
    roles = normalize_role_list(selected_roles)
    if not roles:
        roles = [DEFAULT_USER_ROLE]
    role_set = set(roles)

    if 'officer' in role_set and len(role_set) > 1:
        return False, 'Officer role cannot be combined with other categories.'

    if 'student' in role_set:
        allowed = {'student', 'teaching_assistant'}
        if role_set - allowed:
            return False, 'Students can only be paired with Teaching Assistant.'

    if role_set & CORE_ROLES and (role_set - CORE_ROLES):
        return False, 'Teacher/Dean/Head roles cannot be combined with other categories.'

    return True, roles


def has_teacher_privileges(user) -> bool:
    roles = set(parse_roles(getattr(user, 'role', None)))
    if getattr(user, 'active_role', None):
        roles = set(parse_roles(user.active_role))
    return bool(roles & (TEACHING_ROLES | {ADMIN_ROLE}))


def has_staff_privileges(user) -> bool:
    roles = set(parse_roles(getattr(user, 'role', None)))
    if getattr(user, 'active_role', None):
        roles = set(parse_roles(user.active_role))
    return bool(roles & (STAFF_ROLES | {ADMIN_ROLE}))


def is_admin(user) -> bool:
    if getattr(user, 'active_role', None):
        return ADMIN_ROLE in parse_roles(user.active_role)
    return ADMIN_ROLE in parse_roles(getattr(user, 'role', None))

